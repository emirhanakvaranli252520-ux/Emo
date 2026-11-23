#!/usr/bin/env python3
"""Trade journal and post-trade review for trader-journal. Standard library only.

The other skills get you into a trade and out of it. This one asks, afterwards,
whether any of it worked: it turns your fills into round-trip trades, scores
each one against the plan you made before the entry (in R, the risk you
planned), and checks the Time Machine's odds against what really happened.

  snapshot  saves the current trader/plan.json (and the Time Machine's odds
            from trader/timemachine.json, when they match) into the journal,
            so the plan survives the next trade overwriting plan.json.
  import    reads the fills trader-broker logged in trader/state/broker.json,
            pairs them into round trips (flat -> position -> flat, per
            symbol) and matches each to the plan for that symbol and day.
            Safe to run again: trades already in the journal are kept.
  add       records a trade by hand (fills from another broker, or a past trade).
  note      adds a note or a tag to a trade ("chased", "news", "A+ setup").
  list      the trades, newest first.
  stats     win rate, average win and loss, profit factor, expectancy in
            dollars and in R, the worst drawdown and losing streak, a
            breakdown by setup, by entry hour and by tag, discipline checks
            (stops that filled past the plan, exits after flat_by, trades with
            no plan) and the Time Machine's calibration.

    python3 journal.py snapshot
    python3 journal.py import
    python3 journal.py add --symbol TSLA --date 2026-10-19 --qty 8 --entry 364.18 --exit 358.10 \\
        --stop 358.32 --target 370.04 --setup orb --opened 10:15 --closed 11:40
    python3 journal.py note --id TSLA-2026-10-19-1015 --tag chased --text "bought the second push"
    python3 journal.py list --last 10
    python3 journal.py stats --since 2026-10-01 --setup orb
    python3 journal.py stats --json

Everything lives in trader/journal.json. Times are New York wall-clock times,
the way trader-broker writes them. This is a scorecard, not advice: a good
month does not make the next one good, and a small sample proves little.
"""

import argparse
import datetime
import json
import math
import os
import re
import sys

EPS = 1e-9
PRICE_TOL = 0.011            # a fill within a cent of the stop or target counts as at it
MIN_SAMPLE = 20              # below this, every number gets a "too few trades" warning


class JournalError(Exception):
    pass


# ---------------------------------------------------------------- files

def read_json(path, what, required=True):
    if not path or not os.path.exists(path):
        if required:
            raise JournalError("no %s at %s" % (what, path))
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except ValueError as e:
        raise JournalError("%s is not valid JSON: %s" % (path, e))


def write_json(path, data):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def load_journal(path):
    doc = read_json(path, "journal", required=False)
    if doc is None:
        doc = {}
    if not isinstance(doc, dict):
        raise JournalError("%s should hold a JSON object" % path)
    doc.setdefault("created_by", "trader-journal")
    doc.setdefault("plans", [])
    doc.setdefault("trades", [])
    return doc


# ---------------------------------------------------------------- small helpers

def num(x, what):
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise JournalError("%s should be a number, not %r" % (what, x))
    return v


def r2(x):
    return None if x is None else round(x + 0.0, 2)


def r4(x):
    return None if x is None else round(x + 0.0, 4)


def check_date(text, what="--date"):
    if not text or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(text)):
        raise JournalError("%s wants a date like 2026-10-19" % what)
    try:
        datetime.date(*[int(p) for p in str(text).split("-")])
    except ValueError:
        raise JournalError("%s %r is not a real date" % (what, text))
    return str(text)


def check_clock(text, what):
    if text is None:
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})$", str(text).strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise JournalError("%s wants a 24-hour New York time like 10:15" % what)
    return "%02d:%02d" % (int(m.group(1)), int(m.group(2)))


def clock_of(at):
    """"2026-10-19T10:15:00-04:00" -> "10:15" (the New York wall clock trader-broker writes)."""
    m = re.match(r"^\d{4}-\d{2}-\d{2}[T ](\d{2}):(\d{2})", str(at or ""))
    return "%s:%s" % (m.group(1), m.group(2)) if m else None


def date_of(rec):
    return str(rec.get("date") or str(rec.get("at", ""))[:10])


def money(x):
    if x is None:
        return "n/a"
    return "%s$%s" % ("-" if x < 0 else "", "{:,.2f}".format(abs(x)))


def signed_money(x):
    return ("+" if x is not None and x >= 0 else "") + money(x)


def pct(x):
    return "n/a" if x is None else "%.1f %%" % (100.0 * x)


def rr(x):
    return "n/a" if x is None else "%+.2fR" % x


def str_num(x):
    return ("%d" % x) if abs(x - round(x)) < EPS else ("%g" % x)


# ---------------------------------------------------------------- plans

def plan_from(plan, tm=None, source="trader/plan.json"):
    """A plan.json (and an optional timemachine.json) -> the journal's plan record."""
    if not isinstance(plan, dict):
        raise JournalError("the plan should be a JSON object")
    sym = str(plan.get("symbol") or "").upper()
    if not sym:
        raise JournalError("the plan has no symbol")
    date = check_date(plan.get("date"), "the plan's date")
    entry, stop = num(plan.get("entry"), "the plan's entry"), num(plan.get("stop"), "the plan's stop")
    if stop >= entry:
        raise JournalError("the plan's stop %.2f is not under its entry %.2f (long side only)" % (stop, entry))
    target = plan.get("target")
    rec = {"symbol": sym, "date": date, "setup": plan.get("setup") or "other",
           "entry": entry, "stop": stop, "target": None if target is None else num(target, "the plan's target"),
           "risk_per_share": r2(entry - stop), "flat_by": plan.get("flat_by"),
           "entry_time": plan.get("entry_time"), "source": source}
    if tm and isinstance(tm, dict):
        tp = tm.get("plan") or {}
        same = (str(tp.get("symbol") or "").upper() == sym and tp.get("date") == date
                and abs(float(tp.get("entry", -1)) - entry) < PRICE_TOL
                and abs(float(tp.get("stop", -1)) - stop) < PRICE_TOL)
        mc = tm.get("mc") or {}
        if same and "p_target" in mc and "p_stop" in mc:
            rec["odds"] = {"p_target": float(mc["p_target"]), "p_stop": float(mc["p_stop"]),
                           "verdict": tm.get("verdict"), "replays": mc.get("replays")}
    return rec


def save_plan(journal, rec):
    """Keep one plan per symbol, day and entry; a newer snapshot replaces an older one."""
    plans = [p for p in journal["plans"]
             if not (p["symbol"] == rec["symbol"] and p["date"] == rec["date"]
                     and abs(p["entry"] - rec["entry"]) < PRICE_TOL)]
    plans.append(rec)
    journal["plans"] = sorted(plans, key=lambda p: (p["date"], p["symbol"]))
    return rec


def find_plan(journal, symbol, date, entry_price=None):
    cands = [p for p in journal["plans"] if p["symbol"] == symbol and p["date"] == date]
    if not cands:
        return None
    if entry_price is None or len(cands) == 1:
        return cands[-1]
    return min(cands, key=lambda p: abs(p["entry"] - entry_price))


# ---------------------------------------------------------------- fills -> round trips

def fills_from_state(state):
    out = []
    for rec in (state or {}).get("orders", []):
        if rec.get("status") != "filled":
            continue
        side = str(rec.get("side", "")).lower()
        if side not in ("buy", "sell"):
            continue
        out.append({"at": str(rec.get("at", "")), "date": date_of(rec),
                    "symbol": str(rec.get("symbol", "")).upper(), "side": side,
                    "qty": num(rec.get("qty"), "a fill's qty"), "price": num(rec.get("price"), "a fill's price")})
    out.sort(key=lambda f: f["at"])
    return out


def round_trips(fills):
    """Fills -> closed round trips (flat -> long -> flat per symbol) and what is still open.
    A sell that is bigger than the position is an error: this journal is long only."""
    trades, book = [], {}
    for f in fills:
        sym = f["symbol"]
        cur = book.get(sym)
        if f["side"] == "buy":
            if cur is None:
                cur = book[sym] = {"symbol": sym, "fills": [], "pos": 0.0}
            cur["fills"].append(f)
            cur["pos"] += f["qty"]
        else:
            if cur is None or cur["pos"] + EPS < f["qty"]:
                raise JournalError("a sell of %s %s at %s is bigger than the position the fills show (%s); "
                                   "this journal is long only" % (str_num(f["qty"]), sym, f["at"],
                                                                  str_num(cur["pos"] if cur else 0)))
            cur["fills"].append(f)
            cur["pos"] -= f["qty"]
            if cur["pos"] <= EPS:
                trades.append(cur["fills"])
                del book[sym]
    still_open = [{"symbol": s, "shares": r4(b["pos"]), "since": b["fills"][0]["at"]} for s, b in book.items()]
    return trades, still_open


def trade_from_fills(fills):
    buys = [f for f in fills if f["side"] == "buy"]
    sells = [f for f in fills if f["side"] == "sell"]
    qty = sum(f["qty"] for f in buys)
    cost = sum(f["qty"] * f["price"] for f in buys)
    proceeds = sum(f["qty"] * f["price"] for f in sells)
    first, last = fills[0], fills[-1]
    return {"symbol": first["symbol"], "date": first["date"], "closed_date": last["date"],
            "opened": clock_of(first["at"]), "closed": clock_of(last["at"]), "qty": r4(qty),
            "entry": r4(cost / qty), "exit": r4(proceeds / qty), "fees": 0.0,
            "fills": len(fills), "source": "trader/state/broker.json",
            "key": "|".join("%s/%s/%s/%s" % (f["at"], f["side"], str_num(f["qty"]), f["price"]) for f in fills)}


def make_id(trade, taken):
    base = "%s-%s-%s" % (trade["symbol"], trade["date"], (trade.get("opened") or "0000").replace(":", ""))
    tid, n = base, 2
    while tid in taken:
        tid, n = "%s-%d" % (base, n), n + 1
    return tid


# ---------------------------------------------------------------- scoring

def score(trade, plan):
    """Fill in P&L, R, the outcome and the discipline flags for one trade."""
    qty, entry, exit_ = trade["qty"], trade["entry"], trade["exit"]
    pnl = (exit_ - entry) * qty - float(trade.get("fees") or 0)
    trade["pnl"] = r2(pnl)
    trade["day_trade"] = trade.get("closed_date", trade["date"]) == trade["date"]
    flags = []
    if plan:
        trade["setup"] = trade.get("setup") or plan.get("setup") or "other"
        risk = plan["entry"] - plan["stop"]
        trade["plan"] = {k: plan.get(k) for k in ("entry", "stop", "target", "risk_per_share", "flat_by")}
        if plan.get("odds"):
            trade["plan"]["odds"] = plan["odds"]
        planned_risk = risk * qty
        trade["planned_risk"] = r2(planned_risk)
        trade["r"] = r2(pnl / planned_risk) if planned_risk > EPS else None
        trade["entry_slip"] = r4(entry - plan["entry"])
        if plan.get("target") is not None and exit_ >= plan["target"] - PRICE_TOL:
            outcome = "target"
        elif exit_ <= plan["stop"] + PRICE_TOL:
            outcome = "stop"
        else:
            outcome = "manual"
        if exit_ < plan["stop"] - PRICE_TOL:
            past = (plan["stop"] - exit_) * qty
            flags.append("stop filled past the plan: %s a share under %.2f, %s more than planned"
                         % ("%.2f" % (plan["stop"] - exit_), plan["stop"], money(past)))
            trade["stop_slip_usd"] = r2(past)
        if entry - plan["entry"] > max(0.25 * risk, PRICE_TOL):
            flags.append("chased the entry: paid %.2f over the plan's %.2f (%.0f %% of the risk)"
                         % (entry - plan["entry"], plan["entry"], 100.0 * (entry - plan["entry"]) / risk))
        flat = plan.get("flat_by")
        if flat and trade.get("closed") and trade["day_trade"] and trade["closed"] > flat:
            flags.append("held past flat_by: out at %s, the plan said flat by %s" % (trade["closed"], flat))
    else:
        trade["setup"] = trade.get("setup") or "other"
        trade["r"], outcome = None, ("win" if pnl > 0 else "loss" if pnl < 0 else "flat")
        flags.append("no plan on file for %s on %s: no stop to measure R against" % (trade["symbol"], trade["date"]))
    if not trade["day_trade"]:
        flags.append("held overnight: opened %s, closed %s" % (trade["date"], trade.get("closed_date")))
    trade["outcome"] = outcome
    trade["flags"] = flags
    return trade


# ---------------------------------------------------------------- stats

def max_drawdown(pnls):
    peak = cum = dd = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return dd


def longest_streak(pnls, losing=True):
    best = cur = 0
    for p in pnls:
        hit = p < 0 if losing else p > 0
        cur = cur + 1 if hit else 0
        best = max(best, cur)
    return best


def mean_std(xs):
    n = len(xs)
    if n < 2:
        return (xs[0] if xs else None), None
    m = sum(xs) / float(n)
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def _betacf(a, b, x):
    """Continued fraction for the regularized incomplete beta (modified Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return h


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    front = math.exp(lbeta)
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1 - x) / b


def t_two_sided_p(t, df):
    """Two-sided p-value of Student's t with df degrees of freedom."""
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def edge_test(xs):
    """One-sample t-test of "the average trade is zero". Returns (t, p) or (None, None)."""
    n = len(xs)
    m, s = mean_std(xs)
    if n < 3 or not s:
        return None, None
    t = m / (s / math.sqrt(n))
    return round(t, 3), round(t_two_sided_p(t, n - 1), 4)


def daily_pnl(trades):
    days = {}
    for t in trades:
        d = t.get("closed_date") or t["date"]
        days[d] = days.get(d, 0.0) + t["pnl"]
    return [days[d] for d in sorted(days)]


def ratios(trades):
    """Per-day Sharpe and Sortino (annualized by sqrt(252) trading days) and Tharp's SQN in R."""
    out = {}
    days = daily_pnl(trades)
    m, s = mean_std(days)
    if len(days) >= 2:
        out["trading_days"] = len(days)
        out["sharpe_daily"] = r2(m / s * math.sqrt(252)) if s else None
        downside = math.sqrt(sum(min(d, 0.0) ** 2 for d in days) / len(days))
        out["sortino_daily"] = r2(m / downside * math.sqrt(252)) if downside > EPS else None
    rs = [t["r"] for t in trades if t.get("r") is not None]
    mr, sr = mean_std(rs)
    if len(rs) >= 2 and sr:
        # Van Tharp's System Quality Number: sqrt(n) x mean R / stdev R, n capped at 100
        out["sqn"] = r2(math.sqrt(min(len(rs), 100)) * mr / sr)
    sample = rs if len(rs) >= 3 else [t["pnl"] for t in trades]
    t, p = edge_test(sample)
    if t is not None:
        out["edge_t"], out["edge_p"], out["edge_on"] = t, p, ("R" if sample is rs else "dollars")
    return out


def sqn_label(sqn):
    if sqn is None:
        return ""
    for lim, word in ((1.6, "poor"), (2.0, "average"), (2.5, "good"), (3.0, "excellent"), (5.0, "superb")):
        if sqn < lim:
            return word
    return "too good to be true: check the data"


def summarize(trades):
    n = len(trades)
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    rs = [t["r"] for t in trades if t.get("r") is not None]
    gross_win, gross_loss = sum(wins), -sum(losses)
    out = {
        "trades": n, "wins": len(wins), "losses": len(losses), "flat": n - len(wins) - len(losses),
        "win_rate": r4(len(wins) / float(n)) if n else None,
        "net_pnl": r2(sum(pnls)), "avg_win": r2(gross_win / len(wins)) if wins else None,
        "avg_loss": r2(-gross_loss / len(losses)) if losses else None,
        "profit_factor": r2(gross_win / gross_loss) if gross_loss > EPS else None,
        "expectancy_usd": r2(sum(pnls) / n) if n else None,
        "trades_with_r": len(rs), "expectancy_r": r2(sum(rs) / len(rs)) if rs else None,
        "best": r2(max(pnls)) if pnls else None, "worst": r2(min(pnls)) if pnls else None,
        "max_drawdown": r2(max_drawdown(pnls)),
        "longest_losing_streak": longest_streak(pnls), "longest_winning_streak": longest_streak(pnls, False),
    }
    if wins and losses:
        out["payoff_ratio"] = r2((gross_win / len(wins)) / (gross_loss / len(losses)))
        # the win rate this payoff needs just to break even
        out["breakeven_win_rate"] = r4(1.0 / (1.0 + out["payoff_ratio"])) if out["payoff_ratio"] else None
        # what each dollar risked on an average loss earns back: (1 + payoff) x win rate - 1
        out["expectancy_ratio"] = r2((1 + (gross_win / len(wins)) / (gross_loss / len(losses)))
                                     * len(wins) / float(n) - 1)
    out.update(ratios(trades))
    return out


def group(trades, key):
    buckets = {}
    for t in trades:
        for k in key(t):
            buckets.setdefault(k, []).append(t)
    rows = []
    for k in sorted(buckets):
        s = summarize(buckets[k])
        rows.append({"key": k, "trades": s["trades"], "win_rate": s["win_rate"], "net_pnl": s["net_pnl"],
                     "expectancy_usd": s["expectancy_usd"], "expectancy_r": s["expectancy_r"]})
    return rows


def calibration(trades):
    """The Time Machine's odds against what happened, on trades that carried them."""
    rated = [t for t in trades if (t.get("plan") or {}).get("odds") and t.get("outcome") in ("target", "stop", "manual")]
    if not rated:
        return None
    n = float(len(rated))
    pred_t = sum(t["plan"]["odds"]["p_target"] for t in rated) / n
    pred_s = sum(t["plan"]["odds"]["p_stop"] for t in rated) / n
    act_t = sum(1 for t in rated if t["outcome"] == "target") / n
    act_s = sum(1 for t in rated if t["outcome"] == "stop") / n
    # Brier score on "target first": 0 is perfect, 0.25 is a coin flip's
    brier = sum((t["plan"]["odds"]["p_target"] - (1.0 if t["outcome"] == "target" else 0.0)) ** 2
                for t in rated) / n
    return {"trades": len(rated), "predicted_target": r4(pred_t), "actual_target": r4(act_t),
            "predicted_stop": r4(pred_s), "actual_stop": r4(act_s), "brier_target": r4(brier)}


def discipline(trades):
    slipped = [t for t in trades if t.get("stop_slip_usd")]
    late = [t for t in trades if any(f.startswith("held past flat_by") for f in t.get("flags", []))]
    chased = [t for t in trades if any(f.startswith("chased the entry") for f in t.get("flags", []))]
    no_plan = [t for t in trades if not t.get("plan")]
    overnight = [t for t in trades if not t.get("day_trade", True)]
    big = [t for t in trades if t.get("r") is not None and t["r"] < -1.2]
    return {"stop_slipped": len(slipped), "stop_slip_usd": r2(sum(t["stop_slip_usd"] for t in slipped)),
            "past_flat_by": len(late), "chased_entries": len(chased), "no_plan": len(no_plan),
            "overnight": len(overnight), "losses_over_1_2r": len(big),
            "followed_plan": r4(1 - len(set(id(t) for t in slipped + late + chased + no_plan + big)) / float(len(trades)))
            if trades else None}


def verdict(s, disc):
    n = s["trades"]
    if not n:
        return "No closed trades yet."
    lines = []
    exp_r = s.get("expectancy_r")
    if s["expectancy_usd"] > 0:
        lines.append("Positive so far: the average trade made %s%s." % (
            money(s["expectancy_usd"]), "" if exp_r is None else " (%s)" % rr(exp_r)))
    elif s["expectancy_usd"] < 0:
        lines.append("Negative so far: the average trade lost %s%s." % (
            money(-s["expectancy_usd"]), "" if exp_r is None else " (%s)" % rr(exp_r)))
    else:
        lines.append("Flat so far: the average trade made nothing.")
    if s.get("breakeven_win_rate") is not None:
        lines.append("With wins %.2f times the size of losses you need to win %s of the time to break even; "
                     "you win %s." % (s["payoff_ratio"], pct(s["breakeven_win_rate"]), pct(s["win_rate"])))
    if disc and disc.get("followed_plan") is not None and disc["followed_plan"] < 0.8:
        lines.append("Only %s of trades followed the plan cleanly: fix the process before judging the setup."
                     % pct(disc["followed_plan"]))
    if n < MIN_SAMPLE:
        lines.append("Only %d trade(s): far too few to tell skill from luck. Treat every number here as a "
                     "rough sketch until there are at least %d." % (n, MIN_SAMPLE))
    return " ".join(lines)


def stats_doc(journal, since=None, until=None, setup=None, symbol=None, tag=None):
    trades = [t for t in journal["trades"] if t.get("status", "closed") == "closed"]
    if since:
        trades = [t for t in trades if t["date"] >= since]
    if until:
        trades = [t for t in trades if t["date"] <= until]
    if setup:
        trades = [t for t in trades if t.get("setup") == setup]
    if symbol:
        trades = [t for t in trades if t["symbol"] == symbol.upper()]
    if tag:
        trades = [t for t in trades if tag in (t.get("tags") or [])]
    trades.sort(key=lambda t: (t.get("closed_date") or t["date"], t.get("closed") or "", t["id"]))
    s = summarize(trades)
    disc = discipline(trades) if trades else None
    return {
        "filters": {k: v for k, v in (("since", since), ("until", until), ("setup", setup),
                                      ("symbol", symbol), ("tag", tag)) if v},
        "summary": s,
        "by_setup": group(trades, lambda t: [t.get("setup") or "other"]),
        "by_hour": group(trades, lambda t: ["%s:00" % t["opened"][:2]] if t.get("opened") else ["unknown"]),
        "by_tag": group(trades, lambda t: t.get("tags") or []),
        "by_outcome": group(trades, lambda t: [t.get("outcome") or "unknown"]),
        "discipline": disc,
        "time_machine": calibration(trades),
        "open_positions": journal.get("open", []),
        "verdict": verdict(s, disc),
        "small_sample": s["trades"] < MIN_SAMPLE,
        "note": "A scorecard of past trades, not a forecast and not financial advice.",
    }


# ---------------------------------------------------------------- text output

def table(rows, title):
    if not rows:
        return []
    out = ["", title, "  %-12s %6s %8s %12s %12s %8s" % ("", "trades", "win", "net", "per trade", "per R")]
    for r in rows:
        out.append("  %-12s %6d %8s %12s %12s %8s" % (r["key"][:12], r["trades"], pct(r["win_rate"]),
                                                       signed_money(r["net_pnl"]),
                                                       signed_money(r["expectancy_usd"]), rr(r["expectancy_r"])))
    return out


def render_stats(doc):
    s = doc["summary"]
    head = "Trade journal"
    if doc["filters"]:
        head += " (" + ", ".join("%s %s" % kv for kv in sorted(doc["filters"].items())) + ")"
    out = [head, ""]
    if not s["trades"]:
        out.append("No closed trades match. Run journal.py import after your fills, or journal.py add.")
        return "\n".join(out)
    out += [
        "  trades          %d  (%d won, %d lost, %d flat)" % (s["trades"], s["wins"], s["losses"], s["flat"]),
        "  win rate        %s" % pct(s["win_rate"]),
        "  net P&L         %s" % signed_money(s["net_pnl"]),
        "  avg win / loss  %s / %s" % (money(s["avg_win"]), money(s["avg_loss"])),
        "  profit factor   %s" % ("n/a" if s["profit_factor"] is None else "%.2f" % s["profit_factor"]),
        "  per trade       %s   %s on %d trade(s) with a plan" % (
            signed_money(s["expectancy_usd"]), rr(s["expectancy_r"]), s["trades_with_r"]),
        "  best / worst    %s / %s" % (signed_money(s["best"]), signed_money(s["worst"])),
        "  max drawdown    %s" % money(s["max_drawdown"]),
        "  streaks         %d losing, %d winning in a row" % (s["longest_losing_streak"], s["longest_winning_streak"]),
    ]
    if s.get("expectancy_ratio") is not None:
        out.append("  expect. ratio   %+.2f (per dollar of average loss)" % s["expectancy_ratio"])
    if s.get("sqn") is not None:
        out.append("  SQN             %.2f (%s; Van Tharp, on R)" % (s["sqn"], sqn_label(s["sqn"])))
    if s.get("trading_days"):
        out.append("  Sharpe/Sortino  %s / %s (daily P&L over %d day(s), x sqrt 252)" % (
            "n/a" if s.get("sharpe_daily") is None else "%.2f" % s["sharpe_daily"],
            "n/a" if s.get("sortino_daily") is None else "%.2f" % s["sortino_daily"], s["trading_days"]))
    if s.get("edge_p") is not None:
        out.append("  edge test       t %.2f, p %.3f on %s: %s" % (
            s["edge_t"], s["edge_p"], s["edge_on"],
            "unlikely to be luck alone" if s["edge_p"] < 0.05 and s["edge_t"] > 0 else
            "a real loser, not bad luck" if s["edge_p"] < 0.05 else "can't tell from luck yet"))
    out += table(doc["by_setup"], "By setup")
    out += table(doc["by_hour"], "By entry hour (New York)")
    out += table(doc["by_tag"], "By tag")
    out += table(doc["by_outcome"], "By outcome")
    d = doc["discipline"]
    if d:
        out += ["", "Discipline",
                "  followed the plan cleanly   %s" % pct(d["followed_plan"]),
                "  stops filled past the plan  %d (%s beyond plan)" % (d["stop_slipped"], money(d["stop_slip_usd"])),
                "  losses worse than -1.2R     %d" % d["losses_over_1_2r"],
                "  chased entries              %d" % d["chased_entries"],
                "  exits after flat_by         %d" % d["past_flat_by"],
                "  held overnight              %d" % d["overnight"],
                "  trades with no plan         %d" % d["no_plan"]]
    c = doc["time_machine"]
    if c:
        out += ["", "Time Machine vs reality (%d trade(s) with its odds)" % c["trades"],
                "  target first   predicted %s, happened %s" % (pct(c["predicted_target"]), pct(c["actual_target"])),
                "  stop first     predicted %s, happened %s" % (pct(c["predicted_stop"]), pct(c["actual_stop"])),
                "  Brier score    %.3f (0 is perfect, 0.25 is a coin flip)" % c["brier_target"]]
    if doc["open_positions"]:
        out += ["", "Still open (not scored): " + ", ".join(
            "%s %s since %s" % (p["symbol"], str_num(p["shares"]), p["since"]) for p in doc["open_positions"])]
    out += ["", doc["verdict"], "", doc["note"]]
    return "\n".join(out)


def render_list(trades):
    if not trades:
        return "No trades in the journal yet."
    out = ["%-26s %-5s %6s %9s %9s %10s %7s  %s" % ("id", "setup", "qty", "entry", "exit", "P&L", "R", "outcome")]
    for t in trades:
        out.append("%-26s %-5s %6s %9.2f %9.2f %10s %7s  %s" % (
            t["id"], (t.get("setup") or "")[:5], str_num(t["qty"]), t["entry"], t["exit"],
            signed_money(t["pnl"]), rr(t.get("r")), t.get("outcome", "")))
        for f in t.get("flags", []):
            out.append("    ! " + f)
        if t.get("tags") or t.get("notes"):
            out.append("    # " + " ".join("[%s]" % g for g in t.get("tags") or []) +
                       (" " if t.get("tags") and t.get("notes") else "") + " / ".join(t.get("notes") or []))
    return "\n".join(out)


# ---------------------------------------------------------------- commands

def cmd_snapshot(a):
    j = load_journal(a.journal)
    plan = read_json(a.plan, "plan (run trader-exit plan --write first)")
    tm = read_json(a.timemachine, "time machine result", required=False)
    rec = save_plan(j, plan_from(plan, tm, source=a.plan))
    write_json(a.journal, j)
    odds = rec.get("odds")
    return "Saved the plan for %s on %s: entry %.2f, stop %.2f, target %s%s." % (
        rec["symbol"], rec["date"], rec["entry"], rec["stop"],
        "none" if rec["target"] is None else "%.2f" % rec["target"],
        "" if not odds else ", Time Machine %s target first / %s stop first" % (pct(odds["p_target"]),
                                                                              pct(odds["p_stop"])))


def cmd_import(a):
    j = load_journal(a.journal)
    snap = ""
    plan = read_json(a.plan, "plan", required=False)
    if plan:
        try:
            tm = read_json(a.timemachine, "time machine result", required=False)
            save_plan(j, plan_from(plan, tm, source=a.plan))
            snap = " (and saved the current plan)"
        except JournalError as e:
            snap = " (the current plan was not saved: %s)" % e
    state = read_json(a.state, "broker log (record fills with trader-broker's ticket.py fill)")
    trips, still_open = round_trips(fills_from_state(state))
    known = set(t.get("key") for t in j["trades"])
    taken = set(t["id"] for t in j["trades"])
    added = []
    for fills in trips:
        t = trade_from_fills(fills)
        if t["key"] in known:
            continue
        t["id"] = make_id(t, taken)
        taken.add(t["id"])
        t["status"] = "closed"
        score(t, find_plan(j, t["symbol"], t["date"], t["entry"]))
        j["trades"].append(t)
        added.append(t)
    j["open"] = still_open
    write_json(a.journal, j)
    msg = ["Imported %d new trade(s) from %s%s; %d already in the journal."
           % (len(added), a.state, snap, len(trips) - len(added))]
    for t in added:
        msg.append("  %s  %s  %s  %s" % (t["id"], signed_money(t["pnl"]), rr(t.get("r")), t["outcome"]))
    if still_open:
        msg.append("Still open, scored once it closes: " + ", ".join(
            "%s %s" % (p["symbol"], str_num(p["shares"])) for p in still_open))
    return "\n".join(msg)


def cmd_add(a):
    j = load_journal(a.journal)
    date = check_date(a.date)
    qty, entry, exit_ = num(a.qty, "--qty"), num(a.entry, "--entry"), num(a.exit, "--exit")
    if qty <= 0 or entry <= 0 or exit_ <= 0:
        raise JournalError("--qty, --entry and --exit must be positive")
    sym = a.symbol.upper()
    t = {"symbol": sym, "date": date, "closed_date": check_date(a.closed_date, "--closed-date") if a.closed_date else date,
         "opened": check_clock(a.opened, "--opened"), "closed": check_clock(a.closed, "--closed"),
         "qty": qty, "entry": entry, "exit": exit_, "fees": num(a.fees or 0, "--fees"),
         "fills": 2, "source": "manual", "status": "closed", "setup": a.setup}
    if a.stop is not None:
        stop = num(a.stop, "--stop")
        if stop >= entry:
            raise JournalError("--stop %.2f is not under --entry %.2f (long side only)" % (stop, entry))
        plan = {"symbol": sym, "date": date, "setup": a.setup or "other", "entry": entry, "stop": stop,
                "target": None if a.target is None else num(a.target, "--target"),
                "risk_per_share": r2(entry - stop), "flat_by": check_clock(a.flat_by or "15:55", "--flat-by"),
                "source": "manual"}
    else:
        plan = find_plan(j, sym, date, entry)
    t["key"] = "manual|%s|%s|%s|%s|%s|%s" % (sym, date, t["opened"], str_num(qty), entry, exit_)
    if any(x.get("key") == t["key"] for x in j["trades"]):
        raise JournalError("that trade is already in the journal")
    t["id"] = make_id(t, set(x["id"] for x in j["trades"]))
    score(t, plan)
    if a.note:
        t["notes"] = [a.note]
    if a.tag:
        t["tags"] = sorted(set(a.tag))
    j["trades"].append(t)
    write_json(a.journal, j)
    return "Added %s: %s, %s, %s%s" % (t["id"], signed_money(t["pnl"]), rr(t.get("r")), t["outcome"],
                                       "".join("\n  ! " + f for f in t["flags"]))


def cmd_note(a):
    j = load_journal(a.journal)
    hit = [t for t in j["trades"] if t["id"] == a.id]
    if not hit:
        raise JournalError("no trade %s in the journal (journal.py list shows the ids)" % a.id)
    t = hit[0]
    if not a.text and not a.tag:
        raise JournalError("give --text, --tag or both")
    if a.text:
        t.setdefault("notes", []).append(a.text)
    if a.tag:
        t["tags"] = sorted(set((t.get("tags") or []) + a.tag))
    write_json(a.journal, j)
    return "Noted on %s." % t["id"]


def cmd_list(a):
    j = load_journal(a.journal)
    trades = sorted(j["trades"], key=lambda t: (t["date"], t.get("opened") or "", t["id"]), reverse=True)
    if a.symbol:
        trades = [t for t in trades if t["symbol"] == a.symbol.upper()]
    if a.last:
        trades = trades[:a.last]
    if a.json:
        return json.dumps(trades, indent=2)
    return render_list(trades)


def cmd_stats(a):
    j = load_journal(a.journal)
    doc = stats_doc(j, since=a.since and check_date(a.since, "--since"),
                    until=a.until and check_date(a.until, "--until"), setup=a.setup, symbol=a.symbol, tag=a.tag)
    return json.dumps(doc, indent=2) if a.json else render_stats(doc)


def build_parser():
    ap = argparse.ArgumentParser(description="Trade journal and post-trade review (trader-journal).")
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--journal", default="trader/journal.json")
        return p

    p = common(sub.add_parser("snapshot", help="save the current plan (and Time Machine odds) into the journal"))
    p.add_argument("--plan", default="trader/plan.json")
    p.add_argument("--timemachine", default="trader/timemachine.json")
    p.set_defaults(fn=cmd_snapshot)

    p = common(sub.add_parser("import", help="turn trader-broker's fills into scored round trips"))
    p.add_argument("--state", default="trader/state/broker.json")
    p.add_argument("--plan", default="trader/plan.json")
    p.add_argument("--timemachine", default="trader/timemachine.json")
    p.set_defaults(fn=cmd_import)

    p = common(sub.add_parser("add", help="record a trade by hand"))
    p.add_argument("--symbol", required=True)
    p.add_argument("--date", required=True, help="the day it was opened, 2026-10-19")
    p.add_argument("--closed-date", help="if it was closed on a later day")
    p.add_argument("--qty", required=True)
    p.add_argument("--entry", required=True, help="average buy price")
    p.add_argument("--exit", required=True, help="average sell price")
    p.add_argument("--stop", help="the planned stop (else the saved plan for that symbol and day)")
    p.add_argument("--target")
    p.add_argument("--flat-by", help="with --stop: the planned flat-by time (default 15:55)")
    p.add_argument("--setup", help="orb, flag, bounce, level, ...")
    p.add_argument("--opened", help="New York time in, 10:15")
    p.add_argument("--closed", help="New York time out, 11:40")
    p.add_argument("--fees", help="commissions and fees in dollars")
    p.add_argument("--note")
    p.add_argument("--tag", action="append")
    p.set_defaults(fn=cmd_add)

    p = common(sub.add_parser("note", help="add a note or tag to a trade"))
    p.add_argument("--id", required=True)
    p.add_argument("--text")
    p.add_argument("--tag", action="append")
    p.set_defaults(fn=cmd_note)

    p = common(sub.add_parser("list", help="the trades, newest first"))
    p.add_argument("--last", type=int)
    p.add_argument("--symbol")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_list)

    p = common(sub.add_parser("stats", help="the scorecard"))
    p.add_argument("--since")
    p.add_argument("--until")
    p.add_argument("--setup")
    p.add_argument("--symbol")
    p.add_argument("--tag")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_stats)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    try:
        print(a.fn(a))
    except JournalError as e:
        print("journal: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

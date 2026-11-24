#!/usr/bin/env python3
"""Smart Money Levels for trader-smc. Standard library only. Long side only. It never places an order.

Reads a stock's bars (free Yahoo chart data, or a saved chart JSON) and maps
the price structure the "smart money concepts" (SMC / ICT) crowd trades:

  swings        confirmed swing highs and lows (a pivot needs N bars on each
                side, so it is only known N bars later; nothing looks ahead)
  structure     BOS (break of structure: a close through the last swing in
                the trend's direction) and CHoCH (change of character: the
                first close through it against the trend), and the trend now
  fvg           fair value gaps: a three-bar gap between bar 1's high and bar
                3's low (bullish) or bar 1's low and bar 3's high (bearish),
                open, touched or filled
  order blocks  the last down-candle zone before a bullish break (support) and
                the last up-candle zone before a bearish break (resistance),
                active until a close through it
  liquidity     equal highs / equal lows: two or more swings within a small
                tolerance, where stops cluster; swept once price runs past them
  prior day     the previous session's high and low (intraday bars)

It then lists the nearest support under the last close and resistance over
it, and suggests a level for trader-entry (--setup level) and a stop for
trader-exit (--stop price:X). They are levels to test, not signals: run them
through /trader-timemachine and score them in /trader-journal.

    python3 smc.py levels TSLA                         # 5-minute bars, last 5 days
    python3 smc.py levels TSLA --interval 1d --range 1y --swing 3
    python3 smc.py levels TSLA --at "2026-10-19 10:15" --offline saved-chart.json
    python3 smc.py levels TSLA --json --write          # also trader/smc.json

The detection rules follow joshyattridge/smart-money-concepts (MIT, Copyright
(c) 2020 NeuralNine), rewritten here in the standard library with two changes
for live use: a swing only counts once N bars have closed after it, and no
swing is invented at the first or last bar.
"""

import argparse
import datetime
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; day-trader-skill/2.0; +https://github.com/Jakeschincariol/day-trader-skill)"
HOSTS = ("query2", "query1")
BACKOFF = 5.0
INTERVALS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "60m": 3600, "1h": 3600, "1d": 86400}
DEFAULT_RANGE = {"1m": "5d", "5m": "5d", "15m": "1mo", "30m": "1mo", "60m": "3mo", "1h": "3mo", "1d": "1y"}
EPOCH = datetime.datetime(1970, 1, 1)


class SMCError(Exception):
    pass


# ---------------------------------------------------------------- time (New York, no tz files)

def _nth_sunday(year, month, n):
    d = datetime.date(year, month, 1)
    d += datetime.timedelta(days=(6 - d.weekday()) % 7)
    return d + datetime.timedelta(weeks=n - 1)


def eastern_offset(utc):
    y = utc.year
    start = datetime.datetime.combine(_nth_sunday(y, 3, 2), datetime.time(7, 0))
    end = datetime.datetime.combine(_nth_sunday(y, 11, 1), datetime.time(6, 0))
    naive = utc.replace(tzinfo=None)
    return -4 if start <= naive < end else -5


def to_eastern(utc):
    return utc.replace(tzinfo=None) + datetime.timedelta(hours=eastern_offset(utc))


def eastern_to_utc(local):
    for off in (-4, -5):
        utc = local - datetime.timedelta(hours=off)
        if eastern_offset(utc) == off:
            return utc
    return local + datetime.timedelta(hours=5)


def ts_et(ts):
    return to_eastern(EPOCH + datetime.timedelta(seconds=int(ts)))


def parse_now(text):
    """ISO time -> naive UTC. A time without an offset is New York time."""
    if not text:
        return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0, tzinfo=None)
    t = text.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(t)
    except ValueError:
        raise SMCError("--at wants a time like \"2026-10-19 10:15\" (New York) or ...Z (UTC)")
    if dt.tzinfo is None:
        return eastern_to_utc(dt)
    return (dt - dt.utcoffset()).replace(tzinfo=None)


# ---------------------------------------------------------------- data

def yahoo_get(path):
    last = "no answer"
    for host in HOSTS:
        url = "https://%s.finance.yahoo.com%s" % (host, path)
        for attempt in (0, 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                code = e.code
                e.close()
                last = "HTTP %d" % code
                if code == 429 and attempt == 0:
                    time.sleep(BACKOFF)
                    continue
                if code == 429 or code >= 500:
                    break
                raise SMCError("Yahoo answered HTTP %d for %s" % (code, url.split("?")[0]))
            except (urllib.error.URLError, OSError) as e:
                last = "network error: %s" % (getattr(e, "reason", e),)
                break
    raise SMCError("Yahoo did not answer (%s): wait a minute and try again" % last)


def read_text(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return fh.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def parse_chart(text, sym):
    """Yahoo chart JSON v8 -> (meta, bars). Bars with a null close are dropped."""
    try:
        data = json.loads(text)
        res = data["chart"]["result"]
    except (ValueError, KeyError, TypeError):
        raise SMCError("the chart data for %s is not Yahoo chart JSON" % sym)
    if not res:
        err = (data.get("chart") or {}).get("error") or {}
        raise SMCError("Yahoo has no data for %s: %s" % (sym, err.get("description") or "unknown ticker"))
    r = res[0] or {}
    meta = r.get("meta") or {}
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0] or {}

    def at(key, i):
        arr = q.get(key) or []
        return arr[i] if i < len(arr) else None

    bars = []
    for i, t in enumerate(r.get("timestamp") or []):
        c = at("close", i)
        if t is None or c is None:
            continue
        o, h, lo = at("open", i), at("high", i), at("low", i)
        bars.append({"t": int(t), "o": float(c if o is None else o), "h": float(c if h is None else h),
                     "l": float(c if lo is None else lo), "c": float(c), "v": int(at("volume", i) or 0)})
    return meta, bars


def closed_bars(bars, interval, now_utc):
    """Only bars that had closed by now: a forming bar would move every level."""
    step = INTERVALS[interval]
    cut = int((now_utc - EPOCH).total_seconds())
    if interval == "1d":
        # a daily bar is complete once its New York date is before today's (or it is past 16:00 today)
        now_et = to_eastern(now_utc)
        out = []
        for b in bars:
            d = ts_et(b["t"]).date()
            if d < now_et.date() or (d == now_et.date() and now_et.time() >= datetime.time(16, 0)):
                out.append(b)
        return out
    return [b for b in bars if b["t"] + step <= cut]


# ---------------------------------------------------------------- detection

def swings(bars, n):
    """Confirmed swing highs (+1) and lows (-1): {i, kind, level, confirmed_at}.
    A high must be above the n bars before it and not below the n bars after.
    Back-to-back swings of one kind are all kept: merging them into the more
    extreme one (as the library does) would erase a swing that was already
    confirmed, and maybe already broken, because of a bar that came later."""
    out = []
    for i in range(n, len(bars) - n):
        h, lo = bars[i]["h"], bars[i]["l"]
        left, right = bars[i - n:i], bars[i + 1:i + n + 1]
        if h > max(b["h"] for b in left) and h >= max(b["h"] for b in right):
            out.append({"i": i, "kind": 1, "level": h, "confirmed_at": i + n})
        elif lo < min(b["l"] for b in left) and lo <= min(b["l"] for b in right):
            out.append({"i": i, "kind": -1, "level": lo, "confirmed_at": i + n})
    return out


def fvgs(bars):
    """Fair value gaps, with how far later bars have filled them."""
    out = []
    for i in range(1, len(bars) - 1):
        a, b, c = bars[i - 1], bars[i], bars[i + 1]
        if b["c"] > b["o"] and a["h"] < c["l"]:
            g = {"i": i, "kind": 1, "top": c["l"], "bottom": a["h"]}
        elif b["c"] < b["o"] and a["l"] > c["h"]:
            g = {"i": i, "kind": -1, "top": a["l"], "bottom": c["h"]}
        else:
            continue
        g["status"], g["touched_at"], g["filled_at"] = "open", None, None
        for j in range(i + 2, len(bars)):
            x = bars[j]
            if g["kind"] == 1:
                if x["l"] <= g["bottom"]:
                    g["status"], g["filled_at"] = "filled", j
                    g["touched_at"] = g["touched_at"] if g["touched_at"] is not None else j
                    break
                if x["l"] <= g["top"] and g["touched_at"] is None:
                    g["status"], g["touched_at"] = "touched", j
            else:
                if x["h"] >= g["top"]:
                    g["status"], g["filled_at"] = "filled", j
                    g["touched_at"] = g["touched_at"] if g["touched_at"] is not None else j
                    break
                if x["h"] >= g["bottom"] and g["touched_at"] is None:
                    g["status"], g["touched_at"] = "touched", j
        out.append(g)
    return out


def structure(bars, sw):
    """Walk the bars in order. A close above the last confirmed, unbroken swing
    high is a bullish BOS (in an uptrend or with no trend yet) or CHoCH (in a
    downtrend); the mirror for lows. Each break also marks an order block:
    the lowest-low candle between that swing and the break (bullish), or the
    highest-high one (bearish)."""
    events, blocks = [], []
    trend = 0
    last_high = last_low = None
    k = 0
    pending = sorted(sw, key=lambda s: s["confirmed_at"])
    for i, b in enumerate(bars):
        while k < len(pending) and pending[k]["confirmed_at"] <= i:
            s = dict(pending[k], broken=False)
            if s["kind"] == 1:
                last_high = s
            else:
                last_low = s
            k += 1
        for ob in blocks:
            if ob["status"] != "active" or ob["i"] >= i:
                continue
            if ob["kind"] == 1 and b["c"] < ob["bottom"]:
                ob["status"], ob["broken_at"] = "broken", i
            elif ob["kind"] == -1 and b["c"] > ob["top"]:
                ob["status"], ob["broken_at"] = "broken", i
        if last_high and not last_high["broken"] and b["c"] > last_high["level"]:
            kind = "CHoCH" if trend == -1 else "BOS"
            events.append({"i": i, "type": kind, "dir": 1, "level": last_high["level"], "swing_i": last_high["i"]})
            last_high["broken"] = True
            trend = 1
            seg = range(last_high["i"] + 1, i) if i - last_high["i"] > 1 else [i - 1]
            j = min(seg, key=lambda x: (bars[x]["l"], -x))
            blocks.append({"i": j, "kind": 1, "top": bars[j]["h"], "bottom": bars[j]["l"], "formed_at": i,
                           "status": "active", "broken_at": None})
        elif last_low and not last_low["broken"] and b["c"] < last_low["level"]:
            kind = "CHoCH" if trend == 1 else "BOS"
            events.append({"i": i, "type": kind, "dir": -1, "level": last_low["level"], "swing_i": last_low["i"]})
            last_low["broken"] = True
            trend = -1
            seg = range(last_low["i"] + 1, i) if i - last_low["i"] > 1 else [i - 1]
            j = max(seg, key=lambda x: (bars[x]["h"], x))
            blocks.append({"i": j, "kind": -1, "top": bars[j]["h"], "bottom": bars[j]["l"], "formed_at": i,
                           "status": "active", "broken_at": None})
    return trend, events, blocks


def liquidity(bars, sw, tol_pct):
    """Equal highs / equal lows: 2+ swings of one kind within tol_pct of the first,
    before price ran past them. Swept once a later bar trades beyond the pool."""
    pools = []
    used = set()
    for a_idx, a in enumerate(sw):
        if a_idx in used:
            continue
        tol = a["level"] * tol_pct / 100.0
        members = [a]
        for b_idx in range(a_idx + 1, len(sw)):
            b = sw[b_idx]
            if b["kind"] != a["kind"] or b_idx in used:
                continue
            # stop at the first bar between them that already ran past the pool
            between = bars[members[-1]["i"] + 1:b["i"]]
            if a["kind"] == 1 and any(x["h"] > a["level"] + tol for x in between):
                break
            if a["kind"] == -1 and any(x["l"] < a["level"] - tol for x in between):
                break
            if abs(b["level"] - a["level"]) <= tol:
                members.append(b)
                used.add(b_idx)
        if len(members) < 2:
            continue
        lv = [m["level"] for m in members]
        edge = max(lv) if a["kind"] == 1 else min(lv)
        p = {"kind": a["kind"], "level": round(sum(lv) / len(lv), 4), "edge": edge, "touches": len(members),
             "first_i": members[0]["i"], "last_i": members[-1]["i"], "swept_at": None}
        for j in range(members[-1]["i"] + 1, len(bars)):
            if (a["kind"] == 1 and bars[j]["h"] > edge) or (a["kind"] == -1 and bars[j]["l"] < edge):
                p["swept_at"] = j
                break
        pools.append(p)
    return pools


def prior_day(bars):
    """The previous New York session's high and low, from intraday bars."""
    days = {}
    for b in bars:
        d = ts_et(b["t"]).date().isoformat()
        x = days.setdefault(d, {"h": b["h"], "l": b["l"]})
        x["h"], x["l"] = max(x["h"], b["h"]), min(x["l"], b["l"])
    keys = sorted(days)
    if len(keys) < 2:
        return None
    d = keys[-2]
    return {"date": d, "high": days[d]["h"], "low": days[d]["l"]}


# ---------------------------------------------------------------- the map

def r2(x):
    return None if x is None else round(x + 0.0, 2)


def stamp(bars, i, interval):
    et = ts_et(bars[i]["t"])
    return et.strftime("%Y-%m-%d") if interval == "1d" else et.strftime("%Y-%m-%d %H:%M")


def analyze(meta, bars, sym, interval="5m", swing=5, tol_pct=0.1, now_utc=None, recent=3):
    if swing < 1 or swing > 50:
        raise SMCError("--swing must be between 1 and 50 bars")
    if not 0 < tol_pct <= 5:
        raise SMCError("--tolerance must be a percent between 0 and 5")
    now_utc = now_utc or parse_now(None)
    bars = closed_bars(bars, interval, now_utc)
    if len(bars) < 2 * swing + 3:
        raise SMCError("only %d closed bar(s) of %s: need at least %d for --swing %d"
                       % (len(bars), sym, 2 * swing + 3, swing))
    last = bars[-1]
    price = last["c"]
    sw = swings(bars, swing)
    trend, events, blocks = structure(bars, sw)
    gaps = fvgs(bars)
    pools = liquidity(bars, sw, tol_pct)
    pd_ = prior_day(bars) if interval != "1d" else None

    def at(i):
        return stamp(bars, i, interval)

    levels = []
    for g in gaps:
        if g["status"] == "filled":
            continue
        levels.append({"type": "fvg", "side": "support" if g["kind"] == 1 else "resistance",
                       "dir": "bullish" if g["kind"] == 1 else "bearish", "top": r2(g["top"]),
                       "bottom": r2(g["bottom"]), "status": g["status"], "since": at(g["i"])})
    for ob in blocks:
        if ob["status"] != "active":
            continue
        levels.append({"type": "order_block", "side": "support" if ob["kind"] == 1 else "resistance",
                       "dir": "bullish" if ob["kind"] == 1 else "bearish", "top": r2(ob["top"]),
                       "bottom": r2(ob["bottom"]), "status": "active", "since": at(ob["i"])})
    for p in pools:
        if p["swept_at"] is not None:
            continue
        name = "equal_highs" if p["kind"] == 1 else "equal_lows"
        levels.append({"type": name, "side": "resistance" if p["kind"] == 1 else "support",
                       "top": r2(p["edge"] if p["kind"] == 1 else p["level"]),
                       "bottom": r2(p["level"] if p["kind"] == 1 else p["edge"]),
                       "touches": p["touches"], "status": "unswept", "since": at(p["first_i"])})
    if pd_:
        levels.append({"type": "prior_day_high", "side": "resistance", "top": r2(pd_["high"]),
                       "bottom": r2(pd_["high"]), "status": "", "since": pd_["date"]})
        levels.append({"type": "prior_day_low", "side": "support", "top": r2(pd_["low"]),
                       "bottom": r2(pd_["low"]), "status": "", "since": pd_["date"]})
    hs = [s for s in sw if s["kind"] == 1]
    ls = [s for s in sw if s["kind"] == -1]
    if hs:
        levels.append({"type": "swing_high", "side": "resistance", "top": r2(hs[-1]["level"]),
                       "bottom": r2(hs[-1]["level"]), "status": "", "since": at(hs[-1]["i"])})
    if ls:
        levels.append({"type": "swing_low", "side": "support", "top": r2(ls[-1]["level"]),
                       "bottom": r2(ls[-1]["level"]), "status": "", "since": at(ls[-1]["i"])})

    # where each level sits against the last close: a zone is support only if all of it is below
    below = [lv for lv in levels if lv["top"] < price]
    above = [lv for lv in levels if lv["bottom"] > price]
    inside = [lv for lv in levels if lv["bottom"] <= price <= lv["top"]]
    for lv in below:
        lv["distance_pct"] = r2(100.0 * (lv["top"] / price - 1))
    for lv in above:
        lv["distance_pct"] = r2(100.0 * (lv["bottom"] / price - 1))
    below.sort(key=lambda lv: -lv["top"])
    above.sort(key=lambda lv: lv["bottom"])

    ev = [{"type": e["type"], "dir": "bullish" if e["dir"] == 1 else "bearish", "level": r2(e["level"]),
           "at": at(e["i"])} for e in events[-recent:]]
    idea = suggest(price, trend, events, below, above)
    return {
        "created_by": "trader-smc",
        "symbol": str(meta.get("symbol") or sym).upper(),
        "interval": interval, "swing": swing, "tolerance_pct": tol_pct,
        "bars": len(bars), "last_bar": at(len(bars) - 1), "price": r2(price),
        "trend": {1: "up", -1: "down", 0: "none yet"}[trend],
        "recent_structure": ev,
        "supports": below[:6], "resistances": above[:6], "inside": inside,
        "counts": {"swings": len(sw), "fvg_open": sum(1 for g in gaps if g["status"] != "filled"),
                   "order_blocks_active": sum(1 for b in blocks if b["status"] == "active"),
                   "liquidity_unswept": sum(1 for p in pools if p["swept_at"] is None)},
        "idea": idea,
        "note": ("Smart-money levels are a way of reading structure, not a proven edge. Test any idea here "
                 "with /trader-timemachine and score it in /trader-journal (tag it \"smc\") before trusting it. "
                 "Not financial advice."),
    }


def suggest(price, trend, events, below, above):
    """A long-side reading for trader-entry and trader-exit. Never an order."""
    if trend != 1:
        why = ("the last break was bearish (%s)" % events[-1]["type"]) if events else "no structure break yet"
        return {"long": False, "why": "%s: SMC traders wait for a bullish CHoCH or BOS before a long" % why}
    sup = next((lv for lv in below if lv["type"] in ("order_block", "fvg", "equal_lows", "swing_low")), None)
    res = next((lv for lv in above), None)
    out = {"long": True, "why": "trend up (last break %s)" % events[-1]["type"]}
    if res:
        out["entry_level"] = res["top"] if res["type"] in ("equal_highs",) else res["bottom"]
        out["entry_from"] = res["type"]
        out["entry_cmd"] = "entry.py check SYMBOL --setup level --level %.2f" % out["entry_level"]
    if sup:
        stop = round(sup["bottom"] - 0.01, 2)
        out["stop"] = stop
        out["stop_from"] = sup["type"]
        out["stop_cmd"] = "exit.py plan --setup level --stop price:%.2f" % stop
        ref = out.get("entry_level", price)
        out["risk_per_share"] = r2(ref - stop)
    if res and sup:
        nxt = above[1] if len(above) > 1 else None
        if nxt:
            out["target"] = nxt["bottom"]
            out["target_from"] = nxt["type"]
            if out["risk_per_share"] and out["risk_per_share"] > 0:
                out["reward_risk"] = r2((nxt["bottom"] - out["entry_level"]) / out["risk_per_share"])
    if out.get("reward_risk") is not None and out["reward_risk"] < 1:
        out["warning"] = ("reward:risk %.2f: the next resistance is closer than the stop, so trader-risk's "
                          "min_reward_risk (1.0 by default) will block it. Skip it or wait for a better spot"
                          % out["reward_risk"])
    return out


# ---------------------------------------------------------------- output

def render(doc):
    out = ["%s  %s bars, swing %d  (%d closed bars, last %s)" % (doc["symbol"], doc["interval"], doc["swing"],
                                                                doc["bars"], doc["last_bar"]),
           "Last close %.2f   trend %s" % (doc["price"], doc["trend"]), ""]
    if doc["recent_structure"]:
        out.append("Structure")
        for e in doc["recent_structure"]:
            out.append("  %-5s %-8s through %.2f at %s" % (e["type"], e["dir"], e["level"], e["at"]))
        out.append("")

    def row(lv):
        zone = ("%.2f" % lv["top"]) if lv["top"] == lv["bottom"] else ("%.2f-%.2f" % (lv["bottom"], lv["top"]))
        extra = lv.get("status") or ""
        if lv.get("touches"):
            extra = "%d touches, %s" % (lv["touches"], extra)
        return "  %-16s %-15s %+6.2f%%  %s  (since %s)" % (
            lv["type"] + (" " + lv["dir"][:4] if lv.get("dir") else ""), zone, lv.get("distance_pct", 0.0),
            extra, lv["since"])

    out.append("Resistance above (nearest first)")
    out += [row(lv) for lv in doc["resistances"]] or ["  none in this data"]
    if doc["inside"]:
        out.append("Price is inside")
        out += ["  %s%s %.2f-%.2f" % (lv["type"], (" " + lv["dir"][:4]) if lv.get("dir") else "",
                                      lv["bottom"], lv["top"]) for lv in doc["inside"]]
    out.append("Support below (nearest first)")
    out += [row(lv) for lv in doc["supports"]] or ["  none in this data"]
    i = doc["idea"]
    out += ["", "Long-side reading"]
    if not i["long"]:
        out.append("  no long: " + i["why"])
    else:
        out.append("  " + i["why"])
        if i.get("entry_level") is not None:
            out.append("  entry   close above %.2f (%s)  ->  %s" % (i["entry_level"], i["entry_from"],
                                                                    i["entry_cmd"].replace("SYMBOL", doc["symbol"])))
        if i.get("stop") is not None:
            out.append("  stop    %.2f, a cent under the %s  ->  %s" % (i["stop"], i["stop_from"], i["stop_cmd"]))
        if i.get("target") is not None:
            out.append("  target  %.2f (%s), reward:risk %s" % (i["target"], i["target_from"],
                                                                 "n/a" if i.get("reward_risk") is None
                                                                 else "%.2f" % i["reward_risk"]))
        if i.get("warning"):
            out.append("  ! " + i["warning"])
    out += ["", doc["note"]]
    return "\n".join(out)


def write_json(path, data):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def cmd_levels(a):
    sym = a.symbol.upper()
    if not re.match(r"^[A-Z0-9.\-^=]{1,15}$", sym):
        raise SMCError("%r does not look like a ticker" % a.symbol)
    if a.interval not in INTERVALS:
        raise SMCError("--interval is one of %s" % ", ".join(INTERVALS))
    now = parse_now(a.at)
    if a.offline:
        text = read_text(a.offline)
    else:
        rng = a.range or DEFAULT_RANGE[a.interval]
        text = yahoo_get("/v8/finance/chart/%s?range=%s&interval=%s" % (sym.replace(".", "-"), rng, a.interval))
    meta, bars = parse_chart(text, sym)
    msym = str(meta.get("symbol") or "").upper()
    if msym and msym != sym.replace(".", "-"):
        raise SMCError("the data is for %s, not %s" % (msym, sym))
    gran = meta.get("dataGranularity")
    if gran and gran != a.interval and not (gran == "60m" and a.interval == "1h"):
        raise SMCError("the data has %s bars, not %s: pass --interval %s" % (gran, a.interval, gran))
    doc = analyze(meta, bars, sym, a.interval, a.swing, a.tolerance, now)
    if a.write:
        write_json(a.write, doc)
    return json.dumps(doc, indent=2) if a.json else render(doc)


def build_parser():
    ap = argparse.ArgumentParser(description="Smart-money levels: structure, FVGs, order blocks, liquidity.")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("levels", help="map the levels for one ticker")
    p.add_argument("symbol")
    p.add_argument("--interval", default="5m", help="1m, 5m (default), 15m, 30m, 60m, 1d")
    p.add_argument("--range", help="Yahoo range: 5d, 1mo, 60d, 1y ... (default by interval)")
    p.add_argument("--swing", type=int, default=5, help="bars on each side of a swing (default 5)")
    p.add_argument("--tolerance", type=float, default=0.1,
                   help="percent apart that still counts as equal highs / lows (default 0.1)")
    p.add_argument("--at", help="as of this New York time (only bars closed by then)")
    p.add_argument("--offline", help="a saved Yahoo chart JSON (.json or .json.gz) instead of the network")
    p.add_argument("--json", action="store_true")
    p.add_argument("--write", nargs="?", const="trader/smc.json", metavar="PATH",
                   help="save the map (default trader/smc.json)")
    p.set_defaults(fn=cmd_levels)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    try:
        print(a.fn(a))
    except SMCError as e:
        print("smc: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

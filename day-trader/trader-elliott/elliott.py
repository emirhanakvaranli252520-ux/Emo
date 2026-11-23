#!/usr/bin/env python3
"""Elliott wave counts for trader-elliott. Standard library only. It never places an order.

Elliott wave analysis is famously subjective: two analysts rarely agree on a
count. This tool does not pretend otherwise. It:

  1. finds swings with an ATR zigzag (a swing is confirmed once price comes
     back k x ATR from the extreme; the leg in progress is provisional)
  2. tries every count that ends at the current leg: wave 2, 3, 4 or 5 of an
     impulse, an impulse complete (correction starting), wave B or C of a
     correction, on both sides
  3. throws out any count that breaks a hard rule (wave 2 beyond the start of
     wave 1, wave 3 the shortest, wave 4 into wave 1's territory, a flat's B
     beyond 138 % of A ...) and scores the rest on the guidelines (Fibonacci
     proportions, alternation, volume)
  4. weighs the surviving counts: when they agree on the next direction it
     gives a lean with an invalidation level and a target; when they do not,
     it says Elliott is undecided here
  5. with `evaluate`, replays that process bar by bar on the past (only data
     known at each point) and compares its calls with the base rate

    python3 elliott.py count BTCUSDT --source binance                 # H1, three degrees
    python3 elliott.py count NQ=F --degree 4
    python3 elliott.py count ES=F --at "2026-11-20 18:00"             # Turkey time
    python3 elliott.py evaluate BTCUSDT --source binance --horizon 48
    python3 elliott.py count TSLA --offline chart.json.gz --interval 5m --resample 1h --json

It reuses trader-structure's data loading (Yahoo, Binance, offline files,
Turkey time), so both skills must sit side by side.
"""

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_ST_PATH = os.path.join(HERE, "..", "trader-structure", "structure.py")


def _load_structure():
    if not os.path.exists(_ST_PATH):
        raise SystemExit("elliott: needs trader-structure next to it (%s)" % os.path.normpath(_ST_PATH))
    spec = importlib.util.spec_from_file_location("trader_structure_for_elliott", _ST_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


st = _load_structure()
StructureError = st.StructureError
r2 = st.r2
tr_time = st.tr_time

DEGREES = (2.0, 4.0, 8.0)          # zigzag sizes in ATR(14): minor, intermediate, larger swings
RR_MIN, RR_MAX = 1.5, 3.5          # the reward:risk band the user trades


class ElliottError(Exception):
    pass


# ---------------------------------------------------------------- swings

def atr_series(bars, n=14):
    out, trs = [], []
    for i, b in enumerate(bars):
        tr = b["h"] - b["l"] if i == 0 else max(b["h"] - b["l"], abs(b["h"] - bars[i - 1]["c"]),
                                                  abs(b["l"] - bars[i - 1]["c"]))
        trs.append(tr)
        w = trs[-n:]
        out.append(sum(w) / len(w))
    return out


def zigzag(bars, mult, atr=None):
    """Alternating swing points. Each confirmed pivot: {i, kind (+1 high, -1 low), price, known}.
    `known` is the bar where price came back mult x ATR from it. Returns (pivots, provisional), the
    provisional point being the extreme of the leg in progress."""
    atr = atr or atr_series(bars)
    piv = []
    if len(bars) < 2:
        return piv, None
    direction, hi_i, lo_i, ext = 0, 0, 0, 0
    for i in range(1, len(bars)):
        b, thr = bars[i], mult * atr[i]
        if direction == 0:
            if b["h"] > bars[hi_i]["h"]:
                hi_i = i
            if b["l"] < bars[lo_i]["l"]:
                lo_i = i
            if hi_i < i and bars[hi_i]["h"] - b["l"] >= thr:
                piv.append({"i": hi_i, "kind": 1, "price": bars[hi_i]["h"], "known": i})
                direction = -1
                ext = min(range(hi_i + 1, i + 1), key=lambda k: (bars[k]["l"], k))
            elif lo_i < i and b["h"] - bars[lo_i]["l"] >= thr:
                piv.append({"i": lo_i, "kind": -1, "price": bars[lo_i]["l"], "known": i})
                direction = 1
                ext = max(range(lo_i + 1, i + 1), key=lambda k: (bars[k]["h"], -k))
            continue
        if direction == 1:
            if b["h"] > bars[ext]["h"]:
                ext = i
            elif bars[ext]["h"] - b["l"] >= thr:
                piv.append({"i": ext, "kind": 1, "price": bars[ext]["h"], "known": i})
                direction = -1
                ext = min(range(ext + 1, i + 1), key=lambda k: (bars[k]["l"], k))
        else:
            if b["l"] < bars[ext]["l"]:
                ext = i
            elif b["h"] - bars[ext]["l"] >= thr:
                piv.append({"i": ext, "kind": -1, "price": bars[ext]["l"], "known": i})
                direction = 1
                ext = max(range(ext + 1, i + 1), key=lambda k: (bars[k]["h"], -k))
    prov = None
    if direction != 0:
        prov = {"i": ext, "kind": direction, "price": bars[ext]["h"] if direction == 1 else bars[ext]["l"],
                "known": None, "provisional": True}
    return piv, prov


# ---------------------------------------------------------------- counts

def _in(x, lo, hi):
    return lo <= x <= hi


def _vol(bars, a, b):
    seg = bars[a + 1:b + 1]
    return sum(x.get("v", 0) for x in seg) / len(seg) if seg else 0.0


def hypotheses(pts, bars):
    """Every count that ends at the last point (the leg in progress). pts: [{i, price}], alternating.
    Each count is checked in 'signed' space, where its first leg points up (v = s x price)."""
    out = []
    has_vol = sum(1 for b in bars if b.get("v")) > len(bars) // 2

    def take(k):
        if len(pts) < k:
            return None
        P = pts[-k:]
        s = 1 if P[1]["price"] > P[0]["price"] else -1
        v = [s * p["price"] for p in P]
        L = [abs(v[j + 1] - v[j]) for j in range(k - 1)]
        if min(L) <= 0:
            return None
        return P, s, v, L

    def add(name, k, P, s, lean, invalid, target, checks, extra=None):
        met = [c for c in checks if c[1] is not None]
        score = round(100.0 * sum(1 for c in met if c[1]) / len(met)) if met else 50
        out.append({"count": name, "points": [{"at": tr_time(bars[p["i"]]["t"]), "price": r2(p["price"]),
                                               "i": p["i"]} for p in P],
                    "lean": "up" if lean * s > 0 else "down", "invalidation": r2(s * invalid),
                    "target": r2(s * target) if target is not None else None, "score": score, "legs": k - 1,
                    "guidelines": [{"check": c[0], "ok": c[1]} for c in met], "side": s, **(extra or {})})

    # wave 2 in progress (or wave B: same shape, same next direction)
    t = take(3)
    if t:
        P, s, v, L = t
        if v[2] < v[1] and v[2] > v[0]:
            r = L[1] / L[0]
            add("wave 2 (next: wave 3) / wave B (next: wave C)", 3, P, s, 1, v[0], v[2] + 1.618 * L[0],
                [("wave 2 retraces 38.2-88.6 % of wave 1", _in(r, 0.382, 0.886))],
                {"retrace": r2(r)})

    # wave 3 in progress, or wave C of a zigzag / flat (same direction)
    t = take(4)
    if t:
        P, s, v, L = t
        r = L[1] / L[0]
        if v[3] > v[2] and v[2] > v[0]:
            tgt = _next_ext(v[2], L[0], v[3], (1.618, 2.618, 4.236))
            add("wave 3 (impulse in progress)", 4, P, s, 1, v[2], tgt,
                [("wave 2 retraces 38.2-88.6 % of wave 1", _in(r, 0.382, 0.886)),
                 ("wave 3 already beyond the end of wave 1", v[3] > v[1])], {"retrace": r2(r)})
        if v[3] > v[2] and r < 0.9:
            add("wave C of a zigzag", 4, P, s, 1, v[2], _next_ext(v[2], L[0], v[3]),
                [("B retraces 38.2-88.6 % of A", _in(r, 0.382, 0.886))], {"retrace": r2(r)})
        if v[3] > v[2] and _in(r, 0.9, 1.382):
            add("wave C of a flat", 4, P, s, 1, v[2], _next_ext(v[2], L[0], v[3]),
                [("B retraces 90-138.2 % of A", True), ("regular flat (B 90-105 %)", r <= 1.05)],
                {"retrace": r2(r)})

    # wave 4 in progress: next is wave 5
    t = take(5)
    if t:
        P, s, v, L = t
        if v[2] > v[0] and v[3] > v[1] and v[4] < v[3] and v[4] > v[1] and L[2] > 0:
            r2_, r4 = L[1] / L[0], L[3] / L[2]
            w5 = min(v[4] + L[0], v[4] + 0.618 * (v[3] - v[0]))
            add("wave 4 (next: wave 5)", 5, P, s, 1, v[1], w5,
                [("wave 2 retraces 38.2-88.6 % of wave 1", _in(r2_, 0.382, 0.886)),
                 ("wave 3 is 1.382-2.8 x wave 1", _in(L[2] / L[0], 1.382, 2.8)),
                 ("wave 4 retraces 23.6-50 % of wave 3", _in(r4, 0.236, 0.5)),
                 ("alternation: waves 2 and 4 differ in depth or time",
                  abs(r2_ - r4) >= 0.15 or _time_ratio(P, 1, 3) >= 1.5),
                 ("volume higher in wave 3 than wave 1", (_vol(bars, P[2]["i"], P[3]["i"]) >
                                                          _vol(bars, P[0]["i"], P[1]["i"])) if has_vol else None)],
                {"retrace": r2(r4)})

    # wave 5 in progress: late in the trend
    t = take(6)
    if t:
        P, s, v, L = t
        ok = v[2] > v[0] and v[3] > v[1] and v[4] > v[1] and v[5] > v[4]
        if ok and L[2] < L[0] and L[4] > L[2]:
            ok = False                           # wave 3 would become the shortest
        if ok:
            r2_, r4 = L[1] / L[0], L[3] / L[2]
            cap = v[4] + L[2] if L[2] < L[0] else None
            w5 = min(v[4] + L[0], v[4] + 0.618 * (v[3] - v[0]))
            add("wave 5 (impulse nearly done)", 6, P, s, 1, v[4], w5 if cap is None else min(w5, cap),
                [("wave 2 retraces 38.2-88.6 % of wave 1", _in(r2_, 0.382, 0.886)),
                 ("wave 3 is 1.382-2.8 x wave 1", _in(L[2] / L[0], 1.382, 2.8)),
                 ("wave 4 retraces 23.6-50 % of wave 3", _in(r4, 0.236, 0.5)),
                 ("alternation: waves 2 and 4 differ in depth or time",
                  abs(r2_ - r4) >= 0.15 or _time_ratio(P, 1, 3) >= 1.5)],
                {"late": True, "cap": r2(s * cap) if cap is not None else None})

    # impulse complete, correction under way (wave A): next move against the impulse
    t = take(7)
    if t:
        P, s, v, L = t
        ok = (v[2] > v[0] and v[3] > v[1] and v[4] > v[1] and v[5] > v[3] and v[6] < v[5]
              and not (L[2] < L[0] and L[2] < L[4]))
        if ok:
            r2_, r4 = L[1] / L[0], L[3] / L[2]
            whole = v[5] - v[0]
            w5_ok = _in(L[4] / L[0], 0.618, 1.618) or abs(L[4] - 0.618 * (v[3] - v[0])) <= 0.15 * L[4]
            add("impulse complete (next: correction, wave A/B/C)", 7, P, s, -1, v[5], max(v[4], v[5] - 0.5 * whole),
                [("wave 2 retraces 38.2-88.6 % of wave 1", _in(r2_, 0.382, 0.886)),
                 ("wave 3 is 1.382-2.8 x wave 1", _in(L[2] / L[0], 1.382, 2.8)),
                 ("wave 4 retraces 23.6-50 % of wave 3", _in(r4, 0.236, 0.5)),
                 ("wave 5 is 0.618-1.618 x wave 1, or 0.618 x waves 1-3", w5_ok),
                 ("alternation: waves 2 and 4 differ in depth or time",
                  abs(r2_ - r4) >= 0.15 or _time_ratio(P, 1, 3) >= 1.5)])
        # an ending diagonal: waves 1-4 overlap but the wedge contracts
        if (v[2] > v[0] and v[3] > v[1] and v[5] > v[3] and v[6] < v[5] and v[4] <= v[1] and v[4] > v[2]
                and L[2] < L[0] and L[4] < L[2] and L[3] < L[1]):
            add("ending diagonal complete (next: sharp reversal)", 7, P, s, -1, v[5], v[0],
                [("contracting wedge", True)])
    return out


def _next_ext(base, leg, reached, ratios=(1.0, 1.618, 2.618)):
    """The first extension of `leg` from `base` that price has not reached yet (signed space)."""
    for r in ratios:
        if base + r * leg > reached:
            return base + r * leg
    return None


def _time_ratio(P, a, b):
    """Bars in leg a vs leg b, the bigger over the smaller."""
    ta = P[a + 1]["i"] - P[a]["i"]
    tb = P[b + 1]["i"] - P[b]["i"]
    if min(ta, tb) <= 0:
        return 1.0
    return max(ta, tb) / float(min(ta, tb))


def consensus(hyps, price, rr_min=RR_MIN, rr_max=RR_MAX):
    """Weigh the counts by score. A lean needs 65 % of the weight on one side and a best count scoring 60+."""
    for h in hyps:
        inv, tgt = h["invalidation"], h["target"]
        up = h["lean"] == "up"
        h["rr_from_here"] = None
        if tgt is not None and ((up and inv < price < tgt) or (not up and tgt < price < inv)):
            h["rr_from_here"] = r2(abs(tgt - price) / abs(price - inv))
        rr = h["rr_from_here"]
        h["rr_band"] = None if rr is None else ("in band" if rr_min <= rr <= rr_max else
                                                "under %.1f" % rr_min if rr < rr_min else "over %.1f" % rr_max)
    if not hyps:
        return {"lean": "none", "why": "no count fits the recent swings", "up_weight": None}
    w_up = sum(h["score"] for h in hyps if h["lean"] == "up")
    w_dn = sum(h["score"] for h in hyps if h["lean"] == "down")
    tot = w_up + w_dn
    best = max(hyps, key=lambda h: (h["score"], h["legs"]))
    share = (w_up / tot) if tot else 0.5
    if tot and max(share, 1 - share) >= 0.65 and best["score"] >= 60:
        lean = "up" if share >= 0.5 else "down"
        agree = [h for h in hyps if h["lean"] == lean]
        inv = min(h["invalidation"] for h in agree) if lean == "up" else max(h["invalidation"] for h in agree)
        return {"lean": lean, "up_weight": r2(100 * share), "best": best["count"],
                "invalidation": inv, "why": "%d of %d counts (%.0f %% of the weight) point %s"
                % (len(agree), len(hyps), 100 * max(share, 1 - share), lean)}
    if tot and max(share, 1 - share) >= 0.65:
        why = ("only weak counts fit (the best scores %d of 100 on the guidelines): Elliott does not settle the "
               "direction here" % best["score"])
    else:
        why = ("the counts that fit disagree (up %.0f %% / down %.0f %% of the weight): Elliott does not settle "
               "the direction here" % (100 * share, 100 * (1 - share)))
    return {"lean": "undecided", "up_weight": r2(100 * share) if tot else None, "best": best["count"], "why": why}


def count_at(bars, mult, atr=None, upto=None):
    """The counts for the swings known at bar `upto` (default: the last bar)."""
    seg = bars if upto is None else bars[:upto + 1]
    piv, prov = zigzag(seg, mult, atr[:len(seg)] if atr else None)
    pts = [{"i": p["i"], "price": p["price"]} for p in piv]
    if prov:
        pts.append({"i": prov["i"], "price": prov["price"]})
    hyps = hypotheses(pts[-8:], seg)
    return piv, prov, hyps


def analyze(sym, bars, interval, now, degrees=DEGREES, resampled=False, rr_min=RR_MIN, rr_max=RR_MAX):
    bars = st.closed_only(bars, interval, now, resampled)
    if len(bars) < 60:
        raise ElliottError("only %d closed bar(s) of %s: need at least 60" % (len(bars), sym))
    atr = atr_series(bars)
    price = bars[-1]["c"]
    out = []
    for m in degrees:
        piv, prov, hyps = count_at(bars, m, atr)
        hyps.sort(key=lambda h: (-h["score"], -h["legs"]))
        cons = consensus(hyps, price, rr_min, rr_max)
        for h in hyps:
            for p in h["points"]:
                p.pop("i", None)
            h.pop("side", None)
        out.append({"degree_atr": m, "swings": len(piv),
                    "last_swings": [{"at": tr_time(bars[p["i"]]["t"]), "type": "high" if p["kind"] == 1 else "low",
                                     "price": r2(p["price"])} for p in piv[-6:]],
                    "leg_in_progress": prov and {"from": tr_time(bars[piv[-1]["i"]]["t"]) if piv else None,
                                                 "extreme": r2(prov["price"]), "at": tr_time(bars[prov["i"]]["t"]),
                                                 "dir": "up" if prov["kind"] == 1 else "down"},
                    "counts": hyps[:6], "consensus": cons})
    leans = [d["consensus"]["lean"] for d in out]
    decided = [x for x in leans if x in ("up", "down")]
    overall = ("up" if decided and all(x == "up" for x in decided) else
               "down" if decided and all(x == "down" for x in decided) else "undecided")
    if decided and len(decided) < len(leans) and overall != "undecided":
        overall_note = "%s on %d of %d degrees, undecided on the rest" % (overall, len(decided), len(leans))
    elif overall == "undecided" and decided:
        overall_note = "degrees disagree (%s)" % ", ".join("%gx ATR %s" % (d["degree_atr"], d["consensus"]["lean"])
                                                         for d in out)
    elif overall == "undecided":
        overall_note = "no degree gives a clear lean"
    else:
        overall_note = "every degree leans %s" % overall
    return {"created_by": "trader-elliott", "symbol": sym, "interval": interval, "bars": len(bars),
            "last_bar": tr_time(bars[-1]["t"]), "price": r2(price), "timezone": "Turkey (UTC+3)",
            "rr_band": [rr_min, rr_max], "degrees": out, "overall": overall, "overall_note": overall_note,
            "note": ("Elliott counts are subjective and the evidence that they predict is weak; treat the lean "
                     "as a tie-breaker only when your own structure is undecided, never as a signal, and never "
                     "against your stop. Not financial advice.")}


def evaluate(sym, bars, interval, now, mult=4.0, horizon=48, resampled=False):
    """Replay: at every bar where a new swing gets confirmed, count with only the data known then; if the
    counts lean, record the call. Then check (a) the close `horizon` bars later against the base rate and
    (b) whether the target or the invalidation came first."""
    bars = st.closed_only(bars, interval, now, resampled)
    if len(bars) < 60 + horizon:
        raise ElliottError("need at least %d closed bars to evaluate with --horizon %d" % (60 + horizon, horizon))
    atr = atr_series(bars)
    piv_all, _ = zigzag(bars, mult, atr)
    events = sorted(set(p["known"] for p in piv_all if p["known"] is not None))
    n = len(bars)
    calls = []
    for t in events:
        if t < 60 or t + horizon >= n:
            continue
        _, _, hyps = count_at(bars, mult, atr, upto=t)
        cons = consensus(hyps, bars[t]["c"])
        if cons["lean"] not in ("up", "down"):
            calls.append({"t": t, "lean": cons["lean"]})
            continue
        agree = [h for h in hyps if h["lean"] == cons["lean"]]
        best = max(agree, key=lambda h: h["score"])
        up = cons["lean"] == "up"
        moved_up = bars[t + horizon]["c"] > bars[t]["c"]
        first = None
        tgt, inv = best["target"], cons["invalidation"]
        for j in range(t + 1, t + horizon + 1):
            hit_inv = (bars[j]["l"] <= inv) if up else (bars[j]["h"] >= inv)
            hit_tgt = tgt is not None and ((bars[j]["h"] >= tgt) if up else (bars[j]["l"] <= tgt))
            if hit_inv:
                first = "invalidation"
                break
            if hit_tgt:
                first = "target"
                break
        calls.append({"t": t, "lean": cons["lean"], "right": moved_up == up, "first": first or "neither",
                      "count": best["count"]})
    leaned = [c for c in calls if c["lean"] in ("up", "down")]
    ups = [c for c in leaned if c["lean"] == "up"]
    dns = [c for c in leaned if c["lean"] == "down"]
    base_up = sum(1 for t in range(60, n - horizon) if bars[t + horizon]["c"] > bars[t]["c"]) / float(n - horizon - 60)

    def pct(a, b):
        return r2(100.0 * a / b) if b else None
    return {"created_by": "trader-elliott", "mode": "evaluate", "symbol": sym, "interval": interval,
            "degree_atr": mult, "horizon_bars": horizon, "bars": n,
            "from": tr_time(bars[0]["t"]), "to": tr_time(bars[-1]["t"]),
            "swing_events": len(calls), "leaned": len(leaned), "undecided": len(calls) - len(leaned),
            "up_calls": len(ups), "up_right_pct": pct(sum(1 for c in ups if c["right"]), len(ups)),
            "base_up_pct": r2(100 * base_up),
            "down_calls": len(dns), "down_right_pct": pct(sum(1 for c in dns if c["right"]), len(dns)),
            "base_down_pct": r2(100 * (1 - base_up)),
            "target_first": sum(1 for c in leaned if c["first"] == "target"),
            "invalidation_first": sum(1 for c in leaned if c["first"] == "invalidation"),
            "neither": sum(1 for c in leaned if c["first"] == "neither"),
            "note": ("Calls use only the swings known at the time. Right = the close %d bars later was on the "
                     "called side. Compare each rate with the base rate: a call that is right less often than "
                     "the base rate adds nothing. A few dozen calls prove nothing either way." % horizon)}


# ---------------------------------------------------------------- output

def render(doc):
    out = ["%s  %s  Elliott counts, last bar %s (Turkey time), last close %.2f" % (
        doc["symbol"], doc["interval"], doc["last_bar"], doc["price"]),
        "Overall: %s (%s)" % (doc["overall"].upper(), doc["overall_note"]),
        "R:R band %.1f-%.1f" % tuple(doc["rr_band"]), ""]
    for d in doc["degrees"]:
        c = d["consensus"]
        leg = d["leg_in_progress"]
        out.append("Degree %gx ATR: %d swings%s" % (
            d["degree_atr"], d["swings"],
            ("; leg in progress %s to %.2f (%s)" % (leg["dir"], leg["extreme"], leg["at"][5:])) if leg else ""))
        line = "  lean %s: %s" % (c["lean"], c["why"])
        if c.get("invalidation") is not None:
            line += "; invalidation %.2f" % c["invalidation"]
        out.append(line)
        for h in d["counts"][:4]:
            pts = " ".join("%.2f" % p["price"] for p in h["points"])
            rr = h.get("rr_from_here")
            out.append("    %3d  %-48s lean %-4s inval %s target %s R:R %s%s" % (
                h["score"], h["count"], h["lean"], h["invalidation"],
                "n/a" if h["target"] is None else h["target"], "n/a" if rr is None else "%.2f" % rr,
                "" if h.get("rr_band") in (None, "in band") else " (%s)" % h["rr_band"]))
            out.append("         swings %s" % pts)
            bad = [g["check"] for g in h["guidelines"] if not g["ok"]]
            if bad:
                out.append("         misses: " + "; ".join(bad))
        if not d["counts"]:
            out.append("    no count fits")
        out.append("")
    out.append(doc["note"])
    return "\n".join(out)


def render_eval(d):
    out = ["%s  %s  Elliott replay, %gx ATR, %d-bar horizon, %s to %s" % (
        d["symbol"], d["interval"], d["degree_atr"], d["horizon_bars"], d["from"], d["to"]),
        "Swing events %d: leaned %d, undecided %d" % (d["swing_events"], d["leaned"], d["undecided"])]
    if d["up_calls"]:
        out.append("  up calls   %3d: right %s %% (base rate up %s %%)" % (d["up_calls"], d["up_right_pct"], d["base_up_pct"]))
    if d["down_calls"]:
        out.append("  down calls %3d: right %s %% (base rate down %s %%)" % (d["down_calls"], d["down_right_pct"],
                                                                         d["base_down_pct"]))
    if d["leaned"]:
        out.append("  target first %d, invalidation first %d, neither in the horizon %d"
                   % (d["target_first"], d["invalidation_first"], d["neither"]))
    out += ["", d["note"]]
    return "\n".join(out)


def build_parser():
    ap = argparse.ArgumentParser(description="Elliott wave counts with rules, guidelines, alternates and a replay.")
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("symbol")
        p.add_argument("--source", choices=["yahoo", "binance"], default="yahoo")
        p.add_argument("--interval", default="1h")
        p.add_argument("--range")
        p.add_argument("--fetch-interval")
        p.add_argument("--limit", type=int)
        p.add_argument("--resample")
        p.add_argument("--at", help="as of this Turkey time")
        p.add_argument("--offline")
        p.add_argument("--json", action="store_true")
        p.set_defaults(range_window=24)

    p = sub.add_parser("count", help="the counts that fit now, their lean, invalidation and target")
    common(p)
    p.add_argument("--degree", type=float, action="append",
                   help="zigzag size in ATR(14), repeatable (default 2, 4 and 8)")
    p.add_argument("--rr-min", type=float, default=RR_MIN)
    p.add_argument("--rr-max", type=float, default=RR_MAX)
    p.add_argument("--write", nargs="?", const="trader/elliott.json", metavar="PATH")
    p.set_defaults(fn=cmd_count)

    p = sub.add_parser("evaluate", help="replay the counts on the past and compare with the base rate")
    common(p)
    p.add_argument("--degree", type=float, default=4.0)
    p.add_argument("--horizon", type=int, default=48, help="bars after a call to judge it (default 48)")
    p.set_defaults(fn=cmd_evaluate)
    return ap


def cmd_count(a):
    sym, bars, interval, now, resampled = st.load(a)
    degs = tuple(a.degree) if a.degree else DEGREES
    if any(not 0.5 <= d <= 30 for d in degs):
        raise ElliottError("--degree must be between 0.5 and 30 ATR")
    if not 0 < a.rr_min < a.rr_max:
        raise ElliottError("--rr-min must be positive and under --rr-max")
    doc = analyze(sym, bars, interval, now, degs, resampled, a.rr_min, a.rr_max)
    if a.write:
        st.write_json(a.write, doc)
    return json.dumps(doc, indent=2) if a.json else render(doc)


def cmd_evaluate(a):
    sym, bars, interval, now, resampled = st.load(a)
    if not 5 <= a.horizon <= 500:
        raise ElliottError("--horizon must be between 5 and 500 bars")
    doc = evaluate(sym, bars, interval, now, a.degree, a.horizon, resampled)
    return json.dumps(doc, indent=2) if a.json else render_eval(doc)


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    try:
        print(a.fn(a))
    except (ElliottError, StructureError) as e:
        print("elliott: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

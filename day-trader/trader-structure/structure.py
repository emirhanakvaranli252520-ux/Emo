#!/usr/bin/env python3
"""Advanced market structure for trader-structure. Standard library only. It never places an order.

Classifies swing points in three tiers, both sides, on any market that has
bars (US index futures, crypto majors, stocks, BIST):

  STH / STL   short-term high / low: a high above the highs of the bars
              right before and after it (a low below both lows)
  ITH / ITL   intermediate-term: an STH with a LOWER STH on each side
              (an STL with a HIGHER STL on each side)
  LTH / LTL   long-term: an ITH with a lower ITH on each side
              (an ITL with a higher ITL on each side)

Nothing looks ahead. Each point carries the bar at which it became knowable:
an STH when the next bar closes, an ITH when the next STH (lower) is
confirmed, an LTH when the next ITH (lower) is confirmed.

Then it scans for the sequence:

  bullish   an LTL, then a HIGHER ITL after it, then a bullish fair value gap
            left by the move up from that ITL. Entry zone: the FVG.
            Invalid once a bar closes under the ITL.
  bearish   an LTH, then a LOWER ITH, then a bearish FVG left by the move
            down. Invalid once a bar closes over the ITH.

    python3 structure.py scan BTCUSDT --source binance          # H1, last ~30 days
    python3 structure.py scan NQ=F                              # Yahoo, H1, last 60 days
    python3 structure.py scan XU100.IS --interval 1d --range 2y
    python3 structure.py scan BTCUSDT --source binance --at "2026-11-20 18:00"   # Turkey time
    python3 structure.py scan TSLA --offline chart.json.gz --resample 1h --json --write

Times are shown in Turkey time (UTC+3, no daylight saving) and --at is read
as Turkey time unless it ends in Z or an offset.
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
EPOCH = datetime.datetime(1970, 1, 1)
TR = datetime.timedelta(hours=3)                       # Turkey: UTC+3 all year
SECONDS = {"5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "60m": 3600, "4h": 14400, "1d": 86400}
YAHOO_RANGE = {"5m": "60d", "15m": "60d", "30m": "60d", "1h": "60d", "60m": "60d", "1d": "2y"}
BINANCE_INTERVAL = {"5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "60m": "1h", "4h": "4h", "1d": "1d"}


class StructureError(Exception):
    pass


# ---------------------------------------------------------------- time

def parse_at(text):
    """-> naive UTC. Without an offset the time is Turkey time."""
    if not text:
        return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0, tzinfo=None)
    t = text.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(t)
    except ValueError:
        raise StructureError("--at wants a time like \"2026-11-20 18:00\" (Turkey) or ...Z (UTC)")
    if dt.tzinfo is None:
        return dt - TR
    return (dt - dt.utcoffset()).replace(tzinfo=None)


def tr_time(ts):
    return (EPOCH + datetime.timedelta(seconds=int(ts)) + TR).strftime("%Y-%m-%d %H:%M")


def epoch(dt):
    return int((dt - EPOCH).total_seconds())


# ---------------------------------------------------------------- data

def http_get(url):
    last = "no answer"
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
                time.sleep(5)
                continue
            break
        except (urllib.error.URLError, OSError) as e:
            last = "network error: %s" % (getattr(e, "reason", e),)
            break
    raise StructureError("%s did not answer (%s)" % (url.split("?")[0], last))


def binance_pages(sym, interval, want, end_ms=None):
    """Binance gives 1000 klines a request: walk back page by page until `want` bars, oldest first."""
    rows, end = [], end_ms
    while len(rows) < want:
        n = min(1000, want - len(rows))
        url = "https://api.binance.com/api/v3/klines?symbol=%s&interval=%s&limit=%d" % (sym, interval, n)
        if end is not None:
            url += "&endTime=%d" % end
        page = json.loads(http_get(url))
        if not isinstance(page, list):
            raise StructureError("Binance answered: %s" % (page.get("msg") if isinstance(page, dict) else page))
        if not page:
            break
        rows = page + rows
        end = int(page[0][0]) - 1
        if len(page) < n:
            break
    return json.dumps(rows)


def read_text(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return fh.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def parse_bars(text, sym):
    """Yahoo chart JSON or Binance klines JSON -> (symbol, granularity or None, bars)."""
    try:
        data = json.loads(text)
    except ValueError:
        raise StructureError("the data for %s is not JSON" % sym)
    if isinstance(data, list):                                  # Binance klines
        bars = []
        for k in data:
            try:
                bars.append({"t": int(k[0]) // 1000, "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
                             "c": float(k[4]), "v": float(k[5])})
            except (TypeError, ValueError, IndexError):
                raise StructureError("unexpected Binance kline row: %r" % (k,))
        return sym, None, bars
    try:
        res = data["chart"]["result"]
    except (KeyError, TypeError):
        raise StructureError("the data for %s is neither Yahoo chart JSON nor Binance klines" % sym)
    if not res:
        err = (data.get("chart") or {}).get("error") or {}
        raise StructureError("no data for %s: %s" % (sym, err.get("description") or "unknown symbol"))
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
                     "l": float(c if lo is None else lo), "c": float(c), "v": float(at("volume", i) or 0)})
    return str(meta.get("symbol") or sym).upper(), meta.get("dataGranularity"), bars


def resample(bars, interval):
    """Group bars into interval buckets on the UTC clock (1h buckets start on the hour).
    A bucket's time is its first bar's time."""
    step = SECONDS[interval]
    out, cur, key = [], None, None
    for b in bars:
        k = b["t"] // step
        if k != key:
            if cur:
                out.append(cur)
            cur, key = dict(b), k
        else:
            cur["h"], cur["l"] = max(cur["h"], b["h"]), min(cur["l"], b["l"])
            cur["c"] = b["c"]
            cur["v"] = cur.get("v", 0) + b.get("v", 0)
            cur["last_t"] = b["t"]
    if cur:
        out.append(cur)
    return out


def closed_only(bars, interval, now_utc, resampled=False):
    """Drop bars that had not closed by now (a forming bar would move every point).
    A resampled bar is closed when its whole bucket has passed."""
    cut = epoch(now_utc)
    step = SECONDS[interval]
    if resampled:
        return [b for b in bars if (b["t"] // step + 1) * step <= cut]
    return [b for b in bars if b["t"] + step <= cut]


# ---------------------------------------------------------------- the three tiers

def short_term(bars):
    """STH / STL: three-bar pivots. Known when the bar after closes."""
    highs, lows = [], []
    for i in range(1, len(bars) - 1):
        a, b, c = bars[i - 1], bars[i], bars[i + 1]
        if b["h"] > a["h"] and b["h"] > c["h"]:
            highs.append({"i": i, "level": b["h"], "known": i + 1})
        if b["l"] < a["l"] and b["l"] < c["l"]:
            lows.append({"i": i, "level": b["l"], "known": i + 1})
    return highs, lows


def promote(points, high):
    """One tier up: a point whose neighbours on both sides (in its own tier)
    are lower (for highs) or higher (for lows). Known when the right
    neighbour is known."""
    out = []
    for k in range(1, len(points) - 1):
        p, left, right = points[k], points[k - 1], points[k + 1]
        ok = (left["level"] < p["level"] and right["level"] < p["level"]) if high else \
             (left["level"] > p["level"] and right["level"] > p["level"])
        if ok:
            out.append({"i": p["i"], "level": p["level"], "known": max(p["known"], right["known"])})
    return out


def tiers(bars):
    sth, stl = short_term(bars)
    ith, itl = promote(sth, True), promote(stl, False)
    lth, ltl = promote(ith, True), promote(itl, False)
    return {"STH": sth, "STL": stl, "ITH": ith, "ITL": itl, "LTH": lth, "LTL": ltl}


def fvgs(bars):
    out = []
    for i in range(1, len(bars) - 1):
        a, b, c = bars[i - 1], bars[i], bars[i + 1]
        if b["c"] > b["o"] and a["h"] < c["l"]:
            out.append({"i": i, "dir": 1, "top": c["l"], "bottom": a["h"], "known": i + 1})
        elif b["c"] < b["o"] and a["l"] > c["h"]:
            out.append({"i": i, "dir": -1, "top": a["l"], "bottom": c["h"], "known": i + 1})
    return out


# ---------------------------------------------------------------- the sequence

def r2(x):
    return None if x is None else round(x + 0.0, 2)


def first(seq, pred):
    for x in seq:
        if pred(x):
            return x
    return None


def scan_setups(bars, t, gaps, window=24, min_gap_pct=0.0):
    """LTL -> higher ITL -> bullish FVG (and the bearish mirror). One setup per anchor ITL/ITH."""
    out = []
    n = len(bars)
    for side in (1, -1):
        anchors = t["LTL"] if side == 1 else t["LTH"]
        mids = t["ITL"] if side == 1 else t["ITH"]
        opp_int = t["ITH"] if side == 1 else t["ITL"]
        opp_long = t["LTH"] if side == 1 else t["LTL"]
        for lt in anchors:
            nxt = first(mids, lambda m: m["i"] > lt["i"] and
                        (m["level"] > lt["level"] if side == 1 else m["level"] < lt["level"]))
            if nxt is None:
                continue
            gap = first(gaps, lambda g: g["dir"] == side and nxt["i"] < g["i"] <= nxt["i"] + window
                        and (g["top"] - g["bottom"]) / g["bottom"] * 100 >= min_gap_pct)
            if gap is None:
                continue
            # the move from the ITL must not have closed back through it before the gap formed
            if any((bars[j]["c"] < nxt["level"]) if side == 1 else (bars[j]["c"] > nxt["level"])
                   for j in range(nxt["i"] + 1, gap["i"] + 2)):
                continue
            known = max(lt["known"], nxt["known"], gap["known"])
            s = {"dir": "bullish" if side == 1 else "bearish",
                 "lt": {"type": "LTL" if side == 1 else "LTH", "level": r2(lt["level"]), "at": tr_time(bars[lt["i"]]["t"])},
                 "it": {"type": "ITL" if side == 1 else "ITH", "level": r2(nxt["level"]), "at": tr_time(bars[nxt["i"]]["t"])},
                 "fvg": {"top": r2(gap["top"]), "bottom": r2(gap["bottom"]), "at": tr_time(bars[gap["i"]]["t"])},
                 "known_at": tr_time(bars[known]["t"] + bar_step(bars)), "_known": known, "_gap": gap,
                 "_it": nxt}
            # plan: entry at the near edge of the gap, stop at the ITL/ITH, target the nearest
            # intermediate or long-term point on the other side that was known and not yet traded
            # through by then (untaken liquidity)
            entry = gap["top"] if side == 1 else gap["bottom"]
            stop = nxt["level"]

            def untaken(p):
                if p["known"] > known or not (p["level"] > entry if side == 1 else p["level"] < entry):
                    return False
                return not any((bars[j]["h"] > p["level"]) if side == 1 else (bars[j]["l"] < p["level"])
                               for j in range(p["i"] + 1, known + 1))
            pool = [p for p in opp_int + opp_long if untaken(p)]
            tgt = None
            if pool:
                tgt = min(pool, key=lambda p: p["level"]) if side == 1 else max(pool, key=lambda p: p["level"])
            risk = abs(entry - stop)
            if tgt:
                target = tgt["level"]
                target_from = "untaken %s" % ("ITH/LTH" if side == 1 else "ITL/LTL")
            else:                       # no untaken liquidity on the other side: fall back to 2R
                target = entry + 2 * risk if side == 1 else entry - 2 * risk
                target_from = "2R (no untaken liquidity %s)" % ("above" if side == 1 else "below")
            s["plan"] = {"entry": r2(entry), "stop": r2(stop), "target": r2(target), "target_from": target_from,
                         "risk": r2(risk),
                         "reward_risk": r2(abs(target - entry) / risk) if target is not None and risk > 0 else None}
            # STH / STL are fuel: the nearest untaken short-term point between the entry and the target is
            # the first target (T1); an untaken one just past the stop is liquidity a run would take with it
            near = [p for p in (t["STH"] if side == 1 else t["STL"]) if untaken(p)
                    and ((p["level"] < target) if side == 1 else (p["level"] > target))]
            t1 = None
            if near:
                t1 = min(near, key=lambda p: p["level"]) if side == 1 else max(near, key=lambda p: p["level"])
                s["plan"]["target1"] = r2(t1["level"])
                s["plan"]["target1_from"] = "untaken %s" % ("STH" if side == 1 else "STL")
                s["plan"]["rr1"] = r2(abs(t1["level"] - entry) / risk) if risk > 0 else None

            def untaken_beyond_stop(p):
                if p["known"] > known:
                    return False
                if not ((p["level"] < stop) if side == 1 else (p["level"] > stop)):
                    return False
                if abs(p["level"] - stop) > 0.25 * risk:
                    return False
                return not any((bars[j]["l"] < p["level"]) if side == 1 else (bars[j]["h"] > p["level"])
                               for j in range(p["i"] + 1, known + 1))
            bait = [p for p in (t["STL"] if side == 1 else t["STH"]) if untaken_beyond_stop(p)]
            if bait:
                b0 = min(bait, key=lambda p: p["level"]) if side == 1 else max(bait, key=lambda p: p["level"])
                s["plan"]["stop_warning"] = (
                    "untaken %s at %.2f sits just %s the stop: a run on that liquidity would take the stop too; "
                    "a stop past it would be %.2f" % ("STL" if side == 1 else "STH", b0["level"],
                                                      "under" if side == 1 else "over",
                                                      b0["level"] - 0.01 if side == 1 else b0["level"] + 0.01))
            # what happened after it was known: waiting -> tapped (price reached the FVG) -> target or
            # stopped; invalid if it closed through the ITL/ITH before a tap; missed if it ran to the
            # target without a tap. A bar that touches both stop and target counts as stopped.
            status, when = "waiting", None
            for j in range(known + 1, n):
                bj = bars[j]
                if status == "waiting":
                    if (bj["l"] <= entry) if side == 1 else (bj["h"] >= entry):
                        status, when = "tapped", j
                    elif (bj["c"] < stop) if side == 1 else (bj["c"] > stop):
                        status, when = "invalid", j
                        break
                    elif target is not None and ((bj["h"] >= target) if side == 1 else (bj["l"] <= target)):
                        status, when = "missed", j
                        break
                    if status == "waiting":
                        continue
                if (bj["l"] <= stop) if side == 1 else (bj["h"] >= stop):
                    status, when = "stopped", j
                    break
                if target is not None and ((bj["h"] >= target) if side == 1 else (bj["l"] <= target)):
                    status, when = "target", j
                    break
            s["status"] = status
            s["status_at"] = tr_time(bars[when]["t"]) if when is not None else None
            # did the first target (the STH / STL fuel) fill after a tap, before the stop?
            if t1 is not None and status in ("tapped", "target", "stopped"):
                tap = next(j for j in range(known + 1, n) if ((bars[j]["l"] <= entry) if side == 1
                                                               else (bars[j]["h"] >= entry)))
                hit = None
                for j in range(tap, n):
                    bj = bars[j]
                    if (bj["l"] <= stop) if side == 1 else (bj["h"] >= stop):
                        break
                    if (bj["h"] >= t1["level"]) if side == 1 else (bj["l"] <= t1["level"]):
                        hit = j
                        break
                s["t1_hit"] = tr_time(bars[hit]["t"]) if hit is not None else None
            out.append(s)
    out.sort(key=lambda s: s["_known"])
    return out


def liquidity_map(bars, t, horizons=(6, 12, 24, 48)):
    """How fast this chart's STH / STL (and ITH / ITL) get taken, and which are still untaken.
    Taken = a later bar trades through the level (a high over an STH, a low under an STL), counted
    from the bar it became known. Only points with the full horizon after them count for that horizon."""
    n = len(bars)
    out = {}
    base_h = 24
    # the baseline: from any bar, how often does price reach a level the same distance away within 24 bars?
    fwd_up = [max(bars[k]["h"] for k in range(i + 1, i + base_h + 1)) - bars[i]["c"] for i in range(n - base_h)]
    fwd_dn = [bars[i]["c"] - min(bars[k]["l"] for k in range(i + 1, i + base_h + 1)) for i in range(n - base_h)]
    for name in ("STH", "STL", "ITH", "ITL"):
        high = name.endswith("H")
        rows = []
        for p in t[name]:
            took = None
            for j in range(p["known"], n):
                if (bars[j]["h"] > p["level"]) if high else (bars[j]["l"] < p["level"]):
                    took = j - p["known"]
                    break
            rows.append((p, took))
        stats = {"points": len(rows)}
        for h in horizons:
            elig = [(p, k) for p, k in rows if n - 1 - p["known"] >= h]
            if elig:
                stats["taken_within_%d" % h] = r2(100.0 * sum(1 for p, k in elig if k is not None and k <= h)
                                                  / len(elig))
        elig = [p for p, k in rows if n - 1 - p["known"] >= base_h]
        fwd = fwd_up if high else fwd_dn
        if elig and fwd:
            probs = []
            for p in elig:
                d = (p["level"] - bars[p["known"]]["c"]) if high else (bars[p["known"]]["c"] - p["level"])
                probs.append(sum(1 for x in fwd if x > d) / float(len(fwd)))
            stats["baseline_within_24"] = r2(100.0 * sum(probs) / len(probs))
        times = sorted(k for p, k in rows if k is not None)
        stats["median_bars_to_take"] = times[len(times) // 2] if times else None
        untaken = [p for p, k in rows if k is None]
        price = bars[-1]["c"]
        untaken.sort(key=lambda p: abs(p["level"] - price))
        stats["untaken"] = [{"level": r2(p["level"]), "at": tr_time(bars[p["i"]]["t"]),
                             "age_bars": n - 1 - p["i"], "distance_pct": r2(100.0 * (p["level"] / price - 1))}
                            for p in untaken[:5]]
        stats["untaken_count"] = len(untaken)
        out[name] = stats
    return out


def bar_step(bars):
    if len(bars) < 2:
        return 0
    steps = sorted(bars[k + 1]["t"] - bars[k]["t"] for k in range(len(bars) - 1))
    return steps[len(steps) // 2]


def bias(t):
    """From the last two intermediate highs and lows: HH + HL bullish, LH + LL bearish."""
    ih, il = t["ITH"], t["ITL"]
    if len(ih) < 2 or len(il) < 2:
        return "unclear (not enough intermediate points)"
    hh, hl = ih[-1]["level"] > ih[-2]["level"], il[-1]["level"] > il[-2]["level"]
    if hh and hl:
        return "bullish (higher ITH and higher ITL)"
    if not hh and not hl:
        return "bearish (lower ITH and lower ITL)"
    return "mixed (%s ITH, %s ITL)" % ("higher" if hh else "lower", "higher" if hl else "lower")


def analyze(sym, bars, interval, now_utc, window=24, recent=5, min_gap_pct=0.0, resampled=False,
            range_window=24, skip_range=False, rr_band=(1.5, 3.5)):
    bars = closed_only(bars, interval, now_utc, resampled)
    if len(bars) < 20:
        raise StructureError("only %d closed bar(s) of %s by then: need at least 20" % (len(bars), sym))
    t = tiers(bars)
    gaps = fvgs(bars)
    setups = scan_setups(bars, t, gaps, window, min_gap_pct)
    reg = regime(bars, range_window)
    boxes = amd_boxes(bars, reg, range_window)
    liq = liquidity_map(bars, t)
    lo_rr, hi_rr = rr_band
    for s in setups:
        rr = s["plan"].get("reward_risk")
        s["plan"]["rr_band"] = None if rr is None else ("in band" if lo_rr <= rr <= hi_rr else
                                                       "under %.1f" % lo_rr if rr < lo_rr else "over %.1f" % hi_rr)
    for s in setups:
        k = s["_known"]
        s["regime"] = reg[k]["state"]
        s["in_range_box"] = box_at(boxes, k) is not None
    hidden = 0
    if skip_range:
        keep = [s for s in setups if not s["in_range_box"]]
        hidden = len(setups) - len(keep)
        setups = keep

    def pts(name):
        return [{"type": name, "level": r2(p["level"]), "at": tr_time(bars[p["i"]]["t"]),
                 "known_at": tr_time(bars[p["known"]]["t"] + bar_step(bars))} for p in t[name][-recent:]]

    active = [s for s in setups if s["status"] in ("waiting", "tapped")]
    done = [s for s in setups if s["status"] in ("target", "stopped")]
    clean = []
    for s in setups:
        clean.append({k: v for k, v in s.items() if not k.startswith("_")})
    price = bars[-1]["c"]
    return {
        "created_by": "trader-structure",
        "symbol": sym, "interval": interval, "bars": len(bars),
        "first_bar": tr_time(bars[0]["t"]), "last_bar": tr_time(bars[-1]["t"]), "price": r2(price),
        "timezone": "Turkey (UTC+3)",
        "bias": bias(t),
        "counts": {k: len(v) for k, v in t.items()},
        "points": {k: pts(k) for k in ("LTH", "LTL", "ITH", "ITL")},
        "setups": clean[-12:],
        "record": {"sequences": len(setups), "tapped": sum(1 for s in setups if s["status"] in
                                                            ("tapped", "target", "stopped")),
                   "target": sum(1 for s in done if s["status"] == "target"),
                   "stopped": sum(1 for s in done if s["status"] == "stopped"),
                   "missed": sum(1 for s in setups if s["status"] == "missed"),
                   "invalid": sum(1 for s in setups if s["status"] == "invalid")},
        "liquidity": liq,
        "t1_record": {"with_t1": sum(1 for s in setups if "t1_hit" in s),
                      "t1_hit": sum(1 for s in setups if s.get("t1_hit"))},
        "by_regime": record_by(setups, lambda s: "inside a range box" if s["in_range_box"] else
                               "regime " + s["regime"]),
        "hidden_in_range": hidden,
        "regime_now": regime_now(reg, boxes, bars),
        "active": [{k: v for k, v in s.items() if not k.startswith("_")} for s in active][-5:],
        "note": ("Structure points and setups are a way to read the chart, not a signal and not financial "
                 "advice. Every setup still needs your own confirmation, a stop, the risk check and your yes. "
                 "A sequence inside a range box is flagged [range]: there, wait for the raid (AMD) instead."),
    }


def record_by(setups, key):
    out = {}
    for s in setups:
        r = out.setdefault(key(s), {"sequences": 0, "tapped": 0, "target": 0, "stopped": 0})
        r["sequences"] += 1
        if s["status"] in ("tapped", "target", "stopped"):
            r["tapped"] += 1
        if s["status"] in ("target", "stopped"):
            r[s["status"]] += 1
    return out


def regime_now(reg, boxes, bars):
    r = reg[-1]
    out = {k: r.get(k) for k in ("state", "er", "vol_rel", "atr_rel", "touches")}
    live = box_at(boxes, len(bars) - 1)
    out["box"] = box_doc(live, bars) if live and live["end"] is None else None
    return out


def analyze_range(sym, bars, interval, now_utc, resampled=False, range_window=24, reclaim=3, recent=6):
    bars = closed_only(bars, interval, now_utc, resampled)
    need = range_window * 5 + 2
    if len(bars) < need:
        raise StructureError("only %d closed bar(s) of %s: the range filter needs %d (5 x --range-window + 2)"
                             % (len(bars), sym, need))
    reg = regime(bars, range_window)
    boxes = amd_boxes(bars, reg, range_window, reclaim)
    docs = [box_doc(b, bars) for b in boxes]
    ended = [d for d in docs if d["outcome"]]
    raided = [b for b in boxes if b.get("side") is not None]
    amd = [b for b in raided if b["outcome"] and b["outcome"].startswith("AMD")]
    failed = [b for b in raided if b["outcome"] and b["outcome"].startswith("failed")]
    states = [r["state"] for r in reg if r["state"] != "unknown"]
    return {
        "created_by": "trader-structure", "mode": "range",
        "symbol": sym, "interval": interval, "bars": len(bars), "range_window": range_window,
        "last_bar": tr_time(bars[-1]["t"]), "price": r2(bars[-1]["c"]), "timezone": "Turkey (UTC+3)",
        "volume_in_data": any(r.get("vol_rel") is not None for r in reg),
        "now": regime_now(reg, boxes, bars),
        "time_in_range_pct": r2(100.0 * states.count("range") / len(states)) if states else None,
        "boxes": docs[-recent:],
        "record": {"boxes": len(boxes), "ended": len(ended), "raided": len(raided),
                   "amd_complete": len(amd), "raid_failed": len(failed),
                   "breakout_no_raid": sum(1 for b in boxes if (b["outcome"] or "").startswith("breakout")),
                   "faded": sum(1 for b in boxes if b["outcome"] == "faded")},
        "note": ("A range is read from efficiency, volume and edge visits; a raid is a take of one edge that "
                 "comes back inside; AMD is complete when the opposite edge breaks. It is a reading, not a "
                 "signal and not financial advice: wait for your own confirmation after the raid."),
    }


# ---------------------------------------------------------------- range / AMD (power of three)

def efficiency(bars, i, n):
    """Kaufman efficiency ratio over the n bars up to i: net move / total path. Near 0 = chop."""
    path = sum(abs(bars[j]["c"] - bars[j - 1]["c"]) for j in range(i - n + 1, i + 1))
    return abs(bars[i]["c"] - bars[i - n]["c"]) / path if path > 0 else 0.0


def true_range(bars, j):
    b, pc = bars[j], bars[j - 1]["c"]
    return max(b["h"] - b["l"], abs(b["h"] - pc), abs(b["l"] - pc))


def edge_touches(bars, lo_i, hi_i, level, tol, top):
    """Separate visits to an edge: runs of bars whose high (low) came within tol of it."""
    n, inside = 0, False
    for j in range(lo_i, hi_i + 1):
        near = bars[j]["h"] >= level - tol if top else bars[j]["l"] <= level + tol
        if near and not inside:
            n += 1
        inside = near
    return n


def regime(bars, window=24, long_mult=5, er_max=0.3, vol_ratio=0.8, atr_ratio=0.85, edge_tol=0.15):
    """Per bar, from that bar and the ones before it only:
      range  the net move over `window` bars is small next to the path (efficiency under er_max),
             volume is under vol_ratio x its long average (or, with no volume in the data, the ATR is
             under atr_ratio x its long average), and both edges were visited at least twice
      trend  efficiency 0.5 or more
      mixed  anything else; unknown until there is a long window of history"""
    long_n = window * long_mult
    has_vol = sum(1 for b in bars if b.get("v")) > len(bars) // 2
    out = []
    for i in range(len(bars)):
        if i < long_n:
            out.append({"state": "unknown"})
            continue
        er = efficiency(bars, i, window)
        tr_s = sum(true_range(bars, j) for j in range(i - window + 1, i + 1)) / window
        tr_l = sum(true_range(bars, j) for j in range(i - long_n + 1, i + 1)) / long_n
        atr_rel = tr_s / tr_l if tr_l > 0 else 1.0
        vol_rel = None
        if has_vol:
            v_s = sum(bars[j].get("v", 0) for j in range(i - window + 1, i + 1)) / window
            v_l = sum(bars[j].get("v", 0) for j in range(i - long_n + 1, i + 1)) / long_n
            vol_rel = v_s / v_l if v_l > 0 else 1.0
        hi = max(bars[j]["h"] for j in range(i - window + 1, i + 1))
        lo = min(bars[j]["l"] for j in range(i - window + 1, i + 1))
        tol = (hi - lo) * edge_tol
        tops = edge_touches(bars, i - window + 1, i, hi, tol, True)
        bots = edge_touches(bars, i - window + 1, i, lo, tol, False)
        quiet = (vol_rel < vol_ratio) if vol_rel is not None else (atr_rel < atr_ratio)
        if er < er_max and quiet and tops >= 2 and bots >= 2:
            state = "range"
        elif er >= 0.5:
            state = "trend"
        else:
            state = "mixed"
        out.append({"state": state, "er": round(er, 3), "atr_rel": round(atr_rel, 3),
                    "vol_rel": None if vol_rel is None else round(vol_rel, 3), "high": hi, "low": lo,
                    "touches": [tops, bots]})
    return out


def amd_boxes(bars, reg, window=24, reclaim=3, max_mult=5):
    """Range boxes and what happened to each, bar by bar (power of three):
      accumulation  the box, frozen when the regime first says range
      manipulation  one edge taken: a wick through it that closes back inside, or closes outside that
                    come back inside within `reclaim` bars. The extreme of the raid is kept
      distribution  after a manipulation, a close beyond the OPPOSITE edge: AMD complete
    Other endings: breakout (closed outside for `reclaim` bars with no raid before), failed (closed
    beyond the raid's extreme: it was a real move, not a raid), faded (no ending in max_mult x window)."""
    boxes, box = [], None
    n = len(bars)
    resume = 0                      # after a box ends, wait half a window before the next one
    i = 0
    while i < n:
        if box is None:
            if i >= resume and reg[i]["state"] == "range":
                hi, lo = reg[i]["high"], reg[i]["low"]
                box = {"start": i - window + 1, "detected": i, "high": hi, "low": lo, "phase": "accumulation",
                       "events": [], "outside": None, "extreme": None, "side": None, "end": None,
                       "outcome": None}
            i += 1
            continue
        b = bars[i]
        hi, lo = box["high"], box["low"]
        ph = box["phase"]
        if ph == "accumulation":
            if box["outside"] is not None:
                side, since = box["outside"]
                back = (b["c"] <= hi) if side == 1 else (b["c"] >= lo)
                if back:
                    ext = max(bars[j]["h"] for j in range(since, i + 1)) if side == 1 else \
                        min(bars[j]["l"] for j in range(since, i + 1))
                    box.update(phase="manipulation", side=side, extreme=ext, outside=None, raid_at=i)
                    box["events"].append({"i": i, "type": "raid " + ("high" if side == 1 else "low"),
                                          "extreme": ext, "how": "closed back inside after %d bar(s) out"
                                          % (i - since)})
                elif i - since + 1 >= reclaim:
                    box.update(end=i, outcome="breakout " + ("up" if side == 1 else "down"), outside=None)
            elif b["c"] > hi or b["c"] < lo:
                box["outside"] = (1 if b["c"] > hi else -1, i)
            elif b["h"] > hi or b["l"] < lo:
                side = 1 if b["h"] > hi else -1
                if b["h"] > hi and b["l"] < lo:          # both edges in one bar: the one it closed away from
                    side = 1 if b["c"] < (hi + lo) / 2 else -1
                ext = b["h"] if side == 1 else b["l"]
                box.update(phase="manipulation", side=side, extreme=ext, raid_at=i)
                box["events"].append({"i": i, "type": "raid " + ("high" if side == 1 else "low"),
                                      "extreme": ext, "how": "wick through the edge, closed back inside"})
        elif ph == "manipulation":
            side, ext = box["side"], box["extreme"]
            if (side == -1 and b["c"] > hi) or (side == 1 and b["c"] < lo):
                box.update(end=i, outcome="AMD " + ("bullish" if side == -1 else "bearish"))
                box["events"].append({"i": i, "type": "distribution", "how": "closed beyond the opposite edge"})
            elif (side == -1 and b["c"] < ext) or (side == 1 and b["c"] > ext):
                box.update(end=i, outcome="failed: closed beyond the raid, a real move " +
                           ("down" if side == -1 else "up"))
            elif side == -1 and b["l"] < ext:
                box["extreme"] = b["l"]
            elif side == 1 and b["h"] > ext:
                box["extreme"] = b["h"]
        if box["end"] is None and i - box["detected"] >= max_mult * window:
            box.update(end=i, outcome="faded")
        if box["end"] is not None:
            boxes.append(box)
            box = None
            resume = i + 1 + window // 2
        i += 1
    if box is not None:
        boxes.append(box)
    return boxes


def amd_plan(box, bars):
    """After a raid of one edge: long from the reclaim close (raid of the low), stop past the raid's
    extreme, first target the opposite edge, second the opposite edge plus the box height."""
    if box.get("side") is None:
        return None
    side = -box["side"]                       # trade AGAINST the raided side
    i = box["raid_at"]
    entry, ext = bars[i]["c"], box["extreme"]
    height = box["high"] - box["low"]
    stop = ext
    t1 = box["high"] if side == 1 else box["low"]
    t2 = t1 + height if side == 1 else t1 - height
    risk = abs(entry - stop)
    return {"dir": "long" if side == 1 else "short", "entry": r2(entry), "stop": r2(stop),
            "target1": r2(t1), "target2": r2(t2), "risk": r2(risk),
            "rr1": r2(abs(t1 - entry) / risk) if risk > 0 else None,
            "rr2": r2(abs(t2 - entry) / risk) if risk > 0 else None}


def box_doc(box, bars):
    return {"high": r2(box["high"]), "low": r2(box["low"]),
            "height_pct": r2(100.0 * (box["high"] - box["low"]) / box["low"]),
            "from": tr_time(bars[box["start"]]["t"]), "detected": tr_time(bars[box["detected"]]["t"]),
            "phase": box["phase"] if box["end"] is None else "ended",
            "raided": None if box.get("side") is None else ("high" if box["side"] == 1 else "low"),
            "raid_extreme": r2(box.get("extreme")),
            "events": [{"at": tr_time(bars[e["i"]]["t"]), "type": e["type"], "how": e["how"],
                        "extreme": r2(e.get("extreme"))} for e in box["events"]],
            "ended": tr_time(bars[box["end"]]["t"]) if box["end"] is not None else None,
            "outcome": box["outcome"], "plan": amd_plan(box, bars)}


def box_at(boxes, i):
    """The box that was live at bar i (detected by then, not yet ended), else None."""
    for b in boxes:
        if b["detected"] <= i and (b["end"] is None or i < b["end"]):
            return b
    return None


# ---------------------------------------------------------------- key levels

def _nth_sunday(year, month, n):
    d = datetime.date(year, month, 1)
    d += datetime.timedelta(days=(6 - d.weekday()) % 7)
    return d + datetime.timedelta(weeks=n - 1)


def ny_offset(utc):
    """-4 in US daylight time, -5 otherwise (second Sunday of March to first Sunday of November)."""
    y = utc.year
    start = datetime.datetime.combine(_nth_sunday(y, 3, 2), datetime.time(7, 0))
    end = datetime.datetime.combine(_nth_sunday(y, 11, 1), datetime.time(6, 0))
    return -4 if start <= utc < end else -5


def to_ny(ts):
    utc = EPOCH + datetime.timedelta(seconds=int(ts))
    return utc + datetime.timedelta(hours=ny_offset(utc))


CALENDARS = {
    "crypto": "24/7: the day starts 00:00 UTC (03:00 Turkey), the week on Monday 00:00 UTC",
    "cme": "CME futures: the trading day starts 18:00 New York the evening before, the week on Sunday 18:00",
    "stock": "US stocks: New York calendar days",
    "bist": "Borsa Istanbul: Istanbul calendar days",
}


def guess_calendar(sym):
    if sym.endswith("USDT") or sym.endswith("-USD") or sym.endswith("USDC") or sym.endswith("BUSD"):
        return "crypto"
    if sym.endswith("=F"):
        return "cme"
    if sym.endswith(".IS"):
        return "bist"
    return "stock"


def trading_day(ts, cal):
    """The trading day a bar belongs to under that calendar."""
    if cal == "crypto":
        return (EPOCH + datetime.timedelta(seconds=int(ts))).date()
    if cal == "bist":
        return (EPOCH + datetime.timedelta(seconds=int(ts)) + TR).date()
    ny = to_ny(ts)
    if cal == "cme" and ny.time() >= datetime.time(18, 0):
        return ny.date() + datetime.timedelta(days=1)
    return ny.date()


def period_key(day, kind):
    if kind == "day":
        return day.isoformat()
    if kind == "week":
        y, w, _ = day.isocalendar()
        return "%d-W%02d" % (y, w)
    return "%d-%02d" % (day.year, day.month)


def periods(bars, cal):
    """{kind: [(key, {open, high, low, close, first, last, hi_i, lo_i, monday...})]} in time order."""
    out = {"day": [], "week": [], "month": []}
    for i, b in enumerate(bars):
        d = trading_day(b["t"], cal)
        for kind in out:
            k = period_key(d, kind)
            lst = out[kind]
            if not lst or lst[-1][0] != k:
                lst.append((k, {"open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"], "first": i,
                                "last": i, "hi_i": i, "lo_i": i, "start_day": d}))
            else:
                p = lst[-1][1]
                if b["h"] > p["high"]:
                    p["high"], p["hi_i"] = b["h"], i
                if b["l"] < p["low"]:
                    p["low"], p["lo_i"] = b["l"], i
                p["close"], p["last"] = b["c"], i
    return out


def first_take(bars, level, start, end, above, reclaim=3):
    """The first bar in [start, end] that trades through `level`, and whether price was accepted
    beyond it (the close `reclaim` - 1 bars later is still beyond) or it was a sweep (no close beyond,
    or back on the near side by then)."""
    for j in range(start, end + 1):
        b = bars[j]
        if (b["h"] > level) if above else (b["l"] < level):
            closes = [bars[k]["c"] for k in range(j, min(end, j + reclaim - 1) + 1)]
            beyond = [(c > level) if above else (c < level) for c in closes]
            if not any(beyond):
                how = "swept (wick through, closed back)"
            elif beyond[-1] and len(closes) == reclaim:
                how = "accepted beyond (still past it %d bars later)" % (reclaim - 1)
            elif beyond[-1]:
                how = "closing beyond so far"
            else:
                how = "swept (closed past it, came back within %d bars)" % reclaim
            return {"at": tr_time(b["t"]), "how": how, "i": j}
    return None


def key_levels(sym, bars, interval, now_utc, cal=None, resampled=False, reclaim=3):
    bars = closed_only(bars, interval, now_utc, resampled)
    if len(bars) < 10:
        raise StructureError("only %d closed bar(s) of %s by then" % (len(bars), sym))
    if SECONDS[interval] > 3600 * 4:
        raise StructureError("key levels need intraday bars (1h or smaller) to find opens and the Monday range")
    cal = cal or guess_calendar(sym)
    if cal not in CALENDARS:
        raise StructureError("--calendar is one of %s" % ", ".join(CALENDARS))
    per = periods(bars, cal)
    n = len(bars) - 1
    price = bars[-1]["c"]
    levels, notes = [], []

    def complete(kind, idx):
        """A period is whole only if the data starts before it (else the first one is cut)."""
        return idx > 0

    def add(name, code, value, since=None, extra=None):
        if value is None:
            return
        d = {"name": name, "code": code, "level": r2(value), "distance_pct": r2(100.0 * (value / price - 1))}
        if since:
            d["since"] = since
        if extra:
            d.update(extra)
        levels.append(d)

    def range_levels(kind, label, code):
        lst = per[kind]
        cur_i = len(lst) - 1
        key, cur = lst[cur_i]
        if complete(kind, cur_i):
            add("%s open" % label, code + "O", cur["open"], tr_time(bars[cur["first"]]["t"]))
        else:
            notes.append("the data starts inside this %s, so its open is unknown" % kind)
        if cur_i >= 1:
            pkey, prev = lst[cur_i - 1]
            if not complete(kind, cur_i - 1):
                notes.append("the previous %s (%s) is only partly in the data: its high and low are a "
                             "lower bound; fetch more history" % (kind, pkey))
            mid = (prev["high"] + prev["low"]) / 2
            for nm, cd, val, above in (("previous %s high" % label, "P" + code + "H", prev["high"], True),
                                       ("previous %s low" % label, "P" + code + "L", prev["low"], False)):
                take = first_take(bars, val, cur["first"], n, above, reclaim)
                add(nm, cd, val, pkey, {"taken": take and {"at": take["at"], "how": take["how"]},
                                        "partial": not complete(kind, cur_i - 1)})
            add("previous %s equilibrium" % label, "P" + code + "EQ", mid, pkey)
            return {"key": key, "prev_key": pkey, "prev_high": r2(prev["high"]), "prev_low": r2(prev["low"]),
                    "position_pct": r2(100.0 * (price - prev["low"]) / (prev["high"] - prev["low"]))
                    if prev["high"] > prev["low"] else None,
                    "high_so_far": r2(cur["high"]), "low_so_far": r2(cur["low"])}
        return {"key": key}

    day = range_levels("day", "day", "D")
    week = range_levels("week", "week", "W")
    month = range_levels("month", "month", "M")

    if cal == "cme":
        # ICT's midnight open: the first bar at or after 00:00 New York of the current trading day
        cur = per["day"][-1][1]
        for j in range(cur["first"], n + 1):
            ny = to_ny(bars[j]["t"])
            if ny.time() >= datetime.time(0, 0) and ny.date() == per["day"][-1][1]["start_day"]:
                add("New York midnight open", "MNO", bars[j]["o"], tr_time(bars[j]["t"]))
                break

    # Monday range: the first trading day of the current week, if it is in the data
    mon = None
    wk_first = per["week"][-1][1]["first"]
    days_this_week = [(k, p) for k, p in per["day"] if p["first"] >= wk_first]
    if days_this_week and days_this_week[0][1]["start_day"].weekday() == 0:
        mk, m = days_this_week[0]
        whole_week_in_data = len(per["week"]) > 1
        forming = len(days_this_week) == 1
        mon = {"day": mk, "high": r2(m["high"]), "low": r2(m["low"]), "eq": r2((m["high"] + m["low"]) / 2),
               "forming": forming, "complete": whole_week_in_data}
        if not forming:
            after = m["last"] + 1
            hi_take = first_take(bars, m["high"], after, n, True, reclaim)
            lo_take = first_take(bars, m["low"], after, n, False, reclaim)
            mon["high_taken"] = hi_take and {"at": hi_take["at"], "how": hi_take["how"]}
            mon["low_taken"] = lo_take and {"at": lo_take["at"], "how": lo_take["how"]}
            first = min([t for t in (hi_take, lo_take) if t], key=lambda t: t["i"], default=None)
            if first:
                mon["first_side_taken"] = "high" if first is hi_take else "low"
            mon["position_pct"] = r2(100.0 * (price - m["low"]) / (m["high"] - m["low"])) \
                if m["high"] > m["low"] else None
        add("Monday high", "MH", m["high"], mk, {"forming": forming})
        add("Monday low", "ML", m["low"], mk, {"forming": forming})
        add("Monday equilibrium", "MEQ", (m["high"] + m["low"]) / 2, mk, {"forming": forming})
    elif days_this_week:
        notes.append("the week's first trading day in the data is not a Monday (a holiday, or the data starts "
                     "mid-week): no Monday range")

    above = sorted([l for l in levels if l["level"] > price], key=lambda l: l["level"])
    below = sorted([l for l in levels if l["level"] <= price], key=lambda l: -l["level"])
    return {
        "created_by": "trader-structure", "mode": "levels", "symbol": sym, "interval": interval,
        "calendar": cal, "calendar_rule": CALENDARS[cal], "last_bar": tr_time(bars[-1]["t"]),
        "price": r2(price), "timezone": "Turkey (UTC+3)",
        "day": day, "week": week, "month": month, "monday": mon,
        "above": above, "below": below, "notes": notes,
        "note": ("Key levels are where price has reacted before and where stops collect; they are places to "
                 "watch, not signals and not financial advice. Prop-firm CFD prices can differ a little from "
                 "this feed."),
    }


def render_levels(doc):
    out = ["%s  key levels  (%s bars, last bar %s Turkey time)" % (doc["symbol"], doc["interval"], doc["last_bar"]),
           "Calendar: %s" % doc["calendar_rule"], "Last close %.2f" % doc["price"], ""]

    def pos(x):
        if x is None:
            return ""
        if x < 0:
            return "below the range (%.0f %% of its height under the low)" % -x
        if x > 100:
            return "above the range (%.0f %% of its height over the high)" % (x - 100)
        zone = "premium" if x > 50 else "discount" if x < 50 else "equilibrium"
        return "%.0f %% of the range (%s)" % (x, zone)

    w, m = doc["week"], doc["month"]
    if w.get("prev_high") is not None:
        out.append("Previous week %s: %.2f-%.2f, price at %s" % (w["prev_key"], w["prev_low"], w["prev_high"],
                                                               pos(w["position_pct"])))
    if m.get("prev_high") is not None:
        out.append("Previous month %s: %.2f-%.2f, price at %s" % (m["prev_key"], m["prev_low"], m["prev_high"],
                                                                pos(m["position_pct"])))
    mo = doc["monday"]
    if mo:
        line = "Monday %s range %.2f-%.2f (EQ %.2f)" % (mo["day"], mo["low"], mo["high"], mo["eq"])
        if mo["forming"]:
            line += ", still forming"
        else:
            line += ", price at %s" % pos(mo.get("position_pct"))
        out.append(line)
        for side in ("high", "low"):
            t = mo.get(side + "_taken")
            if t:
                out.append("  Monday %s taken %s: %s" % (side, t["at"][5:], t["how"]))
            elif not mo["forming"]:
                out.append("  Monday %s not taken yet" % side)
        if mo.get("first_side_taken"):
            out.append("  first side taken: the %s" % mo["first_side_taken"])
    out += ["", "Above (nearest first)"]

    def row(l):
        extra = []
        if l.get("taken"):
            extra.append("taken %s, %s" % (l["taken"]["at"][5:], l["taken"]["how"].split(" (")[0]))
        if l.get("partial"):
            extra.append("partial data")
        if l.get("forming"):
            extra.append("forming")
        return "  %-5s %-28s %10.2f  %+6.2f%%  %s" % (l["code"], l["name"], l["level"], l["distance_pct"],
                                                       "; ".join(extra))

    out += [row(l) for l in doc["above"]] or ["  none"]
    out += ["  ----- %.2f last close -----" % doc["price"], "Below (nearest first)"]
    out += [row(l) for l in doc["below"]] or ["  none"]
    for n_ in doc["notes"]:
        out.append("Note: " + n_)
    out += ["", doc["note"]]
    return "\n".join(out)


# ---------------------------------------------------------------- lower-timeframe confirmation

def ltf_pivots(bars, n=2):
    """Fractal swing highs and lows on the lower timeframe: n bars each side, known n bars later."""
    hs, ls = [], []
    for i in range(n, len(bars) - n):
        h, l = bars[i]["h"], bars[i]["l"]
        if all(h > bars[k]["h"] for k in range(i - n, i)) and all(h >= bars[k]["h"] for k in range(i + 1, i + n + 1)):
            hs.append({"i": i, "level": h, "known": i + n})
        if all(l < bars[k]["l"] for k in range(i - n, i)) and all(l <= bars[k]["l"] for k in range(i + 1, i + n + 1)):
            ls.append({"i": i, "level": l, "known": i + n})
    return hs, ls


def _follow(lb, j, stop, target, up, hold):
    """From bar j+1: which came first within `hold` bars, the stop or the target. A bar touching both
    counts as stopped."""
    for k in range(j + 1, min(len(lb), j + 1 + hold)):
        x = lb[k]
        if (x["l"] <= stop) if up else (x["h"] >= stop):
            return "stopped", tr_time(x["t"])
        if target is not None and ((x["h"] >= target) if up else (x["l"] <= target)):
            return "target", tr_time(x["t"])
    return "open", None


def ltf_atr(lb, n=14):
    out, trs = [], []
    for i, b in enumerate(lb):
        trs.append(b["h"] - b["l"] if i == 0 else true_range(lb, i))
        w = trs[-n:]
        out.append(sum(w) / len(w))
    return out


def _finish(res, lb, j, entry, stop, target, up, hold, rr_band):
    """A confirmation at bar j: R:R, what happened next, and the user's band (skip under rr_min, take
    profit at rr_max when the HTF target is further)."""
    risk = abs(entry - stop)
    res.update(state="confirmed", at=tr_time(lb[j]["t"]), entry=r2(entry), stop=r2(stop), risk=r2(risk),
               rr=r2(abs(target - entry) / risk) if target is not None else None, target=r2(target))
    if target is not None and ((target <= entry) if up else (target >= entry)):
        res["state"] = "confirmed past the target"
        return res
    res["result"], res["result_at"] = _follow(lb, j, stop, target, up, hold)
    lo, hi = rr_band
    rr = res["rr"]
    if rr is None or rr < lo:
        res["band"] = {"action": "skip (R:R under %.1f)" % lo}
    else:
        tgt = target
        if rr > hi:
            tgt = entry + hi * risk if up else entry - hi * risk
        r_, at_ = _follow(lb, j, stop, tgt, up, hold)
        res["band"] = {"action": "take profit at %.1fR" % hi if rr > hi else "full HTF target",
                       "target": r2(tgt), "rr": r2(min(rr, hi)), "result": r_, "result_at": at_}
    return res


def ltf_confirm(lb, side, zone_lo, zone_hi, htf_stop, target, start, piv=None, window=36, lookback=24,
                hold=288, swing=2, atr=None, rr_band=(1.5, 3.5), buffer=0.0, mode="itl", ltiers=None):
    """Watch the lower timeframe from bar `start`: the first touch of the zone, then the confirmation,
    before a close through the higher-timeframe stop and within `window` bars of the touch.

      mode "itl"    the first LTF ITL (long) / ITH (short) whose low (high) formed at or after the touch;
                    it confirms when it becomes known (its right-hand STL / STH is confirmed). Entry at
                    that bar's close, stop at the ITL low (ITH high)
      mode "choch"  a close through the last LTF swing high (low) that came before the extreme made in
                    the zone. Entry at that close, stop at the extreme

    Returns the state, and for a confirmation the entry, the stop, the R:R to the target and what
    happened next (target or stop first, within `hold` bars)."""
    n = len(lb)
    up = side == "long"
    atr = atr or ltf_atr(lb)
    word = "an ITL" if (mode == "itl" and up) else "an ITH" if mode == "itl" else "a CHoCH"
    res = {"state": "waiting for a touch", "touch": None, "mode": mode}
    j0 = None
    for j in range(start, n):
        b = lb[j]
        if (b["c"] < htf_stop) if up else (b["c"] > htf_stop):
            res["state"] = "invalid before a touch"
            res["at"] = tr_time(b["t"])
            return res
        if (b["l"] <= zone_hi) if up else (b["h"] >= zone_lo):
            j0 = j
            break
        if target is not None and ((b["h"] >= target) if up else (b["l"] <= target)):
            res["state"] = "missed (reached the target before a touch)"
            res["at"] = tr_time(b["t"])
            return res
    if j0 is None:
        return res
    res.update(state="touched, waiting for %s" % word, touch=tr_time(lb[j0]["t"]))

    if mode == "itl":
        t = ltiers or tiers(lb)
        pts = t["ITL"] if up else t["ITH"]
        cand = [p for p in pts if p["i"] >= j0]
        for j in range(j0, min(n, j0 + window + 1)):
            b = lb[j]
            if (b["c"] < htf_stop) if up else (b["c"] > htf_stop):
                res.update(state="invalidated (closed through the HTF stop)", at=tr_time(b["t"]))
                return res
            hit = [p for p in cand if p["known"] == j]
            if hit:
                p = hit[0]
                pad = buffer * atr[j]
                stop = p["level"] - pad if up else p["level"] + pad
                entry = b["c"]
                if (entry - stop) * (1 if up else -1) <= 0:
                    continue
                res["itl"] = {"level": r2(p["level"]), "at": tr_time(lb[p["i"]]["t"])}
                res["confirm_level"] = r2(p["level"])
                return _finish(res, lb, j, entry, stop, target, up, hold, rr_band)
        if j0 + window < n:
            res["state"] = "no %s within the window" % ("ITL" if up else "ITH")
        return res

    hs, ls = piv or ltf_pivots(lb, swing)
    opp = hs if up else ls                          # the swings a CHoCH must close through
    ext_i = j0
    for j in range(j0, min(n, j0 + window + 1)):
        b = lb[j]
        if (b["l"] < lb[ext_i]["l"]) if up else (b["h"] > lb[ext_i]["h"]):
            ext_i = j
        if (b["c"] < htf_stop) if up else (b["c"] > htf_stop):
            res.update(state="invalidated (closed through the HTF stop)", at=tr_time(b["t"]))
            return res
        cands = [p for p in opp if p["known"] <= j and j0 - lookback <= p["i"] < ext_i]
        if not cands:
            continue
        key = cands[-1]
        res["watch"] = r2(key["level"])
        if (b["c"] > key["level"]) if up else (b["c"] < key["level"]):
            entry = b["c"]
            pad = buffer * atr[j]
            stop = lb[ext_i]["l"] - pad if up else lb[ext_i]["h"] + pad
            if abs(entry - stop) <= 0:
                continue
            disp = abs(b["c"] - b["o"]) >= atr[j]
            gap = None
            for k in range(ext_i + 1, j):
                a_, c_ = lb[k - 1], lb[k + 1]
                if up and a_["h"] < c_["l"]:
                    gap = (a_["h"], c_["l"])
                elif not up and a_["l"] > c_["h"]:
                    gap = (c_["h"], a_["l"])
            res.update(choch_level=r2(key["level"]), confirm_level=r2(key["level"]), displacement=bool(disp or gap),
                       ltf_fvg=[r2(gap[0]), r2(gap[1])] if gap else None)
            return _finish(res, lb, j, entry, stop, target, up, hold, rr_band)
    if j0 + window < n:
        res["state"] = "no CHoCH within the window"
    return res


def bias_at(dbars, t_utc, step=86400):
    """The higher-timeframe bias at a moment, from the bars that had closed by then only:
    the last two ITH and ITL (higher and higher = bullish, lower and lower = bearish), falling back to the
    last two STH and STL when there are not enough intermediate points yet."""
    seen = [b for b in dbars if b["t"] + step <= t_utc]
    if len(seen) < 5:
        return "unknown", "fewer than 5 closed bars"
    t = tiers(seen)
    for hi_k, lo_k in (("ITH", "ITL"), ("STH", "STL")):
        ih, il = t[hi_k], t[lo_k]
        if len(ih) >= 2 and len(il) >= 2:
            hh, hl = ih[-1]["level"] > ih[-2]["level"], il[-1]["level"] > il[-2]["level"]
            if hh and hl:
                return "bullish", "%s higher, %s higher" % (hi_k, lo_k)
            if not hh and not hl:
                return "bearish", "%s lower, %s lower" % (hi_k, lo_k)
            return "mixed", "%s %s, %s %s" % (hi_k, "higher" if hh else "lower", lo_k, "higher" if hl else "lower")
    return "unknown", "not enough swings yet"


def confirm_sequences(lbars, ltf, htf, now_utc, window=36, swing=2, hold=288, rr_band=(1.5, 3.5),
                      fvg_window=24, buffer=0.0, bias_bars=None, bias_tf=None, mode="itl", include_range=False,
                      range_window=24):
    """Every higher-timeframe LTL -> ITL -> FVG sequence (built from the same data), each followed on the
    lower timeframe; plus the comparison: entering at the HTF gap vs waiting for the LTF CHoCH."""
    lbars = closed_only(lbars, ltf, now_utc)
    step_h = SECONDS[htf]
    if step_h <= SECONDS[ltf]:
        raise StructureError("--htf must be a bigger bar than the data's %s" % ltf)
    hbars = closed_only(resample(lbars, htf), htf, now_utc, resampled=True)
    if len(hbars) < 30:
        raise StructureError("only %d %s bars from this data: fetch more history (--days, --range)" % (len(hbars), htf))
    t = tiers(hbars)
    setups = scan_setups(hbars, t, fvgs(hbars), fvg_window)
    piv = ltf_pivots(lbars, swing)
    lt = tiers(lbars) if mode == "itl" else None
    atr = ltf_atr(lbars)
    hreg = regime(hbars, range_window)
    hboxes = amd_boxes(hbars, hreg, range_window)
    times = [b["t"] for b in lbars]
    rows = []
    for s in setups:
        k = s["_known"]
        start_t = hbars[k]["t"] + step_h            # the first LTF bar after the sequence became visible
        start = next((i for i, x in enumerate(times) if x >= start_t), None)
        if start is None:
            continue
        side = "long" if s["dir"] == "bullish" else "short"
        p = s["plan"]
        in_range = box_at(hboxes, k) is not None
        res = ltf_confirm(lbars, side, s["fvg"]["bottom"], s["fvg"]["top"], p["stop"], p["target"], start,
                          piv, window, hold=hold, swing=swing, atr=atr, rr_band=rr_band, buffer=buffer,
                          mode=mode, ltiers=lt)
        htf_r = {"target": p["reward_risk"], "stopped": -1.0}.get(s["status"])
        ltf_r = band_r = None
        if res.get("result") == "target":
            ltf_r = res["rr"]
        elif res.get("result") == "stopped":
            ltf_r = -1.0
        bd = res.get("band") or {}
        if bd.get("result") == "target":
            band_r = bd["rr"]
        elif bd.get("result") == "stopped":
            band_r = -1.0
        bias = why = None
        if bias_bars is not None:
            bias, why = bias_at(bias_bars, start_t, SECONDS[bias_tf])
        rows.append({"dir": s["dir"], "known_at": s["known_at"], "zone": [s["fvg"]["bottom"], s["fvg"]["top"]],
                     "bias": bias, "bias_why": why, "in_range": in_range, "regime": hreg[k]["state"],
                     "aligned": None if bias is None else bias == s["dir"],
                     "htf_plan": {"entry": p["entry"], "stop": p["stop"], "target": p["target"],
                                  "rr": p["reward_risk"], "status": s["status"]},
                     "ltf": res, "htf_r": htf_r, "ltf_r": ltf_r, "band_r": band_r})
    lo, hi = rr_band
    for r in rows:
        rr = r["ltf"].get("rr")
        if rr is not None:
            r["ltf"]["rr_band"] = "in band" if lo <= rr <= hi else ("under %.1f" % lo if rr < lo else "over %.1f" % hi)

    all_rows = rows
    ranged = [r for r in rows if r["in_range"]]
    if not include_range:
        rows = [r for r in rows if not r["in_range"]]

    def tally(key, only=None):
        xs = [r[key] for r in rows if r[key] is not None and (only is None or r["aligned"] is only)]
        return {"trades": len(xs), "wins": sum(1 for x in xs if x > 0), "total_r": r2(sum(xs)),
                "avg_r": r2(sum(xs) / len(xs)) if xs else None}
    conf = [r for r in rows if r["ltf"]["state"].startswith("confirmed")]
    return {
        "created_by": "trader-structure", "mode": "confirm", "ltf": ltf, "htf": htf,
        "ltf_bars": len(lbars), "htf_bars": len(hbars), "from": tr_time(lbars[0]["t"]), "to": tr_time(lbars[-1]["t"]),
        "price": r2(lbars[-1]["c"]), "timezone": "Turkey (UTC+3)", "rr_band": list(rr_band),
        "mode": mode, "range_excluded": 0 if include_range else len(ranged),
        "sequences": all_rows[-12:],
        "live": [r for r in rows if r["ltf"]["state"] in ("waiting for a touch", "touched, waiting for a CHoCH")
                 or (r["ltf"].get("result") == "open")],
        "compare": {"htf_entry": tally("htf_r"), "ltf_confirmed": tally("ltf_r"),
                    "ltf_with_band": tally("band_r"),
                    "skipped_by_band": sum(1 for r in conf if (r["ltf"].get("band") or {}).get("action", "")
                                           .startswith("skip")),
                    "touched": sum(1 for r in rows if r["ltf"]["touch"]),
                    "confirmed": len(conf),
                    "no_confirmation": sum(1 for r in rows if r["ltf"]["state"].startswith("no ")),
                    "missed": sum(1 for r in rows if r["ltf"]["state"].startswith("missed")),
                    "invalidated": sum(1 for r in rows if r["ltf"]["state"].startswith("invalid"))},
        "bias_tf": bias_tf,
        "by_bias": None if bias_bars is None else {
            "aligned": {"sequences": sum(1 for r in rows if r["aligned"] is True),
                        "htf_entry": tally("htf_r", True), "ltf_confirmed": tally("ltf_r", True),
                        "ltf_with_band": tally("band_r", True)},
            "not_aligned": {"sequences": sum(1 for r in rows if r["aligned"] is False),
                            "htf_entry": tally("htf_r", False), "ltf_confirmed": tally("ltf_r", False),
                            "ltf_with_band": tally("band_r", False)},
            "bias_now": bias_at(bias_bars, epoch(now_utc) + 1, SECONDS[bias_tf])[0]},
        "note": ("HTF entry = a limit at the gap with the stop at the ITL / ITH. LTF entry: mode itl = the close of "
                 "the bar where the first LTF ITL (ITH) formed after the touch became known, stop at its low "
                 "(high); mode choch = the close of the LTF CHoCH, stop at the low (high) made in the zone. "
                 "Sequences inside an H1 range box are left out of the comparison unless --include-range. R counts a target "
                 "as its planned R:R and a stop as -1; open trades are left out. A few dozen sequences prove "
                 "nothing. Not financial advice."),
    }


def confirm_zone(lbars, ltf, now_utc, side, lo, hi, htf_stop, target, since_utc, window=36, swing=2, hold=288,
                 rr_band=(1.5, 3.5), buffer=0.0, mode="itl"):
    """A zone the user gives: follow it on the lower timeframe from `since`."""
    lbars = closed_only(lbars, ltf, now_utc)
    start = next((i for i, b in enumerate(lbars) if b["t"] >= epoch(since_utc)), None)
    if start is None:
        raise StructureError("no %s bars after --since" % ltf)
    res = ltf_confirm(lbars, side, lo, hi, htf_stop, target, start, None, window, hold=hold, swing=swing,
                      rr_band=rr_band, buffer=buffer, mode=mode)
    rr = res.get("rr")
    if rr is not None:
        res["rr_band"] = "in band" if rr_band[0] <= rr <= rr_band[1] else (
            "under %.1f" % rr_band[0] if rr < rr_band[0] else "over %.1f" % rr_band[1])
    return {"created_by": "trader-structure", "mode": "confirm-zone", "ltf": ltf, "side": side,
            "zone": [r2(lo), r2(hi)], "htf_stop": r2(htf_stop), "target": r2(target),
            "since": tr_time(lbars[start]["t"]), "last_bar": tr_time(lbars[-1]["t"]), "price": r2(lbars[-1]["c"]),
            "timezone": "Turkey (UTC+3)", "result": res,
            "note": "A CHoCH is a confirmation of intent, not a guarantee. Not financial advice."}


def ltf_line(res):
    st_ = res["state"]
    if st_.startswith("confirmed"):
        if res.get("itl"):
            head = "LTF %s %.2f (made %s)" % ("ITL" if res["entry"] > res["stop"] else "ITH", res["itl"]["level"],
                                             res["itl"]["at"][5:])
        else:
            head = "CHoCH through %.2f" % res["choch_level"]
        line = "%s %s: %s, entry %.2f stop %.2f target %s R:R %s%s%s" % (
            st_, res["at"][5:], head, res["entry"], res["stop"],
            "n/a" if res.get("target") is None else "%.2f" % res["target"],
            "n/a" if res.get("rr") is None else "%.2f" % res["rr"],
            "" if res.get("rr_band") in (None, "in band") else " (%s)" % res["rr_band"],
            ", displacement" if res.get("displacement") else "")
        if res.get("ltf_fvg"):
            line += "; LTF FVG %.2f-%.2f for a limit" % tuple(res["ltf_fvg"])
        if res.get("result"):
            line += " -> %s%s" % (res["result"], (" " + res["result_at"][5:]) if res.get("result_at") else "")
        bd = res.get("band")
        if bd:
            line += "\n               band: %s" % bd["action"]
            if bd.get("result"):
                line += ", target %.2f (%.1fR) -> %s%s" % (bd["target"], bd["rr"], bd["result"],
                                                         (" " + bd["result_at"][5:]) if bd.get("result_at") else "")
        return line
    line = st_
    if res.get("touch"):
        line += " (touched %s)" % res["touch"][5:]
    if res.get("watch") is not None and st_.startswith("touched"):
        line += "; a close %s %.2f confirms" % ("through", res["watch"])
    if res.get("at") and not st_.startswith("touched"):
        line += " %s" % res["at"][5:]
    return line


def render_confirm(doc):
    out = ["%s%s -> %s confirmation, %s to %s (Turkey time), last close %.2f, R:R band %.1f-%.1f" % (
        ("%s bias -> " % doc["bias_tf"]) if doc.get("bias_tf") else "", doc["htf"], doc["ltf"], doc["from"], doc["to"],
        doc["price"], doc["rr_band"][0], doc["rr_band"][1]),
        "Confirmation: %s" % ("an LTF ITL (long) / ITH (short) forming after the touch" if doc.get("mode") == "itl"
                              else "an LTF CHoCH after the touch"), ""]
    if not doc["sequences"]:
        out.append("No HTF sequence in this data.")
    for r in doc["sequences"]:
        h = r["htf_plan"]
        if r.get("in_range"):
            out.append("  [H1 range: not your setup, left out of the comparison]")
        if r.get("bias"):
            out.append("  %s bias %s (%s): %s" % (doc.get("bias_tf"), r["bias"], r["bias_why"],
                                                  "ALIGNED" if r["aligned"] else "against / unclear"))
        out.append("  %-7s known %s zone %.2f-%.2f | HTF: entry %.2f stop %.2f target %.2f R:R %s -> %s" % (
            r["dir"], r["known_at"][5:], r["zone"][0], r["zone"][1], h["entry"], h["stop"], h["target"],
            "n/a" if h["rr"] is None else "%.2f" % h["rr"], h["status"]))
        out.append("          LTF: " + ltf_line(r["ltf"]))
    c = doc["compare"]
    a, b, k = c["htf_entry"], c["ltf_confirmed"], c["ltf_with_band"]
    out += ["", "Compare (closed trades only%s):" % (
        ", %d sequence(s) inside an H1 range left out" % doc["range_excluded"] if doc.get("range_excluded") else ""),
            "  enter at the HTF gap      %d trades, %d won, total %s R, avg %s R" % (
                a["trades"], a["wins"], a["total_r"], a["avg_r"]),
            "  LTF confirm, HTF target   %d trades, %d won, total %s R, avg %s R" % (
                b["trades"], b["wins"], b["total_r"], b["avg_r"]),
            "  LTF confirm + your band   %d trades, %d won, total %s R, avg %s R (%d skipped under %.1f, "
            "targets over %.1fR taken at %.1fR)" % (k["trades"], k["wins"], k["total_r"], k["avg_r"],
                                                   c["skipped_by_band"], doc["rr_band"][0], doc["rr_band"][1],
                                                   doc["rr_band"][1]),
            "  touched %d, confirmed %d, no confirmation %d, invalidated %d, ran to the target untouched %d" % (
                c["touched"], c["confirmed"], c["no_confirmation"], c["invalidated"], c["missed"])]
    bb = doc.get("by_bias")
    if bb:
        out += ["", "Split by the %s bias (bias now: %s):" % (doc["bias_tf"], bb["bias_now"])]
        for key, label in (("aligned", "with the bias"), ("not_aligned", "against / unclear")):
            g = bb[key]
            out.append("  %-18s %d sequence(s)" % (label, g["sequences"]))
            for k2, l2 in (("htf_entry", "HTF entry"), ("ltf_confirmed", "LTF conf."), ("ltf_with_band", "LTF + band")):
                x = g[k2]
                out.append("      %-10s %d trades, %d won, total %s R, avg %s R" % (l2, x["trades"], x["wins"],
                                                                                  x["total_r"], x["avg_r"]))
    if doc["live"]:
        out += ["", "Live now:"]
        for r in doc["live"]:
            out.append("  %s zone %.2f-%.2f: %s" % (r["dir"], r["zone"][0], r["zone"][1], ltf_line(r["ltf"])))
    out += ["", doc["note"]]
    return "\n".join(out)


def render_confirm_zone(doc):
    return "\n".join(["%s zone %.2f-%.2f on %s since %s, HTF stop %.2f, target %s; last close %.2f (%s)" % (
        doc["side"], doc["zone"][0], doc["zone"][1], doc["ltf"], doc["since"], doc["htf_stop"],
        "n/a" if doc["target"] is None else "%.2f" % doc["target"], doc["price"], doc["last_bar"]),
        "  " + ltf_line(doc["result"]), "", doc["note"]])


# ---------------------------------------------------------------- output

def render(doc):
    out = ["%s  %s  %d closed bars, %s to %s (Turkey time)" % (doc["symbol"], doc["interval"], doc["bars"],
                                                                 doc["first_bar"], doc["last_bar"]),
           "Last close %.2f   bias %s" % (doc["price"], doc["bias"]),
           regime_line(doc["regime_now"]),
           "Points: %s" % ", ".join("%s %d" % (k, doc["counts"][k]) for k in
                                    ("LTH", "ITH", "STH", "LTL", "ITL", "STL")), ""]
    for k in ("LTH", "ITH", "LTL", "ITL"):
        ps = doc["points"][k]
        if ps:
            out.append("%s  " % k + "   ".join("%.2f @ %s" % (p["level"], p["at"][5:]) for p in ps))
    liq = doc.get("liquidity")
    if liq:
        out += ["", "Short-term liquidity (STH / STL are fuel price comes back for)"]
        for name in ("STH", "STL", "ITH", "ITL"):
            L = liq[name]
            if not L["points"]:
                continue
            within = ", ".join("%s%% in %s" % (("%.0f" % L[k]), k.split("_")[-1]) for k in
                               ("taken_within_6", "taken_within_12", "taken_within_24", "taken_within_48") if k in L)
            out.append("  %s  %d points, taken: %s bars; median %s bars; %d untaken" % (
                name, L["points"], within or "n/a", "n/a" if L["median_bars_to_take"] is None
                else L["median_bars_to_take"], L["untaken_count"]))
            if L.get("baseline_within_24") is not None and "taken_within_24" in L:
                edge = L["taken_within_24"] - L["baseline_within_24"]
                out.append("        vs any level as far away: %.0f%% in 24 bars, so %s by %+.0f points" % (
                    L["baseline_within_24"], "pulled harder" if edge > 5 else "about the same" if edge > -5
                    else "pulled less", edge))
        for name, word in (("STH", "above"), ("STL", "below")):
            u = [x for x in liq[name]["untaken"]][:3]
            if u:
                out.append("  untaken %s %s: %s" % (name, word, "   ".join(
                    "%.2f (%+.2f%%, %s)" % (x["level"], x["distance_pct"], x["at"][5:]) for x in u)))
    out.append("")
    if not doc["setups"]:
        out.append("No LTL -> ITL -> FVG (or LTH -> ITH -> FVG) sequence in this data.")
    else:
        out.append("Sequences (oldest first; known = when all of it was visible)")
        for s in doc["setups"]:
            p = s["plan"]
            out.append("  %-7s %s %.2f (%s) -> %s %.2f (%s) -> FVG %.2f-%.2f (%s)" % (
                s["dir"], s["lt"]["type"], s["lt"]["level"], s["lt"]["at"][5:], s["it"]["type"], s["it"]["level"],
                s["it"]["at"][5:], s["fvg"]["bottom"], s["fvg"]["top"], s["fvg"]["at"][5:]))
            out.append("          known %s%s  status %s%s  |  entry %.2f stop %.2f target %s R:R %s" % (
                s["known_at"][5:], " [range]" if s.get("in_range_box") else "", s["status"], (" " + s["status_at"][5:]) if s["status_at"] else "",
                p["entry"], p["stop"], "n/a" if p["target"] is None else "%.2f" % p["target"],
                "n/a" if p["reward_risk"] is None else "%.2f" % p["reward_risk"]
                + ("" if p.get("rr_band") in (None, "in band") else " (%s)" % p["rr_band"])))
            if p.get("target1") is not None:
                out.append("          T1 %.2f (%s, R:R %s)%s" % (
                    p["target1"], p["target1_from"], "n/a" if p["rr1"] is None else "%.2f" % p["rr1"],
                    "" if "t1_hit" not in s else ("  hit %s" % s["t1_hit"][5:] if s["t1_hit"] else
                                                  "  not hit before the stop / yet")))
            if p.get("stop_warning"):
                out.append("          ! " + p["stop_warning"])
    rc = doc["record"]
    if rc["sequences"]:
        out += ["", "In this data: %d sequence(s); price came back to the FVG %d time(s): %d target, %d stopped, "
                    "%d still open. %d ran off without a tap, %d invalid before a tap. A handful of cases proves "
                    "nothing." % (rc["sequences"], rc["tapped"], rc["target"], rc["stopped"],
                                  rc["tapped"] - rc["target"] - rc["stopped"], rc["missed"], rc["invalid"])]
    t1r = doc.get("t1_record") or {}
    if t1r.get("with_t1"):
        out.append("T1 (nearest untaken STH / STL) reached after a tap, before the stop: %d of %d"
                   % (t1r["t1_hit"], t1r["with_t1"]))
    if doc.get("by_regime") and len(doc["by_regime"]) > 1:
        out.append("By regime when it became known:")
        for k in sorted(doc["by_regime"]):
            r = doc["by_regime"][k]
            out.append("  %-20s %d sequence(s), %d tapped: %d target, %d stopped"
                       % (k, r["sequences"], r["tapped"], r["target"], r["stopped"]))
    if doc.get("hidden_in_range"):
        out.append("Hidden: %d sequence(s) that formed inside a range box (--skip-range)" % doc["hidden_in_range"])
    if doc["active"]:
        out += ["", "Still live: %d (waiting for price to reach the FVG, or tapped and holding)" % len(doc["active"])]
    out += ["", doc["note"]]
    return "\n".join(out)


def regime_line(r):
    if r.get("state") == "unknown":
        return "Regime: unknown (not enough history for the range filter)"
    bits = ["efficiency %.2f" % r["er"]]
    if r.get("vol_rel") is not None:
        bits.append("volume %.0f %% of normal" % (100 * r["vol_rel"]))
    bits.append("ATR %.0f %% of normal" % (100 * r["atr_rel"]))
    line = "Regime: %s (%s)" % (r["state"], ", ".join(bits))
    if r.get("box"):
        bx = r["box"]
        line += "\n  inside a range box %.2f-%.2f since %s, phase %s%s" % (
            bx["low"], bx["high"], bx["detected"][5:], bx["phase"],
            (", %s raided at %.2f" % (bx["raided"], bx["raid_extreme"])) if bx["raided"] else "")
    return line


def render_range(doc):
    out = ["%s  %s  range / AMD, window %d bars, last bar %s (Turkey time)" % (
        doc["symbol"], doc["interval"], doc["range_window"], doc["last_bar"]),
        "Last close %.2f" % doc["price"], regime_line(doc["now"])]
    if not doc["volume_in_data"]:
        out.append("  (no volume in this data: quiet = ATR under 85 %% of normal instead)")
    if doc["time_in_range_pct"] is not None:
        out.append("Time spent in a range regime in this data: %.0f %%" % doc["time_in_range_pct"])
    bx = doc["now"].get("box")
    if bx and bx.get("plan"):
        p = bx["plan"]
        out += ["", "Live raid: the %s was taken; the AMD read is %s" % (bx["raided"], p["dir"]),
                "  reclaim close %.2f, stop %.2f (past the raid), target %.2f (opposite edge, R:R %s), "
                "then %.2f (one box higher, R:R %s)" % (
                    p["entry"], p["stop"], p["target1"], "n/a" if p["rr1"] is None else "%.2f" % p["rr1"],
                    p["target2"], "n/a" if p["rr2"] is None else "%.2f" % p["rr2"]),
                "  Wait for your own confirmation (a lower-timeframe shift) before acting on it."]
    out += ["", "Recent range boxes (oldest first)"]
    if not doc["boxes"]:
        out.append("  none in this data")
    for b in doc["boxes"]:
        out.append("  %.2f-%.2f (%.2f %%)  from %s, detected %s  ->  %s%s" % (
            b["low"], b["high"], b["height_pct"], b["from"][5:], b["detected"][5:],
            b["outcome"] or "still live (%s)" % b["phase"], (" at " + b["ended"][5:]) if b["ended"] else ""))
        for e in b["events"]:
            out.append("      %s %s%s: %s" % (e["at"][5:], e["type"],
                                             (" @ %.2f" % e["extreme"]) if e["extreme"] is not None else "",
                                             e["how"]))
    rc = doc["record"]
    out += ["", "In this data: %d box(es); %d raided, of which %d completed AMD (opposite edge broke) and %d "
                "failed (the raid kept going); %d broke out with no raid first; %d faded. A handful of boxes "
                "proves nothing." % (rc["boxes"], rc["raided"], rc["amd_complete"], rc["raid_failed"],
                                     rc["breakout_no_raid"], rc["faded"]),
            "", doc["note"]]
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


def load(a):
    """The bars the flags ask for -> (sym, bars, interval, now, resampled)."""
    sym = a.symbol.upper()
    if not re.match(r"^[A-Z0-9.\-^=]{1,20}$", sym):
        raise StructureError("%r does not look like a symbol" % a.symbol)
    interval = a.interval
    if interval not in SECONDS:
        raise StructureError("--interval is one of %s" % ", ".join(SECONDS))
    now = parse_at(a.at)
    if a.offline:
        text = read_text(a.offline)
    elif a.source == "binance":
        want = a.limit or (1000 if a.cmd == "levels" else 720)
        if getattr(a, "days", None):
            want = int(a.days * 86400 // SECONDS[interval])
        text = binance_pages(sym, BINANCE_INTERVAL[interval], want, epoch(now) * 1000 if a.at else None)
    else:
        fetch = a.fetch_interval or ("60m" if interval == "1h" else interval)
        text = http_get("https://query2.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s"
                        % (sym, a.range or YAHOO_RANGE.get(fetch, "60d"), fetch))
    dsym, gran, bars = parse_bars(text, sym)
    if a.source == "yahoo" or a.offline:
        if dsym and dsym != sym and not a.offline:
            raise StructureError("the data is for %s, not %s" % (dsym, sym))
        if a.offline and dsym and dsym != sym:
            raise StructureError("the file holds %s, not %s" % (dsym, sym))
    resampled = False
    if a.resample:
        if a.resample not in SECONDS:
            raise StructureError("--resample is one of %s" % ", ".join(SECONDS))
        cut = epoch(now)
        bars = resample([b for b in bars if b["t"] < cut], a.resample)
        resampled = True
        interval = a.resample
    elif gran and SECONDS.get(gran) and SECONDS[gran] != SECONDS[interval]:
        raise StructureError("the data has %s bars, not %s: pass --interval %s or --resample %s"
                             % (gran, interval, gran, interval))
    if not 6 <= a.range_window <= 200:
        raise StructureError("--range-window must be between 6 and 200 bars")
    return sym, bars, interval, now, resampled


def cmd_scan(a):
    sym, bars, interval, now, resampled = load(a)
    doc = analyze(sym, bars, interval, now, a.window, min_gap_pct=a.min_gap, resampled=resampled,
                  range_window=a.range_window, skip_range=a.skip_range, rr_band=(a.rr_min, a.rr_max))
    if a.write:
        write_json(a.write, doc)
    return json.dumps(doc, indent=2) if a.json else render(doc)


def cmd_range(a):
    sym, bars, interval, now, resampled = load(a)
    doc = analyze_range(sym, bars, interval, now, resampled, a.range_window, a.reclaim)
    if a.write:
        write_json(a.write, doc)
    return json.dumps(doc, indent=2) if a.json else render_range(doc)


def cmd_levels(a):
    sym, bars, interval, now, resampled = load(a)
    doc = key_levels(sym, bars, interval, now, a.calendar, resampled, a.reclaim)
    if a.write:
        write_json(a.write, doc)
    return json.dumps(doc, indent=2) if a.json else render_levels(doc)


def cmd_confirm(a):
    if a.ltf not in SECONDS or a.htf not in SECONDS:
        raise StructureError("--ltf and --htf are one of %s" % ", ".join(SECONDS))
    a.interval = a.data_interval or a.ltf
    if a.interval != a.ltf:
        a.resample = a.ltf                       # build the LTF bars from smaller data
    if a.source == "binance" and not a.offline and a.days is None:
        a.days = 30.0
    sym, bars, interval, now, _ = load(a)
    per_hour = 3600.0 / SECONDS[a.ltf]
    a.window = a.window or max(4, int(round((12 if a.mode == "itl" else 3) * per_hour)))   # 12 h for an ITL, 3 h for a CHoCH
    a.hold = a.hold or int(round(24 * per_hour))                     # one day
    band = (a.rr_min, a.rr_max)
    bias_bars = None
    if a.bias_tf and a.bias_tf.lower() != "none":
        if a.bias_tf not in SECONDS or SECONDS[a.bias_tf] <= SECONDS[a.htf]:
            raise StructureError("--bias-tf must be a bigger bar than --htf (1d, 4h) or none")
        if a.bias_offline:
            _, _, bias_bars = parse_bars(read_text(a.bias_offline), sym)
        elif a.offline:
            bias_bars = resample(bars, a.bias_tf)                # from the same file: short history
        elif a.source == "binance":
            bias_bars = parse_bars(binance_pages(sym, BINANCE_INTERVAL[a.bias_tf], 400,
                                                 epoch(now) * 1000 if a.at else None), sym)[2]
        else:
            bias_bars = parse_bars(http_get("https://query2.finance.yahoo.com/v8/finance/chart/%s?range=2y&interval=%s"
                                            % (sym, "1d" if a.bias_tf == "1d" else "60m")), sym)[2]
            if a.bias_tf != "1d":
                bias_bars = resample(bias_bars, a.bias_tf)
    else:
        a.bias_tf = None
    if a.zone:
        m = re.match(r"^\s*([0-9.]+)\s*-\s*([0-9.]+)\s*$", a.zone)
        if not m or a.side is None or a.stop is None:
            raise StructureError("a manual zone needs --zone LOW-HIGH, --side long|short and --stop PRICE")
        lo, hi = sorted((float(m.group(1)), float(m.group(2))))
        since = parse_at(a.since) if a.since else now - datetime.timedelta(days=1)
        doc = confirm_zone(bars, a.ltf, now, a.side, lo, hi, a.stop, a.target, since, a.window, a.swing,
                           a.hold, band, a.buffer, a.mode)
        out = render_confirm_zone(doc)
    else:
        doc = confirm_sequences(bars, a.ltf, a.htf, now, a.window, a.swing, a.hold, band, buffer=a.buffer,
                                bias_bars=bias_bars, bias_tf=a.bias_tf, mode=a.mode,
                                include_range=a.include_range, range_window=a.range_window)
        out = render_confirm(doc)
    doc["symbol"] = sym
    if a.write:
        write_json(a.write, doc)
    return json.dumps(doc, indent=2) if a.json else out


def build_parser():
    ap = argparse.ArgumentParser(description="Advanced market structure: STH/ITH/LTH, STL/ITL/LTL and the "
                                             "LTL -> ITL -> FVG sequence.")
    sub = ap.add_subparsers(dest="cmd")
    def common(p, default_out):
        p.add_argument("symbol", help="NQ=F, ES=F, ^NDX, BTC-USD (Yahoo) or BTCUSDT (Binance), XU100.IS ...")
        p.add_argument("--source", choices=["yahoo", "binance"], default="yahoo")
        p.add_argument("--interval", default="1h", help="1h (default), 4h, 1d, 15m, 5m ...")
        p.add_argument("--range", help="Yahoo range (default 60d intraday, 2y daily)")
        p.add_argument("--fetch-interval", help="Yahoo bar size to download (default: --interval)")
        p.add_argument("--limit", type=int, help="Binance bars to fetch (default 720; 1000 for levels; max 1000)")
        p.add_argument("--resample", help="build bigger bars from the data first, e.g. 5m data -> 1h")
        p.add_argument("--range-window", type=int, default=24,
                       help="bars the range filter looks at (default 24; its long average uses 5x that)")
        p.add_argument("--at", help="as of this Turkey time, only bars closed by then")
        p.add_argument("--offline", help="a saved Yahoo chart JSON or Binance klines JSON (.json or .json.gz)")
        p.add_argument("--json", action="store_true")
        p.add_argument("--write", nargs="?", const=default_out, metavar="PATH",
                       help="save the result (default %s)" % default_out)

    p = sub.add_parser("scan", help="classify the structure and list the sequences")
    common(p, "trader/structure.json")
    p.add_argument("--window", type=int, default=24,
                   help="bars after the ITL/ITH in which the FVG must appear (default 24)")
    p.add_argument("--min-gap", type=float, default=0.0, help="ignore FVGs smaller than this percent")
    p.add_argument("--skip-range", action="store_true", help="hide sequences that formed inside a range box")
    p.add_argument("--rr-min", type=float, default=1.5, help="the low end of your reward:risk band (default 1.5)")
    p.add_argument("--rr-max", type=float, default=3.5, help="the high end of your reward:risk band (default 3.5)")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("range", help="range / AMD: is the market ranging, was an edge raided, did AMD complete")
    common(p, "trader/range.json")
    p.add_argument("--reclaim", type=int, default=3,
                   help="bars a close outside the box may last and still count as a raid (default 3)")
    p.set_defaults(fn=cmd_range)

    p = sub.add_parser("confirm", help="lower-timeframe confirmation: HTF zone touched, then an LTF CHoCH")
    common(p, "trader/confirm.json")
    p.set_defaults(interval=None)
    p.add_argument("--ltf", default="15m", help="the confirmation timeframe (default 15m)")
    p.add_argument("--htf", default="1h", help="the timeframe of the zones (default 1h, built from the LTF data)")
    p.add_argument("--mode", choices=["itl", "choch"], default="itl",
                   help="the LTF confirmation: itl (default: an LTF ITL / ITH forming after the touch) or choch")
    p.add_argument("--include-range", action="store_true",
                   help="keep sequences that formed inside an H1 range box in the comparison")
    p.add_argument("--bias-tf", default="1d", help="the bias timeframe (default 1d; none to switch it off)")
    p.add_argument("--bias-offline", help="a saved chart file for the bias timeframe (offline runs)")
    p.add_argument("--data-interval", help="the bar size of the data when smaller than --ltf (e.g. 5m)")
    p.add_argument("--days", type=float, help="Binance: days of LTF history to fetch in pages (default 30)")
    p.add_argument("--window", type=int,
                   help="LTF bars after the touch to wait for the confirmation (default: 12 hours itl, 3 hours choch)")
    p.add_argument("--swing", type=int, default=2, help="LTF swing size in bars each side (default 2)")
    p.add_argument("--hold", type=int, help="LTF bars to follow a confirmed trade (default: one day)")
    p.add_argument("--rr-min", type=float, default=1.5)
    p.add_argument("--rr-max", type=float, default=3.5)
    p.add_argument("--buffer", type=float, default=0.0,
                   help="put the stop this many LTF ATRs past the LTF low / high (default 0)")
    p.add_argument("--zone", help="your own zone instead of the HTF sequences: LOW-HIGH")
    p.add_argument("--side", choices=["long", "short"])
    p.add_argument("--stop", type=float, help="the zone's invalidation (HTF stop)")
    p.add_argument("--target", type=float)
    p.add_argument("--since", help="Turkey time to start watching the zone (default one day back)")
    p.set_defaults(fn=cmd_confirm)

    p = sub.add_parser("levels", help="key levels: day / week / month opens and ranges, the Monday range")
    common(p, "trader/levels.json")
    p.add_argument("--calendar", choices=sorted(CALENDARS),
                   help="period rules (default from the symbol: USDT / -USD crypto, =F cme, .IS bist, else stock)")
    p.add_argument("--reclaim", type=int, default=3,
                   help="bars a close beyond a level must hold to count as accepted, not swept (default 3)")
    p.set_defaults(fn=cmd_levels)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    if getattr(a, "limit", None) is not None and not 1 <= a.limit <= 1000:
        print("structure: --limit must be between 1 and 1000", file=sys.stderr)
        return 1
    try:
        print(a.fn(a))
    except StructureError as e:
        print("structure: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

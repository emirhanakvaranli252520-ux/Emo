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
            out.append(s)
    out.sort(key=lambda s: s["_known"])
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


def analyze(sym, bars, interval, now_utc, window=24, recent=5, min_gap_pct=0.0, resampled=False):
    bars = closed_only(bars, interval, now_utc, resampled)
    if len(bars) < 20:
        raise StructureError("only %d closed bar(s) of %s by then: need at least 20" % (len(bars), sym))
    t = tiers(bars)
    gaps = fvgs(bars)
    setups = scan_setups(bars, t, gaps, window, min_gap_pct)

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
        "active": [{k: v for k, v in s.items() if not k.startswith("_")} for s in active][-5:],
        "note": ("Structure points and setups are a way to read the chart, not a signal and not financial "
                 "advice. Every setup still needs your own confirmation, a stop, the risk check and your yes. "
                 "Range / AMD filtering is not applied yet: a setup inside a low-volume range is weaker."),
    }


# ---------------------------------------------------------------- output

def render(doc):
    out = ["%s  %s  %d closed bars, %s to %s (Turkey time)" % (doc["symbol"], doc["interval"], doc["bars"],
                                                                 doc["first_bar"], doc["last_bar"]),
           "Last close %.2f   bias %s" % (doc["price"], doc["bias"]),
           "Points: %s" % ", ".join("%s %d" % (k, doc["counts"][k]) for k in
                                    ("LTH", "ITH", "STH", "LTL", "ITL", "STL")), ""]
    for k in ("LTH", "ITH", "LTL", "ITL"):
        ps = doc["points"][k]
        if ps:
            out.append("%s  " % k + "   ".join("%.2f @ %s" % (p["level"], p["at"][5:]) for p in ps))
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
            out.append("          known %s  status %s%s  |  entry %.2f stop %.2f target %s R:R %s" % (
                s["known_at"][5:], s["status"], (" " + s["status_at"][5:]) if s["status_at"] else "",
                p["entry"], p["stop"], "n/a" if p["target"] is None else "%.2f" % p["target"],
                "n/a" if p["reward_risk"] is None else "%.2f" % p["reward_risk"]))
    rc = doc["record"]
    if rc["sequences"]:
        out += ["", "In this data: %d sequence(s); price came back to the FVG %d time(s): %d target, %d stopped, "
                    "%d still open. %d ran off without a tap, %d invalid before a tap. A handful of cases proves "
                    "nothing." % (rc["sequences"], rc["tapped"], rc["target"], rc["stopped"],
                                  rc["tapped"] - rc["target"] - rc["stopped"], rc["missed"], rc["invalid"])]
    if doc["active"]:
        out += ["", "Still live: %d (waiting for price to reach the FVG, or tapped and holding)" % len(doc["active"])]
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


def cmd_scan(a):
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
        end = "&endTime=%d" % (epoch(now) * 1000) if a.at else ""
        text = http_get("https://api.binance.com/api/v3/klines?symbol=%s&interval=%s&limit=%d%s"
                        % (sym, BINANCE_INTERVAL[interval], a.limit, end))
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
    doc = analyze(sym, bars, interval, now, a.window, min_gap_pct=a.min_gap, resampled=resampled)
    if a.write:
        write_json(a.write, doc)
    return json.dumps(doc, indent=2) if a.json else render(doc)


def build_parser():
    ap = argparse.ArgumentParser(description="Advanced market structure: STH/ITH/LTH, STL/ITL/LTL and the "
                                             "LTL -> ITL -> FVG sequence.")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("scan", help="classify the structure and list the sequences")
    p.add_argument("symbol", help="NQ=F, ES=F, ^NDX, BTC-USD (Yahoo) or BTCUSDT (Binance), XU100.IS ...")
    p.add_argument("--source", choices=["yahoo", "binance"], default="yahoo")
    p.add_argument("--interval", default="1h", help="1h (default), 4h, 1d, 15m, 5m ...")
    p.add_argument("--range", help="Yahoo range (default 60d intraday, 2y daily)")
    p.add_argument("--fetch-interval", help="Yahoo bar size to download (default: --interval)")
    p.add_argument("--limit", type=int, default=720, help="Binance bars to fetch (default 720, max 1000)")
    p.add_argument("--resample", help="build bigger bars from the data first, e.g. 5m data -> 1h")
    p.add_argument("--window", type=int, default=24,
                   help="bars after the ITL/ITH in which the FVG must appear (default 24)")
    p.add_argument("--min-gap", type=float, default=0.0, help="ignore FVGs smaller than this percent")
    p.add_argument("--at", help="as of this Turkey time, only bars closed by then")
    p.add_argument("--offline", help="a saved Yahoo chart JSON or Binance klines JSON (.json or .json.gz)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--write", nargs="?", const="trader/structure.json", metavar="PATH",
                   help="save the result (default trader/structure.json)")
    p.set_defaults(fn=cmd_scan)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    if getattr(a, "limit", 1) < 1 or getattr(a, "limit", 1) > 1000:
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

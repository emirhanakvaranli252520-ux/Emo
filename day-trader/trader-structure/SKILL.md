---
name: trader-structure
description: >-
  Advanced Market Structure. Classifies swing points in three tiers on both
  sides: short-term (STH / STL), intermediate-term (ITH / ITL: a short-term
  point with lower highs, or higher lows, on each side) and long-term (LTH /
  LTL: the same rule one tier up), each with the bar at which it became
  knowable, so nothing looks ahead. Gives the bias from the last two ITH and
  ITL (higher highs and higher lows, or lower and lower), and scans for the
  sequence LTL -> higher ITL -> bullish fair value gap (and LTH -> lower ITH
  -> bearish FVG), with the entry at the gap, the stop at the ITL / ITH, the
  target at the nearest untaken opposite liquidity, and what happened after.
  Works on US index futures (NQ=F, ES=F), crypto majors (Binance BTCUSDT or
  Yahoo BTC-USD), stocks and BIST, on H1 by default, in Turkey time. Use when
  the user says "market structure", "ITH", "ITL", "LTH", "LTL", "STH", "STL",
  "intermediate term high", "long term low", "yapı", "piyasa yapısı",
  "LTL'den sonra ITL", "H1 yapı", or wants the structure on NQ, ES, BTC, ETH
  or a BIST stock.
argument-hint: "SYMBOL [--source yahoo|binance] [--interval 1h|4h|1d] [--at TIME]"
---

# trader-structure

ICT's advanced market structure ranks swing points by how much of the chart
they control. A short-term high is any three-bar pivot. An intermediate-term
high is a short-term high with a lower short-term high on each side. A
long-term high is an intermediate-term high with a lower intermediate-term
high on each side. Lows mirror that. This skill draws those tiers from real
bars and looks for the sequence the user trades: a long-term low, then a
higher intermediate-term low, then a fair value gap left by the move up (and
the bearish mirror). It is a way to read the chart, not a proven edge, and
not financial advice. Day trading loses most people money.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/structure.py" scan BTCUSDT --source binance            # H1, last 720 hours
python3 "${CLAUDE_SKILL_DIR}/structure.py" scan ETHUSDT --source binance --interval 4h
python3 "${CLAUDE_SKILL_DIR}/structure.py" scan NQ=F                                # Nasdaq-100 futures, H1, 60 days
python3 "${CLAUDE_SKILL_DIR}/structure.py" scan ES=F --at "2026-11-20 18:00"        # as it looked then, Turkey time
python3 "${CLAUDE_SKILL_DIR}/structure.py" scan XU100.IS --interval 1d --range 2y
python3 "${CLAUDE_SKILL_DIR}/structure.py" scan BTCUSDT --source binance --json --write   # trader/structure.json
```

Other flags: `--window 24` (bars after the ITL / ITH in which the FVG must
form), `--min-gap 0.05` (ignore gaps smaller than that percent),
`--resample 1h` (build H1 from smaller bars), `--offline FILE` (a saved Yahoo
chart JSON or Binance klines JSON), `--limit` (Binance bars, up to 1000).

## Symbols

| market | Yahoo (`--source yahoo`, default) | Binance (`--source binance`) |
| --- | --- | --- |
| Nasdaq-100 / S&P 500 futures | `NQ=F`, `ES=F` | |
| the indices themselves | `^NDX`, `^GSPC`, `^DJI` | |
| crypto majors | `BTC-USD`, `ETH-USD`, `SOL-USD` | `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (better: real 24/7 exchange bars) |
| BIST | `XU100.IS`, `THYAO.IS` ... | |

Prop-firm CFD prices can differ a little from these feeds: compare a level
with the platform before acting on it.

## The rules, exactly

| point | rule | known when |
| --- | --- | --- |
| STH / STL | high above both neighbours' highs (low below both lows); ties are not pivots | the next bar closes |
| ITH / ITL | an STH with a lower STH right before and right after it (an STL with higher STLs) | the next STH / STL is known |
| LTH / LTL | an ITH with lower ITHs on each side (an ITL with higher ITLs) | the next ITH / ITL is known |
| bias | last two ITHs and ITLs: both higher = bullish, both lower = bearish, else mixed | |
| sequence | an LTL, the first higher ITL after it, then a bullish FVG within `--window` bars of that ITL, with no close under the ITL before the gap (bearish mirror) | when all three are known |
| plan | entry at the gap's near edge, stop at the ITL / ITH, target at the nearest ITH / LTH (ITL / LTL) that was known and not yet traded through; 2R when there is none | |
| status | waiting, then tapped (price reached the gap), then target or stopped; invalid (closed through the ITL before a tap), missed (reached the target without a tap) | |

Only closed bars are read. A setup's status is followed bar by bar after it
became known; a bar that touches both stop and target counts as stopped.

## Steps

1. Run `scan` on the symbol (H1 unless the user asks otherwise).
2. Say the bias and the last LTL / LTH and ITL / ITH in one or two lines,
   with Turkey times.
3. Name any live sequence (waiting or tapped): the zone, the stop, the
   target and the reward:risk. A reward:risk under 1 is not worth it; say so.
4. Say the record in the data ("8 sequences, 3 target, 3 stopped") and that a
   handful of cases proves nothing.
5. Not applied yet: the range / AMD filter (a setup inside a low-volume
   range is weaker) and lower-timeframe confirmation. Say so when it matters.
6. To take one: the user confirms on the lower timeframe, then the stop and
   size go through `/trader-budget` and `/trader-risk`, and the trade is
   logged in `/trader-journal` with the tag `ith-ltl` so its record builds up.

## What it reads and writes

| file | what |
| --- | --- |
| Yahoo chart API, Binance klines API | the bars, free (Binance's public market data needs no key) |
| `trader/structure.json` | with `--write`: the points, the bias, the sequences and their record |

## Rules

- **Never call a sequence a signal.** It is a zone to watch. The entry needs
  the user's own confirmation, a stop, the risk check and the user's yes.
- **Say the data and the time zone.** Name the feed, the interval and the
  last bar, in Turkey time.
- **Not financial advice.** Nothing here places an order.

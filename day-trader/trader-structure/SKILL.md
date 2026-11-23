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
  Its range / AMD filter says when the market is ranging (low efficiency,
  volume under normal, both edges visited), flags sequences that formed
  inside a range, and follows each range box through power of three: the
  raid of one edge (manipulation) and the break of the other (distribution).
  Its key levels give the day, week and month opens, the previous day, week
  and month high, low and equilibrium (taken or not, swept or accepted), the
  Monday range and which side of it went first, the New York midnight open
  for CME futures, and where price sits in each range (premium or discount),
  on the right calendar for crypto, CME futures, US stocks or BIST. It treats
  untaken STH / STL as fuel: how fast this chart takes them against a random
  baseline, the nearest untaken ones, a first target (T1) at the nearest one,
  and a warning when a stop sits inside that liquidity. Its lower-timeframe
  confirmation follows each H1 zone on M5: the touch, then a CHoCH, with the
  entry at the CHoCH close, the stop at the low made in the zone, the user's
  1.5-3.5 reward:risk band applied, and a comparison of waiting for the
  CHoCH against entering at the H1 gap.
  Works on US index futures (NQ=F, ES=F), crypto majors (Binance BTCUSDT or
  Yahoo BTC-USD), stocks and BIST, on H1 by default, in Turkey time. Use when
  the user says "market structure", "ITH", "ITL", "LTH", "LTL", "STH", "STL",
  "intermediate term high", "long term low", "yapı", "piyasa yapısı",
  "LTL'den sonra ITL", "H1 yapı", "range", "AMD", "PO3", "power of three",
  "manipulation", "yatay piyasa", "range piyasası", "likidite avı", "key levels",
  "Monday range", "weekly range", "monthly range", "weekly open", "monthly
  open", "PWH", "PWL", "PDH", "midnight open", "premium discount", "açılış
  seviyesi", "haftalık range", "aylık range", "untaken highs", "STH
  liquidity", "yakıt", "alınmamış tepe", "STL likidite", "confirmation", "konfirmasyon", "alt zaman dilimi",
  "M5 CHoCH", "lower timeframe", "giriş onayı", or wants the structure on NQ, ES, BTC, ETH
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
python3 "${CLAUDE_SKILL_DIR}/structure.py" scan NQ=F --skip-range                   # hide sequences formed inside a range
python3 "${CLAUDE_SKILL_DIR}/structure.py" range BTCUSDT --source binance           # range / AMD: is it ranging, was an edge raided
python3 "${CLAUDE_SKILL_DIR}/structure.py" range NQ=F --range-window 36 --reclaim 2
python3 "${CLAUDE_SKILL_DIR}/structure.py" levels BTCUSDT --source binance          # opens, PDH/PWH/PMH, Monday range
python3 "${CLAUDE_SKILL_DIR}/structure.py" levels NQ=F                              # CME calendar + NY midnight open
python3 "${CLAUDE_SKILL_DIR}/structure.py" levels THYAO.IS --calendar bist
python3 "${CLAUDE_SKILL_DIR}/structure.py" confirm NQ=F                             # 1D bias -> H1 zones -> 15m ITL / ITH (Yahoo, 60 days)
python3 "${CLAUDE_SKILL_DIR}/structure.py" confirm NQ=F --mode choch                # the CHoCH variant, for comparison
python3 "${CLAUDE_SKILL_DIR}/structure.py" confirm NQ=F --ltf 5m --bias-tf none       # H1 -> M5, no daily filter
python3 "${CLAUDE_SKILL_DIR}/structure.py" confirm BTCUSDT --source binance --days 30
python3 "${CLAUDE_SKILL_DIR}/structure.py" confirm ES=F --zone 6010-6018 --side long --stop 6000 --target 6060 --since "2026-11-24 16:30"
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

## STH / STL are fuel

Short-term highs and lows are where stops sit, and price tends to come back
for them. `scan` treats them that way:

- **Liquidity map.** For STH, STL, ITH and ITL on this chart: what share was
  taken (a later bar traded through it) within 6, 12, 24 and 48 bars of
  becoming known, the median bars to take, and the untaken ones nearest the
  price (the fuel still on the chart).
- **Baseline.** Next to each 24-bar rate: how often ANY level the same
  distance away gets reached within 24 bars, from any bar. If STHs are taken
  no more often than that, the chart is not showing a special pull toward
  them; if more, it is. Say this comparison out loud: it is the honest test.
- **T1.** Every sequence's plan gets a first target at the nearest untaken
  STH (bullish) or STL (bearish) between the entry and the main target, with
  its R:R, and whether it was reached after the tap before the stop.
- **Stop warning.** When an untaken STL sits under a long's stop (or an STH
  over a short's) within a quarter of the risk, the stop is inside that
  liquidity: a run on it takes the stop too. The warning gives the price one
  tick past it.

## Lower-timeframe confirmation

The user's day-trading chain is **1D bias -> 1H zone -> 15m confirmation**,
and that is the default. `confirm` takes the lower-timeframe data (`--ltf`,
default 15m; `--data-interval 5m` builds it from smaller bars), builds the H1
bars from it (`--htf`), finds the LTL -> ITL -> FVG sequences there, tags
each with the daily bias at that moment (`--bias-tf 1d`: the last two daily
ITH / ITL, or STH / STL when there are not enough, from closed daily bars
only; `none` switches it off), and follows each one on the lower timeframe
from the moment it became known. The window defaults to three hours of
bars for a CHoCH, twelve hours for an ITL, and the hold to one day. The summary is split into sequences with the
daily bias and against it (or unclear), so the user sees whether the filter
helps. In the table below, "M5" means the lower timeframe:

| step | rule |
| --- | --- |
| mode | **itl (default, the user's way):** after the touch, the first LTF ITL (long) / ITH (short) whose low (high) formed at or after the touch; it confirms when it becomes known (its right-hand STL / STH is confirmed); entry at that bar's close, stop at the ITL low. **choch:** the CHoCH below. The user does not use CHoCH: use itl unless asked |
| range | sequences that formed inside an H1 range box are left out of the comparison (the user's rule is for trending markets); `--include-range` keeps them |
| touch | the first M5 bar that reaches the H1 gap (a long: a low at or under its top); if price reaches the H1 target first, the setup is missed and not watched further |
| invalidation | an M5 close through the H1 stop (the ITL / ITH) before or after the touch |
| CHoCH | after the touch, an M5 close through the last M5 swing high (`--swing` bars each side) that came before the low made in the zone, within `--window` bars (36 = 3 hours on M5); mirror for shorts |
| plan | entry at the CHoCH close; stop at the low made in the zone (plus `--buffer` x M5 ATR, since that low is itself short-term liquidity); target the H1 target; displacement noted (a CHoCH body over one ATR, or an M5 FVG in the move, also given as a limit-entry zone) |
| your band | R:R under `--rr-min` (1.5): skip; over `--rr-max` (3.5): take profit at 3.5R; in between: the H1 target |
| result | stop or target first on M5 within `--hold` bars (288 = one day); a bar touching both is stopped |

The summary compares, on the same sequences: entering at the H1 gap with
the H1 stop, waiting for the M5 CHoCH with the H1 target, and the CHoCH
with the band rules. Read it out: it tells the user whether waiting for
confirmation helped on that market. `Live now` lists the zones being
watched, with the M5 level a close must cross to confirm.

`--zone LOW-HIGH --side long|short --stop X [--target Y] [--since TIME]`
follows the user's own zone instead (a key level, an order block, a range
edge after a raid).

Data: Yahoo keeps 5m bars for 60 days; on Binance `--days` (default 30)
fetches them in pages of 1000.

## Range and AMD (power of three)

A sequence that forms while the market is ranging on thin volume is weaker:
there the play is the raid, not the breakout. `range` reads that, and `scan`
marks every sequence with the regime it formed in (`[range]` when inside a
box) and splits its record by regime.

| piece | rule (from that bar and the ones before it only) |
| --- | --- |
| range | over the last `--range-window` bars (24): efficiency ratio (net move / total path) under 0.3, volume under 80 % of its average over 5 windows (no volume in the data: ATR under 85 % of its average instead), and both the window's high and low visited at least twice |
| trend / mixed | efficiency 0.5 or more is trend; anything else is mixed |
| accumulation | the box: the window's high and low, frozen when the regime first says range |
| manipulation | a raid of one edge: a wick through it that closes back inside, or closes outside that come back inside within `--reclaim` bars (3). The raid's extreme is kept and extended while it holds |
| distribution | after a raid, a close beyond the OPPOSITE edge: AMD complete, in the direction away from the raid |
| other endings | breakout (stayed outside `--reclaim` bars with no raid first), failed (closed beyond the raid's extreme: a real move), faded (nothing in 5 windows) |
| AMD read | after a raid of the low: long from the reclaim close, stop at the raid's low, first target the box high, second one box height above it (mirror after a raid of the high) |

## Key levels

`levels` lists every level above and below the last close, nearest first,
with its distance:

| code | level |
| --- | --- |
| DO, WO, MO | the day, week and month open (first bar of the period) |
| PDH / PDL / PDEQ | previous day high, low, and their midpoint |
| PWH / PWL / PWEQ | previous week high, low, midpoint |
| PMH / PML / PMEQ | previous month high, low, midpoint |
| MH / ML / MEQ | this week's Monday high, low, midpoint ("forming" while Monday trades) |
| MNO | New York midnight open, CME futures only (ICT's true day open) |

For each previous high and low, and for the Monday high and low, it says
whether price has traded through it since, when, and how: **swept** (no
close beyond, or back on the near side within `--reclaim` bars) or
**accepted** (still closed beyond it `--reclaim` - 1 bars later). For the
Monday range it says which side went first. It also places the price in the
previous week's, previous month's and Monday's range: above 50 % premium,
under 50 % discount, or outside the range.

Calendars (picked from the symbol, or `--calendar`):

| calendar | day | week | used for |
| --- | --- | --- | --- |
| crypto | 00:00 UTC (03:00 Turkey) | Monday 00:00 UTC | `BTCUSDT`, `BTC-USD` |
| cme | 18:00 New York the evening before | Sunday 18:00 New York | `NQ=F`, `ES=F` |
| stock | New York calendar day | Monday | US stocks, `^NDX` |
| bist | Istanbul calendar day | Monday | `.IS` |

When the data starts inside a period, its open is not given and the
previous period's high and low are flagged partial. Binance's 1000-bar cap
on H1 is about 41 days, so the previous month can be partial early in a
month: say so.

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
5. Say the regime now. If a range box is live, name its edges and phase;
   if an edge was raided, give the AMD read with its R:R, and say the user
   waits for their own confirmation. A `[range]` sequence is not the trade:
   the raid is. For the entry itself, use `confirm`.
6. Read the liquidity map: the nearest untaken STH above and STL below, how
   fast this chart takes them, and how that compares with the baseline. Give
   T1 with every live sequence and repeat any stop warning.
7. For key levels, lead with where price sits (premium or discount of the
   previous week and the Monday range) and the nearest level above and
   below, then any level taken today and whether it was swept or accepted.
6. To take one: the user confirms on the lower timeframe, then the stop and
   size go through `/trader-budget` and `/trader-risk`, and the trade is
   logged in `/trader-journal` with the tag `ith-ltl` so its record builds up.

## What it reads and writes

| file | what |
| --- | --- |
| Yahoo chart API, Binance klines API | the bars, free (Binance's public market data needs no key) |
| `trader/structure.json` | `scan --write`: the points, the bias, the regime, the sequences and their record |
| `trader/range.json` | `range --write`: the regime now, the range boxes, their raids and outcomes |
| `trader/confirm.json` | `confirm --write`: each zone's M5 state, plan, result and the comparison |
| `trader/levels.json` | `levels --write`: the key levels, the Monday range and the premium / discount read |

## Rules

- **Never call a sequence a signal.** It is a zone to watch. The entry needs
  the user's own confirmation, a stop, the risk check and the user's yes.
- **Say the data and the time zone.** Name the feed, the interval and the
  last bar, in Turkey time.
- **Not financial advice.** Nothing here places an order.

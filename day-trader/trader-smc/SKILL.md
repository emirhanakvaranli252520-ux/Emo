---
name: trader-smc
description: >-
  Smart Money Levels. Maps a stock's price structure the way smart money
  concepts (SMC / ICT) traders read it: confirmed swing highs and lows, break
  of structure (BOS) and change of character (CHoCH) with the trend they leave,
  fair value gaps (open, touched, filled), active order blocks, equal highs
  and equal lows where stops pool (swept or not), and the prior day's high and
  low. Lists the nearest support under the price and resistance over it, then
  gives a long-side reading: a level for /trader-entry (--setup level) and a
  stop for /trader-exit (--stop price:X), with the reward:risk to the next
  level. Free Yahoo bars, closed bars only, no look-ahead. Use when the user
  says "smart money", "SMC", "ICT", "order blocks", "fair value gap", "FVG",
  "break of structure", "BOS", "CHoCH", "liquidity sweep", "equal highs",
  "where is support", "key levels", "destek direnç", "likidite", or after
  /trader-scanner, before /trader-entry.
argument-hint: "TICKER [--interval 5m|15m|1d] [--swing 5] [--at TIME]"
---

# trader-smc

Smart money concepts are a vocabulary for price structure: where the last
swing was, whether price has broken it, where it left a gap, where stops
probably sit. This skill draws that map from real bars so the user does not
have to eyeball it, and hands the levels to the rest of the pack. It is a
way of reading a chart, not a proven edge: nobody has shown these levels
predict anything on their own. Day trading loses most people money, and a
tidy map does not change that.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/smc.py" levels TSLA                     # 5-minute bars, last 5 days, swing 5
python3 "${CLAUDE_SKILL_DIR}/smc.py" levels TSLA --interval 15m --swing 3
python3 "${CLAUDE_SKILL_DIR}/smc.py" levels TSLA --interval 1d --range 1y --swing 3
python3 "${CLAUDE_SKILL_DIR}/smc.py" levels TSLA --at "2026-10-19 10:15" --offline chart.json.gz
python3 "${CLAUDE_SKILL_DIR}/smc.py" levels TSLA --json --write      # also trader/smc.json
```

Other flags: `--tolerance 0.1` (percent apart that still counts as equal
highs / lows), `--range` (any Yahoo range: 5d, 1mo, 60d, 1y).

## What it finds

| concept | rule |
| --- | --- |
| swing high / low | a high above the N bars before it and not below the N after (mirror for lows). Known only N bars later: it is never used before then |
| BOS / CHoCH | a CLOSE through the last confirmed, unbroken swing. With the trend (or no trend yet) it is a BOS; against it, a CHoCH, and the trend flips |
| fair value gap | three bars where bar 1's high is under bar 3's low (bullish, bar 2 green) or bar 1's low over bar 3's high (bearish, bar 2 red). Touched when price trades back into it, filled when it trades through it. Filled gaps are dropped |
| order block | at each break, the lowest-low candle between the broken swing and the break (bullish) or the highest-high one (bearish). Active until a close through the far side |
| equal highs / lows | two or more swings within the tolerance before price ran past them: where stops cluster. Swept once a later bar trades beyond them |
| prior day | the previous session's high and low (intraday bars only) |

The rules follow the open-source
[smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts)
library (MIT), rebuilt in the standard library with two fixes for live use:
that library confirms swings with bars that come after them and marks the
last bar of the data as a swing, which shows levels that did not exist yet.
Here a swing counts only once its N later bars have closed, and only closed
bars are read (a forming bar would move every level). The library also
merges back-to-back swings of one kind into the more extreme one, which can
erase a swing that was already broken because of a later bar; here every
confirmed swing stays.

## Steps

1. Run `levels` on the ticker (after `/trader-scanner` and `/trader-news`).
2. Say the trend and the last break in one line ("trend up since a bullish
   CHoCH through 353.04 at 3:50 PM Friday").
3. Read out the nearest one or two resistances and supports with their
   distance, not the whole list.
4. Give the long-side reading. When the trend is not up, say so plainly: no
   long setup here. When reward:risk to the next level is under 1, say the
   risk check will block it.
5. If the user wants it, hand the level on: `/trader-entry check TICKER
   --setup level --level X`, then `/trader-exit plan --setup level --stop
   price:Y`, then `/trader-timemachine` to see how often such a plan worked on
   this stock's own bars. After the trade, `/trader-journal note --tag smc` so
   the journal can tell whether these levels earn their keep.

## What it reads and writes

| file | what |
| --- | --- |
| Yahoo chart API | the bars, free and unofficial (or `--offline` a saved chart JSON) |
| `trader/smc.json` | with `--write`: the map, the levels and the reading |

## Rules

- **Long side only**, like the rest of the pack. Bearish levels are shown as
  resistance, never as a short idea.
- **Never call a level a signal.** It is a place to watch. The entry still
  needs a close above it (`/trader-entry`), a stop, a risk check and the
  user's yes.
- **Say the data.** Name the interval, the swing length and the last bar's
  time; Yahoo's bars can lag.
- **Not financial advice.** Nothing here places an order. Orders only go
  through `/trader-risk`, `/trader-broker` and the user's explicit yes for
  that exact order.

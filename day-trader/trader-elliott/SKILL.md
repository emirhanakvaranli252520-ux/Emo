---
name: trader-elliott
description: >-
  Elliott Wave. Counts the recent swings the Elliott way, on both sides and at
  three swing sizes: wave 2 (or B), wave 3, wave 4, wave 5, impulse complete,
  wave C of a zigzag or flat, ending diagonal. Drops every count that breaks a
  hard rule (wave 2 beyond the start of 1, wave 3 the shortest, wave 4 into
  wave 1's territory), scores the rest on the guidelines (Fibonacci depth and
  length, alternation, volume), weighs them, and gives a lean with an
  invalidation level, a target and the reward:risk from here against the
  user's 1.5-3.5 band, or says plainly that Elliott is undecided. Its
  evaluate mode replays the counts on the past with only the data known at
  the time and compares the calls with the base rate. Comes with a research
  reference on the rules, the guidelines and the evidence. Use when the user
  says "Elliott", "Elliott wave", "dalga sayımı", "Elliott dalga", "wave
  count", "impulse", "which wave are we in", "kaçıncı dalgadayız", "ABC
  correction", "zigzag", "flat", "diagonal", or when the direction is
  undecided after /trader-structure and the user wants a tie-breaker.
argument-hint: "SYMBOL [--source binance] [--degree 4] | evaluate SYMBOL [--horizon 48]"
---

# trader-elliott

Elliott wave analysis says markets trend in five waves and correct in three,
in a fractal. It is popular, and it is subjective: analysts often disagree on
the same chart, and the statistical support for its Fibonacci ratios is weak
(see `reference.md`). This skill is built around that. It never presents one
count as the truth: it lists every count that survives the rules, weighs
them, and only gives a lean when they agree. The user wants it as a
tie-breaker when the direction is unclear, and that is the only way to use
it. It is not a signal and not financial advice. Day trading loses most
people money.

**Read `${CLAUDE_SKILL_DIR}/reference.md` before explaining Elliott wave to
the user or before relying on a count.** It holds the rules, the guidelines
with their usual numbers, how to use a count, and what the evidence says.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/elliott.py" count BTCUSDT --source binance        # H1, swings of 2, 4 and 8 ATR
python3 "${CLAUDE_SKILL_DIR}/elliott.py" count NQ=F --degree 4                  # one swing size
python3 "${CLAUDE_SKILL_DIR}/elliott.py" count ES=F --at "2026-11-20 18:00"     # as it looked then (Turkey time)
python3 "${CLAUDE_SKILL_DIR}/elliott.py" count ETHUSDT --source binance --interval 4h --json --write
python3 "${CLAUDE_SKILL_DIR}/elliott.py" evaluate BTCUSDT --source binance --degree 4 --horizon 48
```

Data, symbols, `--at`, `--offline` and `--resample` work exactly as in
`/trader-structure` (this tool reuses its loader, so both folders must be
installed side by side). `--rr-min` / `--rr-max` change the band (default
1.5 and 3.5).

## What it does

1. **Swings.** An ATR(14) zigzag: a high is confirmed once price falls
   `degree` x ATR from it (and the mirror for lows). The leg in progress is
   provisional. Three sizes by default (2, 4 and 8 x ATR) stand in for three
   wave degrees.
2. **Counts.** For the swings ending at the leg in progress it tries, on
   both sides: wave 2 or B (next: 3 or C), wave 3, wave C of a zigzag, wave
   C of a flat, wave 4 (next: 5), wave 5 (late), impulse complete (next: a
   correction), ending diagonal complete.
3. **Rules** drop a count: wave 2 beyond the start of 1; wave 3 shortest of
   1, 3, 5; wave 4 overlapping wave 1 (except the diagonal, which must be a
   contracting wedge); a flat's B outside 90-138.2 % of A; a zigzag's B at
   or beyond 100 % of A.
4. **Guidelines** score what is left (0-100): wave 2 38.2-88.6 % of 1, wave
   3 1.382-2.8 x wave 1, wave 4 23.6-50 % of 3, alternation of 2 and 4 in
   depth or time, wave 5 0.618-1.618 x wave 1 or 0.618 x waves 1-3, more
   volume in wave 3 than wave 1.
5. **Lean.** Scores are weights. A lean needs 65 % of the weight on one side
   and a best count scoring 60 or more. Otherwise: undecided. Across the
   three sizes, "overall" is a direction only if no size disagrees.
6. **Plan.** Each count gives an invalidation level (where it is proven
   wrong: the natural stop) and a target (the next Fibonacci extension not
   yet reached), and the reward:risk from the current price, flagged when
   it falls outside 1.5-3.5.
7. **Evaluate.** At every bar where a swing gets confirmed, it counts again
   with only the bars known then, records the lean, and checks the close
   `--horizon` bars later and whether target or invalidation came first. It
   prints the hit rate next to the base rate.

## Steps

1. Use it only after `/trader-structure`: when structure and key levels
   already give a direction, Elliott adds nothing; say so.
2. Run `count`. Lead with the overall line. If undecided, say Elliott does
   not help here and stop; do not pick a count to fill the silence.
3. If it leans, give the best count in plain words ("a fourth wave pullback
   inside an up impulse"), its invalidation level (the stop), the target
   and the R:R, and the main alternate count and what it would mean.
4. Point out when the R:R from here is outside 1.5-3.5: under 1.5 the trade
   is not worth it; over 3.5 the target is far, so plan a partial inside
   the band.
5. Before the user leans on it for a market, run `evaluate` on that market
   and timeframe and say whether its calls beat the base rate there. If they
   do not, say plainly that the counts did not help on that chart.

## What it reads and writes

| file | what |
| --- | --- |
| Yahoo or Binance bars | through trader-structure's loader |
| `trader/elliott.json` | with `count --write`: the counts, leans, invalidations and targets |

## Rules

- **Never present one count as certain.** Always name the alternate.
- **The invalidation level is not optional.** A count without a stop is a
  story.
- **Tie-breaker only.** Elliott never overrides structure, liquidity, the
  risk check or the user's stop.
- **Not financial advice.** Nothing here places an order; orders only go
  through `/trader-risk`, `/trader-broker` and the user's explicit yes.

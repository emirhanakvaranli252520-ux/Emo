---
name: trader-journal
description: >-
  Trade Journal. Closes the loop after the trade: turns the fills trader-broker
  logged into round-trip trades, scores each one against the plan made before
  the entry (P&L in dollars and in R), flags broken discipline (a stop that
  filled past the plan, a chased entry, an exit after flat_by, a trade with no
  plan, a position held overnight), and prints the scorecard: win rate,
  average win and loss, profit factor, expectancy, max drawdown, losing
  streaks, a breakdown by setup, entry hour and tag, and how well the Time
  Machine's odds matched what really happened. Use when the user says "trade
  journal", "how am I doing", "review my trades", "my win rate", "expectancy",
  "what's working", "which setup makes money", "post-trade review", "log this
  trade", "işlem günlüğü", "işlemlerimi değerlendir", "kazanma oranım",
  "hangi strateji kazandırıyor", or after /trader-broker records a fill.
argument-hint: "[import | stats | list | add | note | snapshot]"
---

# trader-journal

The other ten skills on the order path get you into a trade and out of it.
This one asks afterwards whether any of it worked. Without it, a run of
three lucky winners feels like skill and a run of three stop-outs feels like
a broken setup. With it, every trade is measured against the plan you wrote
down before the entry, in R, so a $40 loss on a $50 plan and a $40 loss on a
$20 plan stop looking the same.

It is a scorecard of the past, not a forecast and not financial advice. Most
people who day trade lose money, and a good month does not change that. A
handful of trades proves nothing: below 20 closed trades every number comes
with a warning.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/journal.py" snapshot              # save trader/plan.json (+ Time Machine odds) now
python3 "${CLAUDE_SKILL_DIR}/journal.py" import                # fills in trader/state/broker.json -> scored trades
python3 "${CLAUDE_SKILL_DIR}/journal.py" stats                 # the scorecard
python3 "${CLAUDE_SKILL_DIR}/journal.py" stats --setup orb --since 2026-10-01
python3 "${CLAUDE_SKILL_DIR}/journal.py" list --last 10        # newest first, with every flag
python3 "${CLAUDE_SKILL_DIR}/journal.py" add --symbol TSLA --date 2026-10-19 --qty 8 \
    --entry 364.18 --exit 358.10 --stop 358.32 --target 370.04 --setup orb --opened 10:15 --closed 11:40
python3 "${CLAUDE_SKILL_DIR}/journal.py" note --id TSLA-2026-10-19-1015 --tag chased --text "second push"
```

Every command takes `--journal PATH` (default `trader/journal.json`);
`stats` and `list` take `--json`.

## What it reads and writes

| file | what |
| --- | --- |
| `trader/state/broker.json` | the fills trader-broker logged (`ticket.py fill`): the only source `import` trusts |
| `trader/plan.json` | the plan from trader-exit: entry, stop, target, flat_by, setup |
| `trader/timemachine.json` | the Time Machine's odds, kept only when they are for the same plan |
| `trader/journal.json` | the saved plans, the scored trades, any position still open |

## The workflow

1. **Before the entry**, right after `/trader-timemachine run --write`, run
   `journal.py snapshot`. plan.json is overwritten by the next trade; the
   snapshot keeps this one, with its odds, so the trade can be scored later.
   (`import` also snapshots whatever plan.json holds when it runs.)
2. **After each fill**, once `/trader-broker` has recorded it with
   `ticket.py fill`, run `journal.py import`. Fills are paired flat to flat
   per symbol, oldest first. A position that is still open is listed and
   scored once it closes. Running import twice adds nothing twice.
3. **At the end of the day or the week**, run `journal.py stats` and read the
   verdict out to the user in plain words, then the one or two numbers that
   matter most.
4. Fills from another broker, or old trades: `journal.py add`, one trade at a
   time. Give `--stop` if you know it, else the saved plan for that symbol and
   day is used; with neither, the trade gets dollars but no R.

## How a trade is scored

- **P&L** = (average sell - average buy) x shares - fees.
- **R** = P&L / (planned risk a share x shares). -1R is a clean stop-out.
- **Outcome**: `target` if it sold at or over the target, `stop` if at or
  under the stop, `manual` for anything in between (a flatten, an early exit).
- **Flags**: stop filled more than a cent past the plan (and how many dollars
  that cost), entry more than a quarter of the risk over the plan (chased),
  out after flat_by, no plan on file, held overnight.

## Reading the scorecard

| number | what it tells you |
| --- | --- |
| win rate vs break-even win rate | the break-even rate comes from your own average win and loss; winning less often than that loses money |
| expectancy ($ and R) | what the average trade made; negative means the process loses as it stands |
| profit factor | gross wins / gross losses; under 1.0 loses money |
| max drawdown, losing streak | how bad it got from a peak; size so the worst streak would not end the account |
| by setup / hour / tag | where the money comes from and where it leaks |
| discipline | the share of trades that followed the plan cleanly. Under 80 %: fix the process before you judge the setup |
| Time Machine vs reality | predicted vs actual target-first and stop-first rates, and a Brier score (0 perfect, 0.25 a coin flip) |

## Rules

- **Never invent a trade.** Only fills the broker log holds, or ones the user
  gives you with `add`, go in. Do not fill a missing exit price with a guess.
- **Say the sample size.** With fewer than 20 trades lead with that: the
  numbers are a sketch, not evidence.
- **Process before outcome.** A stopped-out trade that followed the plan is a
  good trade; a winner that broke the plan is a warning. Say so.
- **Not financial advice.** Never tell the user to size up because the stats
  look good. Changing a limit in `trader/config.json` is the user's call, and
  no order is ever placed from here: orders only go through `/trader-risk`,
  `/trader-broker` and the user's explicit yes for that exact order.

## Hands off to

- `/trader-risk`: if the journal shows losses worse than -1R, or a losing
  streak that would hit the daily limit, suggest the user tighten
  `max_loss_per_trade_usd` or `max_trades_per_day` (their decision).
- `/trader-scanner`: drop the setups the scorecard says are losing money.

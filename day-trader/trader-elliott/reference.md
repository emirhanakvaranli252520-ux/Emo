# Elliott wave: reference

What the wave principle says, what is a rule and what is only a guideline,
which numbers are conventions, and what the evidence does and does not
support. Read this before explaining or using a count.

## 1. The idea in one paragraph

R. N. Elliott (1930s) proposed that crowd psychology moves prices in a
repeating fractal: a trend unfolds in five waves (the **motive** phase:
1-2-3-4-5, with 1, 3 and 5 in the trend's direction) and is then corrected
in three (the **corrective** phase: A-B-C). Each wave is itself made of
waves of the next smaller **degree**, and each five-three cycle is one or
two waves of the next larger degree. Frost and Prechter's *Elliott Wave
Principle* (1978) is the standard text; Glenn Neely's *Mastering Elliott
Wave* (NEoWave, 1990) adds many more rules to make counts less subjective.

Degrees, largest to smallest: Grand Supercycle, Supercycle, Cycle, Primary,
Intermediate, Minor, Minute, Minuette, Subminuette. A day trader on H1 works
around Minute to Subminuette. `elliott.py` stands in for degree with the
zigzag size (2, 4 and 8 x ATR).

## 2. The hard rules (a count that breaks one is wrong)

Impulse (the common motive wave, subdivides 5-3-5-3-5):

1. Wave 2 never retraces beyond the start of wave 1.
2. Wave 3 is never the shortest of waves 1, 3 and 5 (it is often the longest).
3. Wave 4 never enters the price territory of wave 1 (no overlap). Some
   futures traders allow a small overlap on leveraged contracts; cash
   markets do not.

Diagonals (the exception to rule 3):

- A **leading diagonal** can be wave 1 or wave A; an **ending diagonal** can
  be wave 5 or wave C. Waves 1 and 4 overlap, and the shape is a wedge.
- In a contracting diagonal wave 3 is shorter than wave 1, wave 5 shorter
  than wave 3, and wave 4 shorter than wave 2. An ending diagonal is
  usually followed by a sharp reversal back to where it started.

Corrections:

- **Zigzag** (5-3-5): B retraces less than all of A; C goes beyond the end
  of A.
- **Flat** (3-3-5): B retraces at least about 90 % of A. Regular flat: B
  90-105 % of A, C ends near A's end. Expanded flat: B beyond A's start,
  commonly up to about 138 % of A, and C beyond A's end. Running flat: B
  beyond A's start but C fails to reach A's end. Sources differ on the exact
  limits (105 % vs 138 % vs 140 %); `elliott.py` uses 90-138.2 %.
- **Triangle** (3-3-3-3-3, A-B-C-D-E): contracting or expanding; appears as
  wave 4, wave B or the last part of a combination, almost never as wave 2.
- **Combination** (W-X-Y, or W-X-Y-X-Z): two or three simple corrections
  joined by X waves; each part keeps its own rules.

## 3. The guidelines (usual, not required)

These are what scores a count. They come from practitioner literature, not
from statistical tests (see section 5).

| guideline | the usual numbers |
| --- | --- |
| wave 2 depth | deep: 50-61.8 % of wave 1 typical, 38.2-88.6 % acceptable; often a zigzag |
| wave 3 length | 1.618 x wave 1 most cited; 2.618 when extended; usually the longest, with the most volume |
| wave 4 depth | shallow: 23.6-38.2 % of wave 3 typical, rarely beyond 50 %; often ends near the fourth wave of one lesser degree |
| alternation | if wave 2 is sharp (deep zigzag), wave 4 tends to be sideways (flat, triangle) and shallow, and vice versa; also in time |
| wave 5 | equal to wave 1 when wave 3 extended, or 0.618 x the distance from the start of 1 to the end of 3; may fall short (truncation) |
| extension | usually exactly one of 1, 3, 5 extends: wave 3 in stock indices, often wave 5 in commodities |
| channel | the line through the ends of 2 and 4, parallel copy through 3, often contains wave 5 |
| after an impulse | the correction usually ends in the area of the previous fourth wave, often 38.2-61.8 % of the whole impulse |
| zigzag C | equal to A, or 1.618 x A |
| flat C | 1 to 1.618 x A |
| volume | highest in wave 3; lower in wave 5 than in wave 3 (a divergence) |

## 4. How to use a count (the practical part)

- **The invalidation level is the useful output.** A wave-4 count is wrong
  if price enters wave 1's territory; a wave-2 count is wrong below the
  start of wave 1. That level is a natural stop and is objective even when
  the count is not.
- **Always hold an alternate count.** Practitioners keep a preferred count
  and at least one alternate; when the preferred one is invalidated, the
  alternate takes over. `elliott.py` lists every count that fits and weighs
  them; when they disagree it says so instead of choosing.
- **Use it as a tie-breaker, not a trigger.** For this user, the order is:
  market structure and liquidity first (`/trader-structure`), key levels
  second, Elliott only when those leave the direction undecided.
- **The same shape has several names.** A three-swing move can be waves
  1-2 of an impulse or A-B of a correction; both expect a continuation in
  the first leg's direction, but with different targets. A completed five
  can be a whole impulse or wave A of a larger zigzag.

## 5. What the evidence says (be honest about this)

- **Subjectivity is the main criticism.** Practitioners often disagree on
  the count for the same chart, and counts are frequently revised after the
  fact. The theory always has an alternate, which makes it hard to falsify.
- **Fibonacci ratios: little statistical support.** Batchelor and Ramyar,
  *Magic numbers in the Dow* (City University London), tested whether
  Fibonacci ratios appear in the ratios of successive Dow trends more often
  than chance, with a block bootstrap; the few significant ratios were no
  more than the number of tests would produce by chance, and they concluded
  the claim can be dismissed. Prechter replied (*Elliott Waves, Fibonacci
  and Statistics*) that their filtered trends are not Elliott waves.
- **Early academic view:** Gehm, *Who is R. N. Elliott and why is he making
  waves?* (Financial Analysts Journal, 1983) judged that many of its
  assumptions seem unreasonable and that it is likely of little practical
  value.
- **Machine-learning studies** report better numbers on pattern recognition
  (for example Vantuch, Zelinka and Vasant, *An algorithm for Elliott Waves
  pattern detection*, Intelligent Decision Technologies 2018, reports trend
  prediction above 70 % on incomplete patterns), but these are small,
  in-sample or single-market tests, and pattern-recognition accuracy is not
  trading profit.
- **Practitioner track records** (Prechter included) are mixed and not
  independently audited.

What follows for us: the only evidence that matters is on the markets and
timeframes the user trades. `elliott.py evaluate` replays the counts on the
past with only the data known at each moment and compares the calls with
the base rate (how often price was higher, or lower, that many bars later
anyway). If the calls do not beat the base rate on BTC, ETH, NQ and ES H1,
Elliott should not tip a decision there, however convincing a count looks.

## 6. What `elliott.py` does and does not do

Does: ATR zigzag swings at three sizes; the counts wave 2 (or B), wave 3,
wave C of a zigzag or flat, wave 4, wave 5, impulse complete, ending
diagonal complete, on both sides; the three impulse rules, the flat B limit
and the diagonal shape as hard filters; the guidelines in section 3 as a
score; a weighted lean with invalidation and target; reward:risk from the
current price against the user's 1.5-3.5 band; a replay against the base
rate.

Does not: count subwaves inside each wave (it judges one degree at a time,
so a "wave 3" is not checked to be five waves inside); triangles and
combinations; time (Fibonacci time zones); NEoWave's extra rules. A human
count can see more; it can also see what it wants to see.

## Sources

- Frost, A. J. and Prechter, R. R., *Elliott Wave Principle: Key to Market Behavior* (1978; many editions).
- Neely, G., *Mastering Elliott Wave* (1990).
- Batchelor, R. and Ramyar, R., *Magic numbers in the Dow*, City University London: https://openaccess.city.ac.uk/id/eprint/16276/ (abstract also on Semantic Scholar).
- Prechter, R. R., *Elliott Waves, Fibonacci and Statistics*: http://socionomics.org/pdf/EW_Fibo_Statistics.pdf
- Gehm, F., *Who is R. N. Elliott and why is he making waves?*, Financial Analysts Journal (1983): https://rpc.cfainstitute.org/research/financial-analysts-journal/1983/who-is-rn-elliott-and-why-is-he-making-waves
- Vantuch, T., Zelinka, I. and Vasant, P., *An algorithm for Elliott Waves pattern detection*, Intelligent Decision Technologies (2018): https://journals.sagepub.com/doi/abs/10.3233/IDT-170319
- Rules and guidelines summaries: https://www.oreilly.com/library/view/mastering-elliott-wave/9781118235157/xhtml/sec18.html, https://www.babypips.com/learn/forex/the-3-cardinal-rules-and-some-guidelines, https://chartschool.stockcharts.com/table-of-contents/market-analysis/elliott-wave-analysis-articles/identifying-elliott-wave-patterns, https://www.esignal.com/publicdocs/eSignal_Manual_ch9.pdf

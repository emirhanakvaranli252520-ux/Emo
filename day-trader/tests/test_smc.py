import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _load import FIX, load

smc = load("trader-smc", "smc")

TSLA = os.path.join(FIX, "trader-timemachine", "TSLA-60d5m.json.gz")
T0 = 1792416600            # 2026-10-19 09:30 EDT


def bars_from(rows):
    """[(o, h, l, c), ...] -> 5-minute bars starting 09:30."""
    return [{"t": T0 + 300 * i, "o": o, "h": h, "l": l, "c": c, "v": 1000} for i, (o, h, l, c) in enumerate(rows)]


def flat(n, p=100.0):
    return [(p, p + 0.1, p - 0.1, p)] * n


class Detection(unittest.TestCase):
    def test_swings_wait_for_confirmation_and_never_invent_edges(self):
        rows = flat(3) + [(100, 103, 99.9, 102)] + flat(3)
        sw = smc.swings(bars_from(rows), 3)
        self.assertEqual([(s["i"], s["kind"], s["level"], s["confirmed_at"]) for s in sw], [(3, 1, 103, 6)])
        # the same high with only 2 bars after it is not a swing yet
        self.assertEqual(smc.swings(bars_from(rows[:-1]), 3), [])

    def test_consecutive_swings_are_all_kept(self):
        # merging them would erase the 102 swing because of a bar that came later
        rows = flat(2) + [(100, 102, 99.9, 100)] + flat(2) + [(100, 104, 99.9, 100)] + flat(2)
        sw = smc.swings(bars_from(rows), 2)
        self.assertEqual([(s["kind"], s["level"]) for s in sw], [(1, 102), (1, 104)])

    def test_fvg_open_touched_filled(self):
        rows = [(100, 101, 99, 100.5), (101, 105, 100.8, 104.5), (104.5, 106, 102, 105.5),
                (105.5, 106, 101.5, 102)]
        g = smc.fvgs(bars_from(rows))
        self.assertEqual(len(g), 1)
        self.assertEqual((g[0]["kind"], g[0]["bottom"], g[0]["top"], g[0]["status"]), (1, 101, 102, "touched"))
        g = smc.fvgs(bars_from(rows + [(102, 102, 100.5, 101)]))
        self.assertEqual(g[0]["status"], "filled")
        self.assertEqual(smc.fvgs(bars_from(rows[:3]))[0]["status"], "open")

    def test_bos_then_choch_and_order_block(self):
        # up-swing to 105, pull back to a 101 low, then close through 105: BOS up.
        # then a swing low at 103 is broken by a close at 100: CHoCH down.
        rows = (flat(2, 100) + [(100, 105, 101.5, 104)] + [(104, 104, 102, 102), (102, 102.5, 101, 101.5),
                (101.5, 103, 101.4, 102.8), (102.8, 104, 102.5, 103.5)]
                + [(103.5, 106, 103.4, 105.6), (105.6, 106.5, 104, 104.2), (104.2, 104.5, 103, 103.2),
                   (103.2, 105, 103.1, 104.8), (104.8, 105.2, 104.5, 105), (105, 105, 99.5, 100)])
        bars = bars_from(rows)
        sw = smc.swings(bars, 2)
        trend, events, blocks = smc.structure(bars, sw)
        self.assertEqual([(e["type"], e["dir"]) for e in events], [("BOS", 1), ("CHoCH", -1)])
        self.assertEqual(events[0]["level"], 105)
        self.assertEqual(trend, -1)
        bull = [b for b in blocks if b["kind"] == 1][0]
        self.assertEqual((bull["bottom"], bull["top"]), (101, 102.5))
        self.assertEqual(bull["status"], "broken")       # the CHoCH close at 100 went through it

    def test_equal_lows_and_sweep(self):
        f = [(101, 101.1, 100.9, 101)]
        rows = (f * 2 + [(101, 101.2, 100.0, 101)] + f + [(101, 102, 100.9, 101)] + f
                + [(101, 101.2, 100.05, 101)] + f * 2)
        bars = bars_from(rows)
        pools = smc.liquidity(bars, smc.swings(bars, 2), 0.1)
        self.assertEqual(len(pools), 1)
        self.assertEqual((pools[0]["kind"], pools[0]["touches"], pools[0]["swept_at"]), (-1, 2, None))
        bars = bars_from(rows + [(101, 101, 99.8, 100.2)])
        pools = smc.liquidity(bars, smc.swings(bars, 2), 0.1)
        self.assertEqual(pools[0]["swept_at"], 9)

    def test_only_closed_bars_are_read(self):
        bars = bars_from(flat(4))
        now = smc.parse_now("2026-10-19 09:47")       # the 09:45 bar is still forming
        self.assertEqual(len(smc.closed_bars(bars, "5m", now)), 3)


class RealData(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = smc.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_tsla_at_the_reel_entry(self):
        code, out, err = self.run_cli("levels", "TSLA", "--offline", TSLA, "--at", "2026-10-19 10:15", "--json")
        self.assertEqual(code, 0, err)
        d = json.loads(out)
        self.assertEqual((d["last_bar"], d["price"], d["trend"]), ("2026-10-19 10:10", 364.18, "up"))
        self.assertEqual(d["recent_structure"][-1]["type"], "CHoCH")
        self.assertTrue(all(lv["top"] < d["price"] for lv in d["supports"]))
        self.assertTrue(all(lv["bottom"] > d["price"] for lv in d["resistances"]))
        self.assertEqual(d["supports"], sorted(d["supports"], key=lambda lv: -lv["top"]))
        self.assertTrue(d["idea"]["long"])
        self.assertLess(d["idea"]["stop"], d["price"])
        self.assertIn("warning", d["idea"])           # 0.35 reward:risk: the risk check would block it

    def test_no_look_ahead(self):
        # the map at 10:15 must not change when later bars exist in the file
        a = self.run_cli("levels", "TSLA", "--offline", TSLA, "--at", "2026-10-19 10:15", "--json")[1]
        bars = smc.parse_chart(smc.read_text(TSLA), "TSLA")[1]
        cut = [b for b in bars if b["t"] + 300 <= smc.parse_now("2026-10-19 10:15").timestamp()
               - smc.datetime.datetime(1970, 1, 1).timestamp()]
        doc = smc.analyze({"symbol": "TSLA"}, cut, "TSLA", "5m", 5, 0.1, smc.parse_now("2026-10-19 10:15"))
        self.assertEqual(json.loads(a)["supports"], doc["supports"])
        self.assertEqual(json.loads(a)["resistances"], doc["resistances"])

    def test_text_and_errors(self):
        code, out, _ = self.run_cli("levels", "TSLA", "--offline", TSLA, "--at", "2026-10-19 10:15")
        self.assertIn("Long-side reading", out)
        self.assertIn("--setup level --level", out)
        self.assertIn("not a proven edge", out)
        code, _, err = self.run_cli("levels", "AAPL", "--offline", TSLA)
        self.assertEqual(code, 1)
        self.assertIn("the data is for TSLA", err)
        code, _, err = self.run_cli("levels", "TSLA", "--offline", TSLA, "--interval", "1d")
        self.assertIn("pass --interval 5m", err)
        code, _, err = self.run_cli("levels", "TSLA", "--offline", TSLA, "--at", "2026-07-01 09:40")
        self.assertIn("closed bar", err)


if __name__ == "__main__":
    unittest.main()

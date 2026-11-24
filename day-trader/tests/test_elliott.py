import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _load import FIX, load

ew = load("trader-elliott", "elliott")

TSLA = os.path.join(FIX, "trader-timemachine", "TSLA-60d5m.json.gz")
T0 = 1792400400


def path_bars(prices, step=10):
    """A bar path through the given turning prices, `step` bars per leg, 0.1-wide bars."""
    bars = []
    for a, b in zip(prices, prices[1:]):
        for k in range(step):
            c = a + (b - a) * (k + 1) / step
            o = a + (b - a) * k / step
            bars.append({"t": T0 + 3600 * len(bars), "o": o, "h": max(o, c) + 0.05, "l": min(o, c) - 0.05,
                         "c": c, "v": 100})
    return bars


def pts(*prices):
    return [{"i": max(0, 10 * k - 1), "price": p} for k, p in enumerate(prices)]


class Rules(unittest.TestCase):
    def setUp(self):
        self.bars = path_bars([100, 110, 104, 126, 120, 131, 125], step=10)

    def names(self, p):
        return {h["count"]: h for h in ew.hypotheses(p, self.bars)}

    def test_a_clean_impulse_then_a_pullback_is_impulse_complete(self):
        h = self.names(pts(100, 110, 104, 126, 120, 131, 125))
        c = h["impulse complete (next: correction, wave A/B/C)"]
        self.assertEqual((c["lean"], c["invalidation"]), ("down", 131))
        self.assertGreaterEqual(c["score"], 80)

    def test_wave_4_cannot_enter_wave_1(self):
        h = self.names(pts(100, 110, 104, 126, 109))          # 109 < 110: overlap
        self.assertNotIn("wave 4 (next: wave 5)", h)
        h = self.names(pts(100, 110, 104, 126, 118))
        w4 = h["wave 4 (next: wave 5)"]
        self.assertEqual((w4["lean"], w4["invalidation"]), ("up", 110))

    def test_wave_2_cannot_pass_the_start(self):
        self.assertNotIn("wave 2 (next: wave 3) / wave B (next: wave C)", self.names(pts(100, 110, 99)))
        w2 = self.names(pts(100, 110, 104))["wave 2 (next: wave 3) / wave B (next: wave C)"]
        self.assertEqual((w2["lean"], w2["invalidation"], w2["target"]), ("up", 100, 120.18))

    def test_wave_3_may_not_be_the_shortest(self):
        # 1 = 10, 3 = 8, 5 running to 9: wave 3 would be shortest
        self.assertNotIn("wave 5 (impulse nearly done)", self.names(pts(100, 110, 105, 113, 111, 120)))
        w5 = self.names(pts(100, 110, 105, 113, 111, 118))["wave 5 (impulse nearly done)"]
        self.assertEqual(w5["cap"], 119)                      # wave 5 may not outgrow wave 3 (8)

    def test_mirror_for_a_down_impulse(self):
        w4 = self.names(pts(200, 190, 196, 174, 182))["wave 4 (next: wave 5)"]
        self.assertEqual((w4["lean"], w4["invalidation"]), ("down", 190))

    def test_flat_and_zigzag_b_limits(self):
        h = self.names(pts(100, 90, 99.5, 95))                # B 95 % of A: flat
        self.assertIn("wave C of a flat", h)
        self.assertNotIn("wave C of a zigzag", h)
        h = self.names(pts(100, 90, 96, 93))                  # B 60 %: zigzag
        self.assertIn("wave C of a zigzag", h)
        self.assertEqual(h["wave C of a zigzag"]["invalidation"], 96)


class Consensus(unittest.TestCase):
    def test_lean_needs_agreement_and_quality(self):
        up = {"count": "a", "lean": "up", "score": 80, "legs": 4, "invalidation": 95, "target": 120}
        dn = {"count": "b", "lean": "down", "score": 80, "legs": 6, "invalidation": 110, "target": 90}
        self.assertEqual(ew.consensus([dict(up)], 100)["lean"], "up")
        self.assertEqual(ew.consensus([dict(up), dict(dn)], 100)["lean"], "undecided")
        weak = dict(up, score=50)
        c = ew.consensus([weak], 100)
        self.assertEqual(c["lean"], "undecided")
        self.assertIn("only weak counts", c["why"])

    def test_rr_band(self):
        h = [{"count": "a", "lean": "up", "score": 80, "legs": 4, "invalidation": 95, "target": 120}]
        ew.consensus(h, 100)
        self.assertEqual((h[0]["rr_from_here"], h[0]["rr_band"]), (4.0, "over 3.5"))
        h = [{"count": "a", "lean": "up", "score": 80, "legs": 4, "invalidation": 95, "target": 110}]
        ew.consensus(h, 100)
        self.assertEqual(h[0]["rr_band"], "in band")


class Swings(unittest.TestCase):
    def test_zigzag_confirms_late_and_alternates(self):
        bars = path_bars([100, 110, 104, 126, 120], step=10)
        piv, prov = ew.zigzag(bars, 2.0)
        kinds = [p["kind"] for p in piv]
        self.assertTrue(all(kinds[k] != kinds[k + 1] for k in range(len(kinds) - 1)))
        for p in piv:
            self.assertGreater(p["known"], p["i"])
        self.assertIsNotNone(prov)

    def test_no_look_ahead(self):
        bars = path_bars([100, 110, 104, 126, 120, 131, 125, 140], step=10)
        early, _ = ew.zigzag(bars[:45], 2.0)
        late, _ = ew.zigzag(bars, 2.0)
        self.assertEqual(early, late[:len(early)])


class RealData(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = ew.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_count_and_evaluate_on_tsla(self):
        base = ["TSLA", "--offline", TSLA, "--interval", "5m", "--resample", "1h", "--at", "2026-10-19 17:15"]
        code, out, err = self.run_cli("count", *base, "--json")
        self.assertEqual(code, 0, err)
        d = json.loads(out)
        self.assertEqual([x["degree_atr"] for x in d["degrees"]], [2.0, 4.0, 8.0])
        self.assertIn(d["overall"], ("up", "down", "undecided"))
        for deg in d["degrees"]:
            for h in deg["counts"]:
                self.assertTrue(0 <= h["score"] <= 100)
                if h["lean"] == "up":
                    self.assertLess(h["invalidation"], max(p["price"] for p in h["points"]) + 1e-9)
        code, out, err = self.run_cli("evaluate", *base, "--degree", "2", "--horizon", "24", "--json")
        self.assertEqual(code, 0, err)
        e = json.loads(out)
        self.assertEqual(e["leaned"] + e["undecided"], e["swing_events"])
        self.assertEqual(e["target_first"] + e["invalidation_first"] + e["neither"], e["leaned"])
        self.assertIsNotNone(e["base_up_pct"])
        code, out, _ = self.run_cli("count", *base)
        self.assertIn("Overall:", out)
        self.assertIn("tie-breaker", out)


if __name__ == "__main__":
    unittest.main()

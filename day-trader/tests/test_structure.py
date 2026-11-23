import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _load import FIX, load

st = load("trader-structure", "structure")

TSLA = os.path.join(FIX, "trader-timemachine", "TSLA-60d5m.json.gz")
T0 = 1792400400            # 2026-10-19 09:00 UTC, on the hour


def zigzag(peaks, troughs=None):
    """Bars where the odd bars carry the given highs (and lows, if given) and the
    even bars are flat at 1.0 / 0.5. One bar an hour."""
    bars = []
    for k, p in enumerate(peaks):
        bars.append({"t": T0 + 3600 * len(bars), "o": 1, "h": 1.0, "l": 0.5, "c": 1})
        lo = troughs[k] if troughs else 0.5
        bars.append({"t": T0 + 3600 * len(bars), "o": 1, "h": p, "l": lo, "c": 1})
    bars.append({"t": T0 + 3600 * len(bars), "o": 1, "h": 1.0, "l": 0.5, "c": 1})
    return bars


class Tiers(unittest.TestCase):
    def test_short_intermediate_long_highs(self):
        bars = zigzag([2, 4, 3, 6, 3, 5, 2, 8, 3, 4, 2, 7, 2])
        t = st.tiers(bars)
        self.assertEqual(len(t["STH"]), 13)
        self.assertEqual([p["level"] for p in t["ITH"]], [4, 6, 5, 8, 4, 7])
        self.assertEqual([p["level"] for p in t["LTH"]], [6, 8])
        six = t["LTH"][0]
        self.assertEqual(six["i"], 7)
        # an STH is known one bar later; the 6 is an ITH once the next STH (bar 9) is known (bar 10),
        # and an LTH once the next ITH (the 5 at bar 11) is known, which needs the STH at bar 13 (bar 14)
        self.assertEqual([p["known"] for p in t["STH"][:2]], [2, 4])
        self.assertEqual([p for p in t["ITH"] if p["i"] == 7][0]["known"], 10)
        self.assertEqual(six["known"], 14)

    def test_lows_mirror_the_highs(self):
        troughs = [9, 7, 8, 5, 8, 6, 9, 3, 8, 7, 9, 4, 9]
        bars = zigzag([1.0] * 13, troughs)
        for b in bars:
            if b["l"] == 0.5:
                b["l"], b["h"] = 10.0, 11.0
        t = st.tiers(bars)
        self.assertEqual([p["level"] for p in t["ITL"]], [7, 5, 6, 3, 7, 4])
        self.assertEqual([p["level"] for p in t["LTL"]], [5, 3])

    def test_equal_highs_are_not_pivots(self):
        bars = zigzag([2, 2, 2])
        self.assertEqual([p["level"] for p in st.tiers(bars)["ITH"]], [])

    def test_fvg(self):
        bars = [{"t": T0, "o": 10, "h": 11, "l": 9, "c": 10.5}, {"t": T0 + 3600, "o": 10.5, "h": 14, "l": 10.4, "c": 13.8},
                {"t": T0 + 7200, "o": 13.8, "h": 15, "l": 12, "c": 14.5}]
        g = st.fvgs(bars)
        self.assertEqual([(x["dir"], x["bottom"], x["top"], x["known"]) for x in g], [(1, 11, 12, 2)])


class Data(unittest.TestCase):
    def test_binance_klines_and_turkey_time(self):
        rows = [[1792400400000, "100", "101", "99", "100.5", "12.5", 1792403999999, "0", 1, "0", "0", "0"]]
        sym, gran, bars = st.parse_bars(json.dumps(rows), "BTCUSDT")
        self.assertEqual((sym, gran, bars[0]["t"], bars[0]["h"], bars[0]["v"]), ("BTCUSDT", None, 1792400400, 101.0, 12.5))
        self.assertEqual(st.tr_time(1792400400), "2026-10-19 12:00")         # 09:00 UTC = 12:00 Turkey
        self.assertEqual(st.parse_at("2026-10-19 12:00"), st.datetime.datetime(2026, 10, 19, 9, 0))
        self.assertEqual(st.parse_at("2026-10-19T09:00Z"), st.datetime.datetime(2026, 10, 19, 9, 0))

    def test_resample_and_closed_bars(self):
        five = [{"t": T0 + 300 * k, "o": 1 + k, "h": 2 + k, "l": k, "c": 1.5 + k, "v": 1} for k in range(18)]
        hourly = st.resample(five, "1h")
        self.assertEqual(len(hourly), 2)
        self.assertEqual((hourly[0]["o"], hourly[0]["h"], hourly[0]["l"], hourly[0]["c"], hourly[0]["v"]),
                         (1, 13, 0, 12.5, 12))
        now = st.datetime.datetime(2026, 10, 19, 10, 30)                     # the 10:00 hour is still forming
        self.assertEqual(len(st.closed_only(hourly, "1h", now, resampled=True)), 1)


class RealData(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = st.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def scan(self, at):
        code, out, err = self.run_cli("scan", "TSLA", "--offline", TSLA, "--interval", "5m", "--resample", "1h",
                                      "--at", at, "--json")
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_tsla_hourly(self):
        d = self.scan("2026-10-19 17:15")
        self.assertEqual((d["interval"], d["last_bar"], d["timezone"]), ("1h", "2026-10-19 16:30", "Turkey (UTC+3)"))
        self.assertGreater(d["counts"]["STH"], d["counts"]["ITH"])
        self.assertGreater(d["counts"]["ITH"], d["counts"]["LTH"])
        self.assertTrue(d["setups"])
        for s in d["setups"]:
            self.assertLessEqual(s["known_at"], d["last_bar"][:10] + " 23:59")
            self.assertLess(s["lt"]["at"], s["it"]["at"])
            self.assertLess(s["it"]["at"], s["fvg"]["at"])
            if s["dir"] == "bullish":
                self.assertGreater(s["it"]["level"], s["lt"]["level"])
                self.assertGreater(s["plan"]["entry"], s["plan"]["stop"])
                self.assertGreater(s["plan"]["target"], s["plan"]["entry"])
            else:
                self.assertLess(s["it"]["level"], s["lt"]["level"])
                self.assertLess(s["plan"]["target"], s["plan"]["entry"])
            self.assertIn(s["status"], ("waiting", "tapped", "target", "stopped", "missed", "invalid"))
        self.assertIn("bias", d)

    def test_no_look_ahead(self):
        # every point and every sequence visible on Sep 25 is still there, unchanged, on Oct 19
        early = self.scan("2026-09-25 23:00")
        bars = st.resample(st.parse_bars(st.read_text(TSLA), "TSLA")[2], "1h")
        bars = st.closed_only(bars, "1h", st.parse_at("2026-10-19 23:00"), resampled=True)
        t = st.tiers(bars)

        def key(s):
            return (s["dir"], s["lt"]["at"], s["it"]["at"], s["fvg"]["at"], s["plan"]["entry"], s["plan"]["stop"])
        later = set(key(s) for s in st.scan_setups(bars, t, st.fvgs(bars)))
        self.assertTrue(early["setups"])
        for s in early["setups"]:
            self.assertIn(key(s), later)
        for name in ("LTH", "LTL", "ITH", "ITL"):
            late_pts = [(st.r2(p["level"]), st.tr_time(bars[p["i"]]["t"])) for p in t[name]]
            for p in early["points"][name]:
                self.assertIn((p["level"], p["at"]), late_pts)

    def test_text_and_errors(self):
        code, out, _ = self.run_cli("scan", "TSLA", "--offline", TSLA, "--interval", "5m", "--resample", "1h",
                                    "--at", "2026-10-19 17:15")
        self.assertIn("Sequences", out)
        self.assertIn("Turkey time", out)
        self.assertIn("proves nothing", out)
        code, _, err = self.run_cli("scan", "TSLA", "--offline", TSLA)
        self.assertEqual(code, 1)
        self.assertIn("--resample 1h", err)
        code, _, err = self.run_cli("scan", "AAPL", "--offline", TSLA, "--interval", "5m")
        self.assertIn("holds TSLA", err)


if __name__ == "__main__":
    unittest.main()

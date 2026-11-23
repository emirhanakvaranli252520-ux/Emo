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


def amd_bars(tail, volume=True):
    """30 trending bars on heavy volume, 12 bars ranging 99-101 on light volume, then `tail`."""
    bars = []
    for k in range(30):
        c = 90 + 0.3 * k
        bars.append((c - 0.2, c + 0.3, c - 0.3, c, 1000))
    for k in range(12):
        bars.append((100, 101, 100.2, 100.5, 200) if k % 2 == 0 else (100, 99.8, 99, 99.5, 200))
    bars += tail
    return [{"t": T0 + 3600 * j, "o": o, "h": h, "l": l, "c": c, "v": v if volume else 0}
            for j, (o, h, l, c, v) in enumerate(bars)]


RAID_LOW = (99.6, 100, 98.5, 99.4, 300)


class RangeAMD(unittest.TestCase):
    def boxes(self, tail, volume=True):
        bars = amd_bars(tail, volume)
        reg = st.regime(bars, 6)
        return bars, reg, st.amd_boxes(bars, reg, 6)

    def test_the_range_is_found_from_efficiency_volume_and_edges(self):
        bars, reg, boxes = self.boxes([])
        self.assertEqual(reg[29]["state"], "unknown")
        self.assertEqual(reg[35]["state"], "range")
        self.assertLess(reg[35]["vol_rel"], 0.8)
        self.assertEqual(reg[35]["touches"], [3, 3])
        self.assertEqual((boxes[0]["detected"], boxes[0]["high"], boxes[0]["low"]), (35, 101, 99))
        self.assertEqual(boxes[0]["phase"], "accumulation")

    def test_raid_low_then_opposite_edge_is_bullish_amd(self):
        bars, reg, boxes = self.boxes([RAID_LOW, (99.5, 100.8, 99.3, 100.6, 300), (100.6, 102, 100.5, 101.8, 900)])
        b = boxes[0]
        self.assertEqual((b["side"], b["extreme"], b["raid_at"]), (-1, 98.5, 42))
        self.assertEqual((b["end"], b["outcome"]), (44, "AMD bullish"))
        plan = st.amd_plan(b, bars)
        self.assertEqual((plan["dir"], plan["entry"], plan["stop"], plan["target1"], plan["target2"], plan["rr1"]),
                         ("long", 99.4, 98.5, 101, 103, 1.78))

    def test_a_raid_that_keeps_going_failed(self):
        bars, reg, boxes = self.boxes([RAID_LOW, (99.3, 99.4, 97.9, 98.2, 900)])
        self.assertTrue(boxes[0]["outcome"].startswith("failed"))

    def test_closes_outside_that_come_back_are_a_raid_but_staying_out_is_a_breakout(self):
        back = [(99.2, 99.3, 98.6, 98.8, 300), (98.8, 99.6, 98.4, 99.5, 300)]
        b = self.boxes(back)[2][0]
        self.assertEqual((b["phase"], b["side"], b["extreme"]), ("manipulation", -1, 98.4))
        out = [(99.2, 99.3, 98.6, 98.8, 300), (98.8, 98.9, 98.2, 98.5, 300), (98.5, 98.6, 97.8, 98.0, 300)]
        b = self.boxes(out)[2][0]
        self.assertEqual(b["outcome"], "breakout down")

    def test_no_volume_falls_back_to_atr(self):
        bars, reg, boxes = self.boxes([], volume=False)
        self.assertIsNone(reg[35]["vol_rel"])
        self.assertIn("atr_rel", reg[35])

    def test_range_command_on_real_data(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = st.main(["range", "TSLA", "--offline", TSLA, "--interval", "5m", "--resample", "1h",
                            "--at", "2026-10-19 17:15", "--json"])
        self.assertEqual(code, 0, err.getvalue())
        d = json.loads(out.getvalue())
        self.assertEqual(d["record"]["amd_complete"], 1)
        box = d["boxes"][0]
        self.assertEqual((box["low"], box["high"], box["raided"], box["outcome"]), (357.04, 371.83, "low", "AMD bullish"))
        self.assertEqual(box["events"][0]["extreme"], 354.63)
        # the same box marks the structure sequence that formed inside it
        with redirect_stdout(io.StringIO()) as o2, redirect_stderr(io.StringIO()):
            st.main(["scan", "TSLA", "--offline", TSLA, "--interval", "5m", "--resample", "1h",
                     "--at", "2026-10-19 17:15", "--json"])
        scan = json.loads(o2.getvalue())
        self.assertIn("by_regime", scan)
        self.assertIn(scan["regime_now"]["state"], ("range", "trend", "mixed"))


def hourly(start_utc, rows):
    """rows of (o, h, l, c) one hour apart from a naive-UTC datetime."""
    t0 = st.epoch(start_utc)
    return [{"t": t0 + 3600 * k, "o": o, "h": h, "l": l, "c": c, "v": 1} for k, (o, h, l, c) in enumerate(rows)]


class KeyLevels(unittest.TestCase):
    def test_calendars(self):
        self.assertEqual([st.guess_calendar(s) for s in ("BTCUSDT", "ETH-USD", "NQ=F", "THYAO.IS", "TSLA")],
                         ["crypto", "crypto", "cme", "bist", "stock"])
        D = st.datetime.datetime
        # Sunday 23:30 UTC = 19:30 New York (EDT): CME's Monday session; crypto's Sunday
        ts = st.epoch(D(2026, 10, 18, 23, 30))
        self.assertEqual(st.trading_day(ts, "cme"), st.datetime.date(2026, 10, 19))
        self.assertEqual(st.trading_day(ts, "crypto"), st.datetime.date(2026, 10, 18))
        # 22:00 UTC = 01:00 Istanbul the next day
        self.assertEqual(st.trading_day(st.epoch(D(2026, 10, 19, 22, 0)), "bist"), st.datetime.date(2026, 10, 20))

    def test_crypto_week_monday_and_prior_levels(self):
        D = st.datetime.datetime
        # Sun Oct 18 00:00 UTC .. : 24 h of Sunday, 24 h of Monday, 6 h of Tuesday
        rows = [(100, 101, 99, 100)] * 24
        rows += [(102.5, 105, 102, 104)] + [(104, 104.5, 102, 103)] * 23          # Monday 102-105
        rows += [(103, 103.5, 101.5, 102)] + [(102, 102.5, 100.5, 101)] * 2     # Tuesday takes the low, stays under
        rows += [(101, 106, 100.8, 104.6)] + [(104.6, 105.2, 104, 104.8)] * 2   # wick over the high, closes back
        bars = hourly(D(2026, 10, 18), rows)
        d = st.key_levels("BTCUSDT", bars, "1h", D(2026, 10, 20, 6, 0))
        self.assertEqual(d["calendar"], "crypto")
        mo = d["monday"]
        self.assertEqual((mo["day"], mo["low"], mo["high"], mo["forming"]), ("2026-10-19", 102, 105, False))
        self.assertTrue(mo["low_taken"]["how"].startswith("accepted"))
        self.assertTrue(mo["high_taken"]["how"].startswith("swept"))
        self.assertEqual(mo["first_side_taken"], "low")
        codes = {l["code"]: l for l in d["above"] + d["below"]}
        self.assertEqual(codes["PDH"]["level"], 105)        # Monday was the previous day
        self.assertEqual(codes["DO"]["level"], 103)
        self.assertEqual(codes["PWH"]["level"], 101)        # the week before held only Sunday
        self.assertTrue(codes["PWH"]["partial"])
        self.assertTrue(any("partly in the data" in n for n in d["notes"]))

    def test_cme_midnight_open_and_week(self):
        D = st.datetime.datetime
        # Sunday 22:00 UTC (18:00 NY) through Monday 06:00 UTC (02:00 NY)
        rows = [(200 + k, 201 + k, 199 + k, 200.5 + k) for k in range(12)]
        bars = hourly(D(2026, 10, 18, 22), rows)
        d = st.key_levels("NQ=F", bars, "1h", D(2026, 10, 19, 10))
        codes = {l["code"]: l for l in d["above"] + d["below"]}
        self.assertEqual(codes["MNO"]["level"], 206)        # the 7th bar, 04:00 UTC, is 00:00 New York
        self.assertEqual(d["monday"]["day"], "2026-10-19")
        self.assertTrue(d["monday"]["forming"])

    def test_on_real_data(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = st.main(["levels", "TSLA", "--offline", TSLA, "--interval", "5m", "--resample", "1h",
                            "--at", "2026-10-16 23:30", "--json"])
        self.assertEqual(code, 0, err.getvalue())
        d = json.loads(out.getvalue())
        self.assertEqual((d["monday"]["low"], d["monday"]["high"]), (377.58, 382.61))
        self.assertEqual(d["monday"]["first_side_taken"], "low")
        self.assertEqual(d["week"]["prev_key"], "2026-W41")
        self.assertTrue(all(l["level"] > d["price"] for l in d["above"]))
        with redirect_stdout(io.StringIO()) as o, redirect_stderr(io.StringIO()):
            st.main(["levels", "TSLA", "--offline", TSLA, "--interval", "5m", "--resample", "1h",
                     "--at", "2026-10-16 23:30"])
        self.assertIn("below the range", o.getvalue())

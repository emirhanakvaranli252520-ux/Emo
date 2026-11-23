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


class Liquidity(unittest.TestCase):
    def test_time_to_take_and_untaken(self):
        # STHs at bars 1, 3, 5 (2, 4, 3); bar 4 takes the 2 three bars after it is known; the 4 is never taken
        rows = [(1, 1, 0.5, 1), (1, 2, 0.5, 1), (1, 1, 0.5, 1), (1, 4, 0.5, 1), (1, 1, 0.5, 1), (1, 3, 0.5, 1)]
        rows += [(1, 1, 0.5, 1)] * 60
        bars = [{"t": T0 + 3600 * k, "o": o, "h": h, "l": l, "c": c} for k, (o, h, l, c) in enumerate(rows)]
        liq = st.liquidity_map(bars, st.tiers(bars))["STH"]
        self.assertEqual(liq["points"], 3)
        self.assertEqual(liq["untaken_count"], 2)                  # the 4 and the 3
        self.assertEqual(liq["median_bars_to_take"], 1)            # the 2, known at bar 2, taken at bar 3
        self.assertAlmostEqual(liq["taken_within_6"], 33.33, places=2)
        self.assertIn("baseline_within_24", liq)
        self.assertEqual([u["level"] for u in liq["untaken"]], [3, 4])

    def test_plans_carry_the_sth_stl_fuel(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            st.main(["scan", "TSLA", "--offline", TSLA, "--interval", "5m", "--resample", "1h",
                     "--at", "2026-10-19 17:15", "--json"])
        d = json.loads(out.getvalue())
        self.assertGreater(d["liquidity"]["STH"]["taken_within_48"], 90)
        with_t1 = [s for s in d["setups"] if "target1" in s["plan"]]
        self.assertTrue(with_t1)
        for s in with_t1:
            p = s["plan"]
            if s["dir"] == "bullish":
                self.assertTrue(p["entry"] < p["target1"] < p["target"])
            else:
                self.assertTrue(p["target"] < p["target1"] < p["entry"])
        warned = [s for s in d["setups"] if "stop_warning" in s["plan"]]
        self.assertTrue(warned)
        for s in warned:
            self.assertIn("sits just", s["plan"]["stop_warning"])
        self.assertGreaterEqual(d["t1_record"]["with_t1"], d["t1_record"]["t1_hit"])


def ltf_path(prices, step=4):
    """5-minute bars walking through the given prices, `step` bars per leg."""
    bars = []
    for a, b in zip(prices, prices[1:]):
        for k in range(step):
            o = a + (b - a) * k / step
            c = a + (b - a) * (k + 1) / step
            bars.append({"t": T0 + 300 * len(bars), "o": o, "h": max(o, c) + 0.02, "l": min(o, c) - 0.02,
                         "c": c, "v": 1})
    return bars


class LowerTimeframe(unittest.TestCase):
    # down into the 100-101 zone with a lower high at 102.5, a low at 99.6, then up through 102.5 and on to 117
    PATH = [104, 101.8, 102.5, 99.6, 103.2, 102.6, 117]

    def test_touch_choch_entry_stop_and_target(self):
        lb = ltf_path(self.PATH)
        r = st.ltf_confirm(lb, "long", 100, 101, 98, 120, 0, rr_band=(1.5, 3.5), window=40, mode="choch")
        self.assertEqual(r["state"], "confirmed")
        self.assertEqual(r["choch_level"], 102.52)
        self.assertEqual((r["entry"], r["stop"]), (103.2, 99.58))          # the CHoCH close, the low in the zone
        self.assertEqual(r["rr"], 4.64)
        self.assertEqual(r["result"], "open")                              # 120 never came
        self.assertEqual(r["band"]["action"], "take profit at 3.5R")
        self.assertEqual((r["band"]["target"], r["band"]["result"]), (115.87, "target"))

    def test_band_skips_a_small_reward(self):
        lb = ltf_path([102.9] + self.PATH[1:])            # start under the 103.6 target
        r = st.ltf_confirm(lb, "long", 100, 101, 98, 103.6, 0, rr_band=(1.5, 3.5), window=40, mode="choch")
        self.assertTrue(r["band"]["action"].startswith("skip"))

    def test_buffer_moves_the_stop(self):
        lb = ltf_path(self.PATH)
        a = st.ltf_confirm(lb, "long", 100, 101, 98, 107, 0, window=40, mode="choch")
        b = st.ltf_confirm(lb, "long", 100, 101, 98, 107, 0, window=40, buffer=0.5, mode="choch")
        self.assertLess(b["stop"], a["stop"])

    def test_htf_stop_invalidates_and_no_choch(self):
        lb = ltf_path([104, 101.8, 102.5, 99.6, 97.5, 97])
        self.assertTrue(st.ltf_confirm(lb, "long", 100, 101, 98, 107, 0, mode="choch")["state"].startswith("invalidated"))
        lb = ltf_path([104, 101.8, 102.5, 99.6, 100.5, 100.0, 100.6, 100.1] + [100.3, 100.2] * 12)
        self.assertEqual(st.ltf_confirm(lb, "long", 100, 101, 98, 107, 0, window=20, mode="choch")["state"],
                         "no CHoCH within the window")

    def test_short_side_mirror(self):
        lb = ltf_path([96, 98.2, 97.5, 100.4, 96.8, 97.4, 92])
        r = st.ltf_confirm(lb, "short", 99, 100, 102, 93, 0, window=40, mode="choch")
        self.assertEqual((r["state"], r["result"]), ("confirmed", "target"))
        self.assertEqual(r["stop"], 100.42)

    def test_binance_pages(self):
        calls = []
        old = st.http_get

        def fake(url):
            calls.append(url)
            end = int(url.split("endTime=")[1]) if "endTime=" in url else 10 ** 13
            n = int(url.split("limit=")[1].split("&")[0])
            start = end - n * 300000
            return json.dumps([[start + 300000 * k, "1", "1", "1", "1", "1"] for k in range(n)])
        st.http_get = fake
        try:
            rows = json.loads(st.binance_pages("BTCUSDT", "5m", 2500))
        finally:
            st.http_get = old
        self.assertEqual(len(rows), 2500)
        self.assertEqual(len(calls), 3)
        self.assertEqual(rows, sorted(rows, key=lambda r: r[0]))

    def test_sequences_on_real_data(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = st.main(["confirm", "TSLA", "--offline", TSLA, "--at", "2026-10-19 17:15", "--json",
                            "--ltf", "5m", "--bias-tf", "none", "--mode", "choch", "--pattern", "classic"])
        self.assertEqual(code, 0, err.getvalue())
        d = json.loads(out.getvalue())
        self.assertEqual((d["ltf"], d["htf"]), ("5m", "1h"))
        c = d["compare"]
        self.assertEqual(c["touched"], 7)
        self.assertEqual(c["missed"], 2)             # ran to the H1 target before price came back
        self.assertEqual(c["confirmed"], 5)
        for r in d["sequences"]:
            l_ = r["ltf"]
            if l_["state"] == "confirmed":
                if r["dir"] == "bullish":
                    self.assertLess(l_["stop"], l_["entry"])
                else:
                    self.assertGreater(l_["stop"], l_["entry"])
                self.assertGreaterEqual(l_["at"], r["known_at"][:13])
        with redirect_stdout(io.StringIO()) as o, redirect_stderr(io.StringIO()):
            code = st.main(["confirm", "TSLA", "--offline", TSLA, "--at", "2026-10-19 17:15", "--ltf", "5m",
                            "--zone", "355.4-356.4", "--side", "long", "--stop", "349", "--target", "370",
                            "--since", "2026-10-19 16:30"])
        self.assertEqual(code, 0)
        self.assertIn("zone 355.40-356.40", o.getvalue())


class DailyBias(unittest.TestCase):
    def test_bias_from_closed_daily_bars_only(self):
        D = st.datetime.datetime
        day0 = st.epoch(D(2026, 9, 1))
        # rising zigzag: higher highs and higher lows, one bar a day
        highs = [10, 12, 11, 14, 13, 16, 15, 18, 17, 20]
        bars = [{"t": day0 + 86400 * k, "o": h - 1, "h": h, "l": h - 2, "c": h - 0.5} for k, h in enumerate(highs)]
        self.assertEqual(st.bias_at(bars, day0 + 86400 * 10)[0], "bullish")
        self.assertEqual(st.bias_at(bars, day0 + 86400 * 3)[0], "unknown")       # only 3 closed days
        # a day still trading does not count
        self.assertEqual(st.bias_at(bars, day0 + 86400 * 9 + 3600), st.bias_at(bars, day0 + 86400 * 9))
        falling = [{"t": b["t"], "o": -b["o"], "h": -b["l"], "l": -b["h"], "c": -b["c"]} for b in bars]
        self.assertEqual(st.bias_at(falling, day0 + 86400 * 10)[0], "bearish")

    def test_day_15m_hour_chain_on_real_data(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = st.main(["confirm", "TSLA", "--offline", TSLA, "--data-interval", "5m",
                            "--at", "2026-10-19 17:15", "--json"])
        self.assertEqual(code, 0, err.getvalue())
        d = json.loads(out.getvalue())
        self.assertEqual((d["bias_tf"], d["htf"], d["ltf"]), ("1d", "1h", "15m"))
        bb = d["by_bias"]
        self.assertEqual(bb["aligned"]["sequences"] + bb["not_aligned"]["sequences"], len(d["sequences"]))
        for r in d["sequences"]:
            self.assertIn(r["bias"], ("bullish", "bearish", "mixed", "unknown"))
            self.assertEqual(r["aligned"], r["bias"] == r["dir"])
        with redirect_stdout(io.StringIO()) as o, redirect_stderr(io.StringIO()):
            st.main(["confirm", "TSLA", "--offline", TSLA, "--data-interval", "5m", "--at", "2026-10-19 17:15"])
        self.assertIn("1d bias -> 1h -> 15m confirmation", o.getvalue())
        self.assertIn("Split by the 1d bias", o.getvalue())


def lows_path(lows, top=105.0, start_t=T0):
    """15m bars whose lows follow `lows` exactly, highs one point above, closing near the high."""
    return [{"t": start_t + 900 * k, "o": l + 0.5, "h": l + 1.0, "l": l, "c": l + 0.9, "v": 1}
            for k, l in enumerate(lows)]


class ItlConfirmation(unittest.TestCase):
    # lows: into the zone (<= 101), STLs at 100.0, 99.2, 100.4: 99.2 is an ITL once 100.4 is confirmed
    LOWS = [103, 102, 101, 100.0, 100.6, 99.2, 100.8, 100.4, 101.5, 103, 105, 108, 112, 116, 120]

    def test_first_itl_after_the_touch(self):
        lb = lows_path(self.LOWS)
        r = st.ltf_confirm(lb, "long", 100.5, 101, 97, 115, 0, window=20)
        self.assertEqual(r["state"], "confirmed")
        self.assertEqual(r["itl"]["level"], 99.2)
        self.assertEqual(r["stop"], 99.2)
        self.assertEqual(r["entry"], lb[8]["c"])          # the ITL is known when the STL at bar 7 is (bar 8)
        self.assertEqual(r["result"], "target")
        self.assertEqual(r["band"]["action"], "take profit at 3.5R")

    def test_stop_close_and_target_first(self):
        lb = lows_path([103, 102, 101, 96.5, 96.0, 95.5])
        self.assertTrue(st.ltf_confirm(lb, "long", 100.5, 101, 97, 115, 0)["state"].startswith("invalidated"))
        lb = lows_path([103, 104, 110, 116, 101])        # ran to 115 before coming back to the zone
        self.assertTrue(st.ltf_confirm(lb, "long", 100.5, 101, 97, 115, 0)["state"].startswith("missed"))

    def test_no_itl_in_the_window(self):
        lb = lows_path([103, 102, 101, 100.5, 100.3, 100.1, 99.9, 99.7, 99.5, 99.3, 99.1, 98.9])
        self.assertEqual(st.ltf_confirm(lb, "long", 100.5, 101, 97, 115, 0, window=8)["state"],
                         "no ITL within the window")

    def test_short_side(self):
        lb = [{"t": T0 + 900 * k, "o": -l - 0.5, "h": -l, "l": -l - 1.0, "c": -l - 0.9, "v": 1}
              for k, l in enumerate(self.LOWS)]
        r = st.ltf_confirm(lb, "short", -101, -100.5, -97, -115, 0, window=20)
        self.assertEqual((r["state"], r["itl"]["level"], r["result"]), ("confirmed", -99.2, "target"))

    def test_itl_chain_and_range_flag_on_real_data(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = st.main(["confirm", "TSLA", "--offline", TSLA, "--data-interval", "5m",
                            "--at", "2026-10-19 17:15", "--json"])
        self.assertEqual(code, 0, err.getvalue())
        d = json.loads(out.getvalue())
        self.assertEqual(d["mode"], "itl")
        for r in d["sequences"]:
            self.assertIn("in_range", r)
            l_ = r["ltf"]
            if l_["state"] == "confirmed":
                self.assertEqual(l_["stop"], l_["itl"]["level"])
                self.assertGreaterEqual(l_["itl"]["at"], l_["touch"])


class FastPattern(unittest.TestCase):
    def test_itl_then_sth_with_a_gap_in_that_leg(self):
        bars = [{"t": T0 + 3600 * k, "o": 100, "h": 101, "l": 99, "c": 100.5} for k in range(20)]
        t = {"ITL": [{"i": 5, "level": 98.0, "known": 8}], "ITH": [], "STH": [{"i": 12, "level": 110.0, "known": 13}],
             "STL": [], "LTL": [], "LTH": []}
        gaps = [{"i": 4, "dir": 1, "top": 99.5, "bottom": 99.0, "known": 5},      # before the ITL: not in the leg
                {"i": 9, "dir": 1, "top": 104.0, "bottom": 102.0, "known": 10},
                {"i": 12, "dir": 1, "top": 109.0, "bottom": 108.0, "known": 13}]  # the STH bar itself: too late
        c = st._candidates(bars, t, gaps, 1, "fast", 24, 0.0)
        self.assertEqual(len(c), 1)
        sw, kind, itl, gap, known = c[0]
        self.assertEqual((kind, sw["level"], itl["level"], gap["top"], known), ("STH", 110.0, 98.0, 104.0, 13))
        self.assertEqual(st._candidates(bars, t, gaps, 1, "classic", 24, 0.0), [])   # no LTL, no classic

    def test_volume_gate_and_split_on_real_data(self):
        def run(*extra):
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                st.main(["confirm", "TSLA", "--offline", TSLA, "--data-interval", "5m", "--at", "2026-10-19 17:15",
                         "--json"] + list(extra))
            return json.loads(out.getvalue())
        both = run()
        self.assertEqual(set(both["by_pattern"]), {"classic", "fast"})
        fast = [r for r in both["sequences"] if r["pattern"] == "fast"]
        self.assertTrue(all(r["volume_rel"] >= 1.2 for r in fast))
        loose = run("--pattern", "fast", "--fast-vol", "0")
        self.assertGreater(loose["by_pattern"]["fast"]["sequences"], both["by_pattern"]["fast"]["sequences"])
        for r in loose["sequences"]:
            self.assertTrue(r["structure"].startswith(("ITL", "ITH")))

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _load import FIX, load

journal = load("trader-journal", "journal")

PLAN = os.path.join(FIX, "trader-budget", "plan-tsla.json")


def fill(at, side, qty, price, sym="TSLA"):
    return {"at": at, "date": at[:10], "status": "filled", "symbol": sym, "side": side,
            "qty": str(qty), "price": price}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.j = os.path.join(self.dir, "journal.json")
        self.state = os.path.join(self.dir, "broker.json")
        self.tm = os.path.join(self.dir, "timemachine.json")
        with open(PLAN) as fh:
            self.plan = json.load(fh)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = journal.main(list(argv) + ["--journal", self.j])
        return code, out.getvalue(), err.getvalue()

    def write(self, path, doc):
        with open(path, "w") as fh:
            json.dump(doc, fh)

    def doc(self):
        with open(self.j) as fh:
            return json.load(fh)


class RoundTrips(unittest.TestCase):
    def test_pairs_flat_to_flat_and_keeps_what_is_open(self):
        fills = journal.fills_from_state({"orders": [
            fill("2026-10-19T10:15:00-04:00", "buy", 8, 364.20),
            fill("2026-10-19T10:40:00-04:00", "buy", 2, 366.00),
            fill("2026-10-19T11:05:00-04:00", "sell", 5, 370.04),
            fill("2026-10-19T11:30:00-04:00", "sell", 5, 368.00),
            fill("2026-10-19T12:00:00-04:00", "buy", 3, 10.0, sym="KO"),
            {"status": "placed", "symbol": "TSLA"},
        ]})
        trips, still_open = journal.round_trips(fills)
        self.assertEqual(len(trips), 1)
        t = journal.trade_from_fills(trips[0])
        self.assertEqual((t["qty"], t["entry"], t["exit"]), (10, 364.56, 369.02))
        self.assertEqual((t["opened"], t["closed"], t["fills"]), ("10:15", "11:30", 4))
        self.assertEqual(still_open, [{"symbol": "KO", "shares": 3.0, "since": "2026-10-19T12:00:00-04:00"}])

    def test_oversell_is_refused(self):
        fills = journal.fills_from_state({"orders": [fill("2026-10-19T10:15:00-04:00", "sell", 1, 10.0)]})
        with self.assertRaises(journal.JournalError):
            journal.round_trips(fills)


class Scoring(Base):
    def test_stop_slippage_is_measured_in_r_and_dollars(self):
        plan = journal.plan_from(self.plan)
        t = {"symbol": "TSLA", "date": "2026-10-19", "closed_date": "2026-10-19", "opened": "10:15",
             "closed": "11:40", "qty": 8, "entry": 364.18, "exit": 358.10, "fees": 0}
        journal.score(t, plan)
        self.assertEqual(t["pnl"], -48.64)
        self.assertEqual(t["r"], -1.04)
        self.assertEqual(t["outcome"], "stop")
        self.assertEqual(t["stop_slip_usd"], 1.76)
        self.assertTrue(any(f.startswith("stop filled past the plan") for f in t["flags"]))

    def test_target_chase_and_late_exit(self):
        plan = journal.plan_from(self.plan)
        t = {"symbol": "TSLA", "date": "2026-10-19", "closed_date": "2026-10-19", "opened": "10:30",
             "closed": "15:58", "qty": 8, "entry": 366.00, "exit": 370.04, "fees": 1.0}
        journal.score(t, plan)
        self.assertEqual((t["outcome"], t["pnl"]), ("target", 31.32))
        self.assertTrue(any(f.startswith("chased the entry") for f in t["flags"]))
        self.assertTrue(any(f.startswith("held past flat_by") for f in t["flags"]))

    def test_no_plan_means_no_r(self):
        t = {"symbol": "KO", "date": "2026-10-19", "closed_date": "2026-10-20", "qty": 10,
             "entry": 60.0, "exit": 61.0, "fees": 0}
        journal.score(t, None)
        self.assertIsNone(t["r"])
        self.assertEqual(t["outcome"], "win")
        self.assertFalse(t["day_trade"])

    def test_time_machine_odds_attach_only_to_the_same_plan(self):
        tm = {"plan": dict(self.plan), "mc": {"p_target": 0.294, "p_stop": 0.255, "replays": 10000},
              "verdict": "close to a coin flip"}
        self.assertEqual(journal.plan_from(self.plan, tm)["odds"]["p_target"], 0.294)
        tm["plan"]["entry"] = 300.0
        self.assertNotIn("odds", journal.plan_from(self.plan, tm))

    def test_stop_above_entry_is_refused(self):
        bad = dict(self.plan, stop=400.0)
        with self.assertRaises(journal.JournalError):
            journal.plan_from(bad)


class Stats(unittest.TestCase):
    def trades(self, pnls, r=True):
        return [{"id": "T%d" % i, "symbol": "X", "date": "2026-10-%02d" % (i + 1), "pnl": p,
                 "r": (p / 50.0) if r else None, "setup": "orb", "opened": "10:15", "outcome": "manual",
                 "status": "closed", "flags": [], "day_trade": True, "plan": {"stop": 1}}
                for i, p in enumerate(pnls)]

    def test_summary_numbers(self):
        s = journal.summarize(self.trades([50, -25, -25, 100, -50]))
        self.assertEqual((s["trades"], s["wins"], s["losses"]), (5, 2, 3))
        self.assertEqual(s["win_rate"], 0.4)
        self.assertEqual(s["net_pnl"], 50)
        self.assertEqual(s["profit_factor"], 1.5)
        self.assertEqual(s["expectancy_usd"], 10)
        self.assertEqual(s["expectancy_r"], 0.2)
        self.assertEqual(s["max_drawdown"], 50)
        self.assertEqual(s["longest_losing_streak"], 2)
        self.assertEqual(s["payoff_ratio"], 2.25)
        self.assertEqual(s["breakeven_win_rate"], 0.3077)

    def test_empty_and_small_sample(self):
        doc = journal.stats_doc({"trades": [], "plans": []})
        self.assertEqual(doc["verdict"], "No closed trades yet.")
        doc = journal.stats_doc({"trades": self.trades([10, -5]), "plans": []})
        self.assertTrue(doc["small_sample"])
        self.assertIn("far too few", doc["verdict"])

    def test_calibration(self):
        ts = self.trades([50, -50, -50, -50])
        for t, o in zip(ts, ["target", "stop", "stop", "manual"]):
            t["outcome"] = o
            t["plan"] = {"odds": {"p_target": 0.5, "p_stop": 0.25}}
        c = journal.calibration(ts)
        self.assertEqual((c["predicted_target"], c["actual_target"]), (0.5, 0.25))
        self.assertEqual((c["predicted_stop"], c["actual_stop"]), (0.25, 0.5))
        self.assertEqual(c["brier_target"], 0.25)

    def test_filters(self):
        ts = self.trades([10, -5, 20])
        ts[1]["setup"] = "flag"
        doc = journal.stats_doc({"trades": ts, "plans": []}, since="2026-10-02", setup="orb")
        self.assertEqual(doc["summary"]["trades"], 1)
        self.assertEqual(doc["summary"]["net_pnl"], 20)


class Cli(Base):
    def test_snapshot_import_stats_end_to_end(self):
        plan_path = os.path.join(self.dir, "plan.json")
        self.write(plan_path, self.plan)
        self.write(self.tm, {"plan": self.plan, "mc": {"p_target": 0.294, "p_stop": 0.255}, "verdict": "coin flip"})
        code, out, _ = self.run_cli("snapshot", "--plan", plan_path, "--timemachine", self.tm)
        self.assertEqual(code, 0, out)
        self.assertIn("Time Machine 29.4 % target first", out)
        # the next trade overwrites plan.json: the snapshot still scores the first one
        self.write(plan_path, dict(self.plan, symbol="AAPL", entry=200.0, stop=199.0, target=202.0))
        self.write(self.state, {"orders": [
            fill("2026-10-19T10:15:00-04:00", "buy", 8, 364.18),
            fill("2026-10-19T11:40:00-04:00", "sell", 8, 370.04)]})
        args = ("import", "--state", self.state, "--plan", plan_path, "--timemachine", self.tm)
        code, out, err = self.run_cli(*args)
        self.assertEqual(code, 0, err)
        self.assertIn("Imported 1 new trade(s)", out)
        t = self.doc()["trades"][0]
        self.assertEqual((t["id"], t["outcome"], t["pnl"], t["r"]), ("TSLA-2026-10-19-1015", "target", 46.88, 1.0))
        self.assertEqual(t["plan"]["odds"]["p_target"], 0.294)
        code, out, _ = self.run_cli(*args)
        self.assertIn("Imported 0 new trade(s)", out)
        self.assertEqual(len(self.doc()["trades"]), 1)
        code, out, _ = self.run_cli("note", "--id", "TSLA-2026-10-19-1015", "--tag", "a-plus")
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli("stats")
        self.assertIn("win rate        100.0 %", out)
        self.assertIn("Time Machine vs reality", out)
        self.assertIn("a-plus", out)
        code, out, _ = self.run_cli("stats", "--json")
        self.assertEqual(json.loads(out)["summary"]["expectancy_r"], 1.0)

    def test_add_and_list(self):
        code, out, err = self.run_cli("add", "--symbol", "tsla", "--date", "2026-10-19", "--qty", "8",
                                      "--entry", "364.18", "--exit", "358.10", "--stop", "358.32",
                                      "--opened", "10:15", "--closed", "11:40", "--tag", "news")
        self.assertEqual(code, 0, err)
        self.assertIn("-1.04R", out)
        code, out, err = self.run_cli("add", "--symbol", "tsla", "--date", "2026-10-19", "--qty", "8",
                                      "--entry", "364.18", "--exit", "358.10", "--stop", "358.32",
                                      "--opened", "10:15", "--closed", "11:40")
        self.assertEqual(code, 1)
        self.assertIn("already in the journal", err)
        code, out, _ = self.run_cli("list")
        self.assertIn("TSLA-2026-10-19-1015", out)
        self.assertIn("stop filled past the plan", out)
        self.assertIn("[news]", out)

    def test_bad_input_is_a_clean_error(self):
        code, _, err = self.run_cli("add", "--symbol", "X", "--date", "2026-13-40", "--qty", "1",
                                    "--entry", "1", "--exit", "1")
        self.assertEqual(code, 1)
        self.assertIn("not a real date", err)
        code, _, err = self.run_cli("import", "--state", os.path.join(self.dir, "missing.json"),
                                    "--plan", os.path.join(self.dir, "none.json"))
        self.assertEqual(code, 1)
        self.assertIn("no broker log", err)


if __name__ == "__main__":
    unittest.main()


class Ratios(unittest.TestCase):
    def test_t_distribution_matches_tables(self):
        self.assertAlmostEqual(journal.t_two_sided_p(2.0, 10), 0.0734, places=4)
        self.assertAlmostEqual(journal.t_two_sided_p(1.0, 4), 0.3739, places=4)
        self.assertAlmostEqual(journal.t_two_sided_p(0.2, 2), 1 - 0.2 / (0.04 + 2) ** 0.5, places=6)

    def test_sqn_sharpe_sortino_and_expectancy_ratio(self):
        ts = [{"id": str(i), "date": "2026-10-%02d" % (i + 1), "pnl": p, "r": p / 50.0, "status": "closed"}
              for i, p in enumerate([50, -25, -25, 100, -50])]
        s = journal.summarize(ts)
        self.assertEqual(s["expectancy_ratio"], 0.3)          # (1 + 2.25) x 0.4 - 1
        self.assertEqual(s["sqn"], 0.36)                       # sqrt(5) x 0.2 / stdev(R) 1.255
        self.assertEqual(s["trading_days"], 5)
        self.assertIsNotNone(s["sharpe_daily"])
        self.assertGreater(s["sortino_daily"], s["sharpe_daily"])
        self.assertEqual(s["edge_on"], "R")
        self.assertGreater(s["edge_p"], 0.5)
        self.assertEqual(journal.sqn_label(2.2), "good")

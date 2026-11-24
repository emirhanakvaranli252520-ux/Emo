import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _load import FIX, ROOT, load

check = load("trader-risk", "check")

CFG_PATH = os.path.join(ROOT, "trader-budget", "config.example.json")
TSLA_PATH = os.path.join(FIX, "trader-risk", "orders-tsla.json")
NOW = check.parse_now("2026-10-19 10:15")
PORTFOLIO = {"cash": 5000, "positions": []}
PRICES = {"TSLA": 364.18}


def cfg(prot):
    with open(CFG_PATH) as fh:
        c = json.load(fh)
    c["protections"] = prot
    return c


def tsla():
    with open(TSLA_PATH) as fh:
        return json.load(fh)["orders"][0]


def trade(sym, date, closed, pnl, r, outcome, setup="orb"):
    return {"id": "%s-%s" % (sym, closed), "symbol": sym, "date": date, "closed_date": date,
            "closed": closed, "pnl": pnl, "r": r, "outcome": outcome, "setup": setup, "status": "closed"}


def run(journal, prot, orders=None):
    return check.check(orders or [tsla()], cfg(prot), PORTFOLIO, PRICES, None, "2026-10-19", NOW,
                       None, journal)


class Protections(unittest.TestCase):
    def reasons(self, res):
        return " | ".join(res["results"][0]["reasons"])

    def test_off_without_a_protections_block(self):
        j = {"trades": [trade("TSLA", "2026-10-19", "10:05", -46, -1.0, "stop")] * 5}
        res = check.check([tsla()], cfg({}), PORTFOLIO, PRICES, None, "2026-10-19", NOW, None, j)
        self.assertEqual(res["results"][0]["verdict"], "PASS")
        self.assertEqual(res["protections"], [])

    def test_cooldown_blocks_the_same_symbol_only(self):
        j = {"trades": [trade("TSLA", "2026-10-19", "10:00", 20, 0.5, "manual")]}
        res = run(j, {"cooldown": {"minutes": 30}})
        self.assertEqual(res["results"][0]["verdict"], "BLOCK")
        self.assertIn("no re-entry for 30 minutes, until 10:30", self.reasons(res))
        res = run(j, {"cooldown": {"minutes": 10}})
        self.assertEqual(res["results"][0]["verdict"], "PASS")
        other = {"trades": [trade("AAPL", "2026-10-19", "10:00", 20, 0.5, "manual")]}
        self.assertEqual(run(other, {"cooldown": {"minutes": 30}})["results"][0]["verdict"], "PASS")

    def test_stop_guard_counts_stops_in_the_lookback(self):
        j = {"trades": [trade("AAPL", "2026-10-16", "11:00", -40, -1.0, "stop"),
                        trade("NVDA", "2026-10-19", "09:50", -45, -1.0, "stop")]}
        res = run(j, {"stop_guard": {"lookback_days": 1, "trade_limit": 2}})
        self.assertEqual(res["results"][0]["verdict"], "PASS")          # Friday's stop is outside 1 day
        res = run(j, {"stop_guard": {"lookback_days": 2, "trade_limit": 2}})
        self.assertEqual(res["results"][0]["verdict"], "BLOCK")
        self.assertIn("2 stopped-out trades", self.reasons(res))

    def test_max_drawdown(self):
        j = {"trades": [trade("A", "2026-10-15", "11:00", 100, 2, "target"),
                        trade("B", "2026-10-16", "11:00", -90, -1, "stop"),
                        trade("C", "2026-10-19", "09:55", -80, -1, "stop")]}
        res = run(j, {"max_drawdown": {"lookback_days": 5, "max_drawdown_usd": 150}})
        self.assertEqual(res["results"][0]["verdict"], "BLOCK")
        self.assertIn("down $170 from the peak", self.reasons(res))
        res = run(j, {"max_drawdown": {"lookback_days": 5, "max_drawdown_usd": 200}})
        self.assertEqual(res["results"][0]["verdict"], "PASS")

    def test_losing_setup_locks_that_setup_only(self):
        j = {"trades": [trade("X", "2026-10-%02d" % d, "11:00", -10, -0.4, "manual") for d in (12, 13, 14, 15, 16)]}
        res = run(j, {"losing_setup": {"lookback_trades": 10, "trade_limit": 5, "min_expectancy_r": 0}})
        self.assertEqual(res["results"][0]["verdict"], "BLOCK")
        self.assertIn("the orb setup's last 5 trades average -0.40R", self.reasons(res))
        for t in j["trades"]:
            t["setup"] = "flag"
        res = run(j, {"losing_setup": {"lookback_trades": 10, "trade_limit": 5}})
        self.assertEqual(res["results"][0]["verdict"], "PASS")

    def test_exits_are_never_locked(self):
        j = {"trades": [trade("TSLA", "2026-10-19", "10:00", -46, -1.0, "stop")] * 3}
        sell = {"symbol": "TSLA", "side": "sell", "qty": "8", "type": "market", "time_in_force": "day"}
        pf = {"cash": 2000, "positions": [{"ticker": "TSLA", "shares": 8}]}
        res = check.check([sell], cfg({"stop_guard": {"lookback_days": 1, "trade_limit": 1},
                                       "cooldown": {"minutes": 60}}), pf, PRICES, None, "2026-10-19", NOW,
                          None, j)
        self.assertEqual(res["results"][0]["verdict"], "PASS")
        self.assertEqual(res["results"][0]["kind"], "exit")

    def test_future_trades_are_ignored_and_bad_config_is_an_error(self):
        j = {"trades": [trade("TSLA", "2026-10-19", "11:00", -46, -1.0, "stop")]}
        self.assertEqual(run(j, {"cooldown": {"minutes": 30}})["results"][0]["verdict"], "PASS")
        with self.assertRaises(check.RiskError):
            run(j, {"nap_time": {}})
        with self.assertRaises(check.RiskError):
            run(j, {"cooldown": {"minutes": "soon"}})

    def test_no_journal_is_a_warning(self):
        res = run(None, {"cooldown": {"minutes": 30}})
        self.assertEqual(res["results"][0]["verdict"], "PASS")
        self.assertTrue(any("no trader/journal.json" in w for w in res["warnings"]))

    def test_cli_reads_the_journal(self):
        d = tempfile.mkdtemp()
        paths = {}
        for name, doc in (("orders", {"orders": [tsla()]}), ("config", cfg({"cooldown": {"minutes": 30}})),
                          ("portfolio", PORTFOLIO), ("prices", {"prices": PRICES}),
                          ("journal", {"trades": [trade("TSLA", "2026-10-19", "10:00", 5, 0.1, "manual")]})):
            paths[name] = os.path.join(d, name + ".json")
            with open(paths[name], "w") as fh:
                json.dump(doc, fh)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = check.main(["--orders", paths["orders"], "--config", paths["config"], "--portfolio",
                               paths["portfolio"], "--prices", paths["prices"], "--journal", paths["journal"],
                               "--state", os.path.join(d, "none.json"), "--now", "2026-10-19 10:15",
                               "--no-write"])
        self.assertEqual(code, 1)
        self.assertIn("Protections active: cooldown TSLA until 10:30", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class RewardRiskBand(unittest.TestCase):
    def test_over_max_reward_risk_warns_but_passes(self):
        c = cfg({})
        c.update(min_reward_risk=0.5, max_reward_risk=0.8)
        res = check.check([tsla()], c, PORTFOLIO, PRICES, None, "2026-10-19", NOW, None, None)
        r = res["results"][0]
        self.assertEqual(r["verdict"], "PASS")
        self.assertTrue(any("over your max_reward_risk 0.8" in w for w in r["warnings"]))
        c.update(min_reward_risk=1.5, max_reward_risk=3.5)
        r = check.check([tsla()], c, PORTFOLIO, PRICES, None, "2026-10-19", NOW, None, None)["results"][0]
        self.assertEqual(r["verdict"], "BLOCK")             # the reel's 1R target is under a 1.5 minimum
        self.assertTrue(any("under your minimum 1.5" in x for x in r["reasons"]))

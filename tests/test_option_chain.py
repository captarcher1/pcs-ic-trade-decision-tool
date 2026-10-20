"""Offline tests for data/option_chain.py (no network). Run: python -m unittest discover tests"""
import datetime, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import option_chain as oc
from data.option_chain import Contract

D = datetime.date


def C(cp, k, bid, ask, delta, iv=0.2, oi=500, root="SPXW", exp=D(2026, 11, 16)):
    return Contract(root, exp, cp, float(k), bid, ask, delta, iv, oi, 10)


def put_chain():
    # shorts at 7285 (.149) 7240 (.109) with longs 25 lower
    return [C("P", 7285, 5.0, 5.4, -.149), C("P", 7260, 2.0, 2.4, -.10),
            C("P", 7240, 4.0, 4.4, -.109), C("P", 7215, 1.5, 1.9, -.07),
            C("P", 7200, 6.0, 6.4, -.20),   # above cap
            C("P", 7000, 1.0, 1.2, -.05)]   # below floor


class T(unittest.TestCase):
    def test_delta_band_and_credit(self):
        rows, hidden = oc.build_rows(put_chain(), "P", 25, True)
        self.assertTrue(rows)
        for r in rows:
            self.assertLessEqual(r["delta"], 0.15)
            self.assertGreaterEqual(r["delta"], 0.07)
            self.assertLess(r["long_strike"], r["short_strike"])
            self.assertLessEqual(r["bid"], r["mid"])
            self.assertLessEqual(r["mid"], r["ask"])
        r = next(x for x in rows if x["short_strike"] == 7285)
        self.assertEqual(r["long_strike"], 7260)
        self.assertAlmostEqual(r["mid"], 5.2 - 2.2, 2)
        self.assertAlmostEqual(r["bid"], 5.0 - 2.4, 2)
        self.assertAlmostEqual(r["ask"], 5.4 - 2.0, 2)

    def test_missing_long_leg_hidden(self):
        rows, hidden = oc.build_rows([C("P", 7285, 5.0, 5.4, -.149)], "P", 25, True)
        self.assertEqual(rows, []); self.assertEqual(hidden, 1)

    def test_wide_spread_and_zero_bid_hidden(self):
        ch = [C("P", 7285, 1.0, 3.0, -.149), C("P", 7260, 0.5, 0.6, -.1),
              C("P", 7240, 0.0, 0.5, -.109), C("P", 7215, 0.1, 0.2, -.08)]
        rows, hidden = oc.build_rows(ch, "P", 25, True)
        self.assertEqual(rows, []); self.assertEqual(hidden, 4)  # 7285 wide, 7260 no long leg, 7240 zero bid, 7215 no long leg

    def test_open_interest_only_for_non_index(self):
        ch = [C("P", 100, 1.0, 1.1, -.10, oi=5), C("P", 95, .5, .6, -.07, oi=5)]
        self.assertEqual(oc.build_rows(ch, "P", 5, False)[0], [])
        self.assertTrue(oc.build_rows(ch, "P", 5, True)[0])

    def test_call_side(self):
        ch = [C("C", 8055, 3.0, 3.2, .149), C("C", 8080, 0.8, 1.0, .08)]
        rows, _ = oc.build_rows(ch, "C", 25, True)
        self.assertEqual(rows[0]["long_strike"], 8080)

    def test_pair_ic_same_tier(self):
        p = [{"tier": 15}, {"tier": 11}]; c = [{"tier": 11}, {"tier": 9}]
        self.assertEqual([x["tier"] for x in oc.pair_ic(p, c)], [11])

    def test_pair_ic_distance(self):
        spot = 7000.0
        def row(k, d): return {"short_strike": k, "delta": d, "tier": int(d * 100)}
        puts = [row(6900, .15), row(6850, .11)]            # 100 and 150 below spot
        calls = [row(7100, .09), row(7105, .09), row(7150, .07), row(7300, .05)]
        pairs, unpaired = oc.pair_ic_distance(puts, calls, spot)
        self.assertEqual([(x["put"]["short_strike"], x["call"]["short_strike"]) for x in pairs], [(6900, 7100), (6850, 7150)])
        self.assertEqual(pairs[0]["dist_gap"], 0.0)
        self.assertEqual(unpaired, 0)
        # nothing near the needed distance -> unpaired, not forced
        pairs, unpaired = oc.pair_ic_distance([row(6500, .10)], calls, spot)
        self.assertEqual((pairs, unpaired), ([], 1))
        # each call used once
        pairs, _ = oc.pair_ic_distance([row(6900, .15), row(6902, .14)], calls, spot)
        self.assertEqual(len({x["call"]["short_strike"] for x in pairs}), len(pairs))

    def test_build_all_returns_every_eligible(self):
        rows = oc.build_all(put_chain(), "P", 25, True)
        self.assertTrue(all(0.07 <= r["delta"] <= 0.15 for r in rows))

    def test_call_floor_param_and_cheap_spread_allowance(self):
        ch = [C("C", 8100, 0.25, 0.35, .02), C("C", 8125, 0.05, 0.10, .01)]   # 0.10 spread on a 0.30 mid = 33%
        self.assertEqual(oc.build_all(ch, "C", 25, True), [])                 # default floor 7%
        rows = oc.build_all(ch, "C", 25, True, floor=0.01)
        self.assertEqual(len(rows), 1)                                        # allowed: spread <= $0.10

    def test_pair_ic_tier_adds_distances(self):
        p = [{"tier": 15, "short_strike": 7000.0}]; c = [{"tier": 15, "short_strike": 7500.0}]
        r = oc.pair_ic(p, c, 7200.0)[0]
        self.assertEqual((r["dist_put"], r["dist_call"]), (200.0, 300.0))

    def test_expiry_choice(self):
        today = D(2026, 10, 19)  # +28d = 2026-11-16
        av = [("SPX", D(2026, 11, 20)), ("SPXW", D(2026, 11, 18)), ("SPXW", D(2026, 11, 13)), ("SPXW", D(2026, 12, 30))]
        self.assertEqual(oc.choose_expiry(av, 4, today, ["SPXW", "SPX"]), ("SPXW", D(2026, 11, 18)))
        self.assertIsNone(oc.choose_expiry([("SPXW", D(2026, 12, 30))], 4, today))
        self.assertIsNone(oc.choose_expiry([("X", D(2026, 10, 1))], 1, today))

    def test_bs_delta(self):
        d = oc.bs_delta(100, 100, 30 / 365, 0.04, 0, 0.2, True)
        self.assertTrue(0.5 < d < 0.56)
        self.assertAlmostEqual(oc.bs_delta(100, 80, .1, .04, 0, .2, False), oc.bs_delta(100, 80, .1, .04, 0, .2, True) - 1, 6)
        self.assertIsNone(oc.bs_delta(100, 100, 0, .04, 0, .2, True))

    def test_parse_cboe(self):
        payload = {"timestamp": "2026-10-19 10:30:00", "data": {"current_price": 7000.5, "options": [
            {"option": "SPXW261116P07285000", "bid": 5, "ask": 5.4, "iv": .2, "delta": -.149, "open_interest": 10, "volume": 3},
            {"option": "garbage"}]}}
        cs, meta = oc._parse_cboe(payload)
        self.assertEqual(len(cs), 1)
        self.assertEqual((cs[0].root, cs[0].cp, cs[0].strike, cs[0].expiry), ("SPXW", "P", 7285.0, D(2026, 11, 16)))
        self.assertEqual(meta["spot"], 7000.5)
        with self.assertRaises(oc.ChainError):
            oc._parse_cboe({"data": {"options": []}})

    def test_fallback_to_yfinance(self):
        oc.clear_cache()
        o1, o2 = oc._from_cboe, oc._from_yfinance
        try:
            def boom(*a): raise oc.ChainError("down")
            oc._from_cboe = boom
            oc._from_yfinance = lambda *a: {"ok": True, "source": "yfinance"}
            r = oc.get_candidates("SPX", 4, 25, 25)
            self.assertEqual(r["source"], "yfinance"); self.assertIn("down", r["fallback_reason"])
            oc._from_yfinance = boom
            with self.assertRaises(oc.ChainError): oc.get_candidates("SPX", 4, 25, 25)
        finally:
            oc._from_cboe, oc._from_yfinance = o1, o2

    def test_cboe_all_zero_quotes_raises(self):
        zero = [C("P", 700 - i, 0.0, 0.0, -.1, root="SPY", exp=D(2026, 11, 13)) for i in range(50)]
        orig = oc._load_cboe
        try:
            oc._load_cboe = lambda t: ({"contracts": zero, "meta": {"spot": 765.0, "quote_timestamp": "x"}}, 0)
            with self.assertRaises(oc.ChainError):
                oc._from_cboe("SPY", 4, 5, 5, False, D(2026, 10, 20))
        finally:
            oc._load_cboe = orig

    def test_hybrid_uses_cboe_delta_with_yf_quotes(self):
        today, exp = D(2026, 10, 20), D(2026, 11, 17)
        raw = [{"root": "SPY", "cp": "P", "strike": 700.0, "bid": 2.0, "ask": 2.1, "iv": .2, "oi": 1000, "volume": 5},
               {"root": "SPY", "cp": "P", "strike": 695.0, "bid": 1.5, "ask": 1.6, "iv": .2, "oi": 1000, "volume": 5}]
        cboe = [Contract("SPY", exp, "P", 700.0, 0, 0, -.12, .2, 0, 0), Contract("SPY", exp, "P", 695.0, 0, 0, -.10, .2, 0, 0)]
        o1, o2 = oc._load_yf_expiries, oc._load_yf_chain
        try:
            oc._load_yf_expiries = lambda t: ({"exps": [exp.isoformat()], "spot": 765.0}, 0)
            oc._load_yf_chain = lambda t, e: (raw, 0)
            r = oc._from_yfinance("SPY", 4, 5, 5, False, today, cboe)
            self.assertEqual(r["source"], "hybrid"); self.assertFalse(r["delta_estimated"])
            self.assertEqual(r["put_rows"][0]["delta"], 0.12)
            self.assertAlmostEqual(r["put_rows"][0]["mid"], 2.05 - 1.55, 2)
            r2 = oc._from_yfinance("SPY", 4, 5, 5, False, today, None)   # no Cboe -> Black-Scholes
            self.assertEqual(r2["source"], "yfinance"); self.assertTrue(r2["delta_estimated"])
        finally:
            oc._load_yf_expiries, oc._load_yf_chain = o1, o2

    def test_vix_rank_not_applicable(self):
        self.assertFalse(oc.get_vix_rank("AAPL")["applicable"])


if __name__ == "__main__":
    unittest.main()

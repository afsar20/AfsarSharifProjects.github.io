"""Accounting identities, time boundaries, statistical edges and feasibility."""
import unittest
from dataclasses import replace
import numpy as np
import pandas as pd

from research.strategist_lab.data import parse_french,load_data
from research.strategist_lab.execution import clean_fills,account_ledger,cost_model,simulate_ledger,ExecutionConfig
from research.strategist_lab.portfolio import (allocate,covariance,risk_contributions,
    scenario_risk,coverage_tests,make_books,walk_forward,factor_decomposition,RiskConfig,BOOK_WEIGHTS)


class PublicDataTests(unittest.TestCase):
    def test_first_table_and_percentage_conversion(self):
        text='metadata\n,A,B\n20200102,1.2,-0.3\n20200103,0.0,2.0\n\nEqual weighted\n,A,B\n20200102,90,90\n'
        result=parse_french(text)
        self.assertEqual(len(result),2)
        self.assertAlmostEqual(result.iloc[0,0],.012)
        self.assertAlmostEqual(result.iloc[0,1],-.003)

    def test_missing_sentinel_is_rejected(self):
        with self.assertRaises(ValueError):parse_french(',A\n20200102,-99.99\n')

    def test_frozen_files_match_manifest(self):
        industry,factors=load_data()
        self.assertTrue(industry.index.equals(factors.index))
        self.assertEqual(industry.shape,(2766,10))


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.orders=pd.DataFrame({"order_id":[1,2,3],"date":["2025-01-02"]*3,
            "side":[1,-1,1],"qty":[100,100,100],"decision_price":[100.]*3,
            "arrival_price":[101.,99.,100.],"benchmark_price":[102.,98.,100.],
            "end_price":[105.,95.,102.]})
        self.fills=pd.DataFrame({"fill_id":[1,2,3],"order_id":[1,1,2],
            "qty":[30,30,100],"price":[103.,103.,97.],"fee":[.3,.3,1.],"latency_ms":[10.]*3})

    def test_buy_sell_partial_and_unfilled_pnl_reconcile(self):
        detail,_,errors=account_ledger(self.orders,self.fills)
        self.assertAlmostEqual(detail.loc[0,"is_usd"],380.6)
        self.assertAlmostEqual(detail.loc[0,"net_pnl_usd"],119.4)
        self.assertAlmostEqual(detail.loc[1,"is_usd"],301.)
        self.assertAlmostEqual(detail.loc[2,"opportunity_usd"],200.)
        self.assertAlmostEqual(detail.loc[2,"net_pnl_usd"],0.)
        self.assertLess(max(errors.values()),1e-8)

    def test_retry_idempotence(self):
        raw=pd.concat([self.fills,self.fills.iloc[[0]]],ignore_index=True)
        clean,report=clean_fills(self.orders,raw)
        self.assertEqual(len(clean),3)
        self.assertEqual(report["exact_retries_removed"],1)

    def test_conflicting_retry_fails(self):
        extra=self.fills.iloc[[0]].copy();extra["price"]=999
        with self.assertRaises(ValueError):clean_fills(self.orders,pd.concat([self.fills,extra]))

    def test_orphan_and_negative_price_are_quarantined(self):
        raw=self.fills.copy();raw.loc[0,"order_id"]=999;raw.loc[1,"price"]=-2
        clean,report=clean_fills(self.orders,raw)
        self.assertEqual(len(clean),1)
        self.assertEqual(report["rejected_rows"],2)

    def test_overfill_fails(self):
        raw=self.fills.copy();raw.loc[0,"qty"]=100
        with self.assertRaises(ValueError):clean_fills(self.orders,raw)

    def test_detector_features_exclude_labels_and_realised_latency(self):
        transformer=cost_model(1).named_steps["features"]
        columns=sum([list(item[2]) for item in transformer.transformers],[])
        self.assertNotIn("router_incident",columns)
        self.assertNotIn("latency_ms",columns)

    def test_market_volatility_feature_has_no_future_dependency(self):
        _,factors=load_data();changed=factors.copy();cut=pd.Timestamp("2025-08-01")
        changed.loc[cut:,"Mkt-RF"]*=3
        config=ExecutionConfig(orders_per_day=10)
        before,*_=simulate_ledger(factors,config);after,*_=simulate_ledger(changed,config)
        pd.testing.assert_frame_equal(before.loc[before.date<=cut],after.loc[after.date<=cut])


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.default_rng(93)
        values=self.rng.normal(0,.01,(300,6))
        self.cov,_=covariance(values);self.w=np.full(6,1/6)

    def test_euler_contributions_sum_to_volatility(self):
        sigma,rc=risk_contributions(self.w,self.cov)
        self.assertAlmostEqual(rc.sum(),sigma,places=12)

    def test_shrunk_covariance_is_positive_semidefinite(self):
        self.assertGreaterEqual(np.linalg.eigvalsh(self.cov).min(),-1e-12)

    def test_scenarios_remain_psd_and_scale_with_leverage(self):
        a,_,_=scenario_risk(self.cov,self.w,1,.5,1)
        b,_,matrix=scenario_risk(self.cov,self.w,1,.5,2)
        self.assertAlmostEqual(b,2*a)
        self.assertGreaterEqual(np.linalg.eigvalsh(matrix).min(),-1e-12)

    def test_allocator_respects_caps_and_turnover(self):
        cfg=RiskConfig()
        for method in ["equal","inverse_vol","minimum_variance"]:
            w=allocate(self.cov,self.w,method,cfg)
            self.assertAlmostEqual(w.sum(),1.)
            self.assertLessEqual(w.max(),cfg.cap+1e-8)
            self.assertGreaterEqual(w.min(),cfg.floor-1e-8)
            self.assertLessEqual(np.abs(w-self.w).sum()/2,cfg.one_way_turnover_limit+1e-8)

    def test_coverage_zero_and_all_exception_edges_are_finite(self):
        for hits in [np.zeros(100),np.ones(100),np.tile([0,0,0,1],25)]:
            score=coverage_tests(hits)
            self.assertTrue(np.isfinite(score["uc_p"]))
            self.assertTrue(np.isfinite(score["independence_p"]))

    def test_books_have_disclosed_unit_gross_exposure(self):
        np.testing.assert_allclose(np.abs(BOOK_WEIGHTS).sum(axis=1),1)

    def test_factor_sample_variance_reconciles(self):
        industries,factors=load_data();books,_=make_books(industries,factors)
        part=books.iloc[-252:]
        decomposition=factor_decomposition(part,factors.loc[part.index],self.w)
        self.assertLess(decomposition["reconciliation_error"],1e-10)

    def test_future_mutation_does_not_change_earlier_allocations_or_forecasts(self):
        industries,factors=load_data();books,_=make_books(industries,factors)
        small=books.iloc[-100:];f=factors.loc[small.index].copy()
        cut=small.index[-20];changed=small.copy();changed.loc[cut:]*=-2
        changed_f=f.copy();changed_f.loc[cut:,"RF"]+=.001
        cfg=RiskConfig(lookback=30,evaluation_start=str(small.index[40].date()))
        a,_,_=walk_forward(small,f,cfg);b,_,_=walk_forward(changed,changed_f,cfg)
        pd.testing.assert_frame_equal(a.loc[a.date<cut].reset_index(drop=True),b.loc[b.date<cut].reset_index(drop=True))
        today=a.date==cut;other=b.date==cut
        np.testing.assert_allclose(a.loc[today,"var99"],b.loc[other,"var99"])
        self.assertTrue((a.forecast_max_date<a.date).all())


if __name__=="__main__":unittest.main()

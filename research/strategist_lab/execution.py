"""Seeded synthetic order ledger, audited SQL accounting and frozen monitoring.

All orders, quotes, fills, venues, alpha and incidents are simulated. Historical
market volatility is the only real market input. This is an engineering and
statistical validation experiment, not evidence about any execution venue.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import OUTPUT

@dataclass(frozen=True)
class ExecutionConfig:
    seed: int = 20261025
    orders_per_day: int = 400
    train_days: int = 126
    validation_days: int = 63
    bootstrap_samples: int = 1500
    router_shift_bps: float = 6.
    alpha_decay_bps: float = 13.


def simulate_ledger(factors: pd.DataFrame, config: ExecutionConfig):
    rng = np.random.default_rng(config.seed)
    dates = factors.loc["2025"].index
    # Shift before reindexing: no current-session return enters an order feature.
    vol_series = factors["Mkt-RF"].rolling(20).std().shift(1).reindex(dates) * 10000
    n = len(dates) * config.orders_per_day
    day = np.repeat(np.arange(len(dates)), config.orders_per_day)
    strategy = rng.choice(["StatArb", "Momentum", "Rebalance"], n, p=[.4,.35,.25])
    venue = rng.choice(["Venue A", "Venue B", "Venue C"], n, p=[.45,.35,.2])
    side = rng.choice([-1,1], n)
    price = rng.uniform(20,250,n)
    qty = (rng.lognormal(7.3,.8,n).astype(int) // 10 + 1) * 10
    participation = rng.uniform(.002,.15,n)
    volatility = vol_series.to_numpy()[day]
    spread = rng.uniform(.5,5,n) + .008*volatility
    urgency = rng.choice([0,1],n,p=[.7,.3])
    forecast = np.where(strategy=="StatArb",5.,np.where(strategy=="Momentum",8.,2.))
    truth_router = (day >= 210) & (day < 225) & (venue=="Venue B")
    truth_alpha = (day >= 235) & (strategy=="Momentum")
    actual_alpha = forecast - np.where(truth_alpha,config.alpha_decay_bps,0.)
    end_move = side * (actual_alpha + rng.normal(0,14,n))
    end_price = price * (1 + end_move/10000)
    arrival = price * (1 + side * rng.normal(.3,.8,n)/10000)
    benchmark = arrival * (1 + side * rng.normal(.2,1.0,n)/10000)
    fraction = np.clip(rng.beta(13,2,n) - .16*truth_router, .1,1)
    fraction[rng.random(n)<.035] = 0
    filled = np.floor(qty*fraction).astype(int)
    orders = pd.DataFrame({"order_id":np.arange(n), "date":dates.to_numpy()[day],
        "strategy":strategy,"venue":venue,"side":side,"qty":qty,
        "decision_price":price,"arrival_price":arrival,"benchmark_price":benchmark,
        "end_price":end_price,"participation":participation,"volatility_bps":volatility,
        "spread_bps":spread,"urgency":urgency,"forecast_bps":forecast})
    # Generate three child fills for each filled parent. Their aggregate conserves quantity.
    parent = np.flatnonzero(filled>=3)
    parent_idx = np.repeat(parent,3)
    first = filled[parent]//3
    quantities = np.column_stack([first,first,filled[parent]-2*first]).ravel()
    latency = rng.lognormal(2.6,.45,len(parent_idx)) + 180*truth_router[parent_idx]
    baseline = (.18 + .38*spread[parent_idx] + .009*volatility[parent_idx]
                + 6*np.sqrt(participation[parent_idx]) + .7*urgency[parent_idx]
                + np.where(venue[parent_idx]=="Venue B",.35,0)
                + np.where(venue[parent_idx]=="Venue C",-.25,0))
    execution_bps = baseline + rng.normal(0,.9,len(parent_idx)) + config.router_shift_bps*truth_router[parent_idx]
    fill_price = benchmark[parent_idx] + side[parent_idx]*price[parent_idx]*execution_bps/10000
    fills = pd.DataFrame({"fill_id":np.arange(len(parent_idx)),"order_id":parent_idx,
        "qty":quantities,"price":fill_price,"fee":quantities*price[parent_idx]*.12/10000,
        "latency_ms":latency})
    # Realistic feed defects with disjoint fill IDs: exact retries, orphan, bad price.
    retries = fills.sample(frac=.01,random_state=config.seed).copy()
    invalid = fills.iloc[:2].copy()
    invalid["fill_id"] = [len(fills),len(fills)+1]
    invalid.loc[invalid.index[0],"order_id"] = n+10
    invalid.loc[invalid.index[1],"price"] = -1
    dirty = pd.concat([fills,retries,invalid],ignore_index=True)
    truth = pd.DataFrame({"order_id":orders.order_id,"router_incident":truth_router,"alpha_incident":truth_alpha})
    return orders, dirty, truth


def clean_fills(orders: pd.DataFrame, raw: pd.DataFrame):
    if orders.order_id.duplicated().any():
        raise ValueError("Duplicate parent order ID")
    dup = raw[raw.fill_id.duplicated(keep=False)]
    if len(dup) and (dup.groupby("fill_id").nunique(dropna=False)>1).any().any():
        raise ValueError("Conflicting duplicate fill ID; quarantine source before accounting")
    unique = raw.drop_duplicates("fill_id").copy()
    orphan = ~unique.order_id.isin(orders.order_id)
    invalid = (~np.isfinite(unique[["qty","price","fee","latency_ms"]]).all(axis=1)
               | (unique.qty<=0) | (unique.price<=0) | (unique.fee<0) | (unique.latency_ms<0))
    clean = unique.loc[~(orphan|invalid)].copy()
    total = clean.groupby("order_id").qty.sum().reindex(orders.order_id,fill_value=0).to_numpy()
    if (total>orders.qty.to_numpy()).any():
        raise ValueError("Aggregate fill quantity exceeds parent quantity")
    return clean, {"raw_rows":len(raw),"clean_rows":len(clean),
        "exact_retries_removed":len(raw)-len(unique),"orphan_rows":int(orphan.sum()),
        "invalid_rows":int(invalid.sum()),"rejected_rows":int((orphan|invalid).sum())}


def account_ledger(orders, fills, database=":memory:"):
    connection = sqlite3.connect(database)
    try:
        orders = orders.copy()
        orders["date"] = pd.to_datetime(orders.date).dt.strftime("%Y-%m-%d")
        orders.to_sql("orders",connection,index=False,if_exists="replace")
        fills.to_sql("fills",connection,index=False,if_exists="replace")
        connection.executescript("CREATE UNIQUE INDEX order_key ON orders(order_id);"
                                 "CREATE UNIQUE INDEX fill_key ON fills(fill_id);"
                                 "CREATE INDEX fill_parent ON fills(order_id);")
        connection.executescript((Path(__file__).parent/"sql/diagnostics.sql").read_text())
        detail = pd.read_sql_query("SELECT * FROM order_diagnostics ORDER BY order_id",connection)
        daily = pd.read_sql_query("SELECT * FROM daily_production ORDER BY date",connection)
    finally:
        connection.close()
    parts = detail[["delay_usd","market_usd","execution_usd","opportunity_usd","fees"]].sum(axis=1)
    error = np.max(np.abs(parts-detail.is_usd))
    pnl_error = np.max(np.abs(detail.ideal_pnl_usd-detail.net_pnl_usd-detail.is_usd))
    if max(error,pnl_error)>1e-6:
        raise ArithmeticError("P&L bridge does not reconcile")
    return detail,daily,{"max_cost_error_usd":float(error),"max_pnl_error_usd":float(pnl_error)}


def cost_model(alpha):
    numeric = ["spread_bps","volatility_bps","sqrt_participation","urgency"]
    return Pipeline([("features",ColumnTransformer([
        ("numeric",StandardScaler(),numeric),
        ("categorical",OneHotEncoder(handle_unknown="ignore"),["venue","strategy"])])),
        ("ridge",Ridge(alpha=alpha))])


def block_interval(values, rng, samples=1500, block=5):
    """Moving-block bootstrap of daily means. No iid child-fill resampling."""
    x = np.asarray(values,dtype=float)
    if len(x)<block:
        raise ValueError("Not enough sessions for block bootstrap")
    starts = rng.integers(0,len(x)-block+1,(samples,int(np.ceil(len(x)/block))))
    draws = x[(starts[...,None]+np.arange(block)).reshape(samples,-1)[:,:len(x)]]
    return np.quantile(draws.mean(axis=1),[.025,.975]).tolist()


def run_execution(factors, config=ExecutionConfig(), output=OUTPUT/"execution", keep_db=False):
    output.mkdir(parents=True,exist_ok=True)
    orders, raw, truth = simulate_ledger(factors,config)
    fills, quality = clean_fills(orders,raw)
    database = output/"ledger.sqlite" if keep_db else ":memory:"
    if keep_db and Path(database).exists():
        Path(database).unlink()
    detail,daily,reconciliation = account_ledger(orders,fills,database)
    detail["sqrt_participation"] = np.sqrt(detail.participation)
    dates = sorted(detail.date.unique())
    train_end = dates[config.train_days-1]
    val_end = dates[config.train_days+config.validation_days-1]
    train = (detail.date<=train_end)&detail.execution_bps.notna()
    val = (detail.date>train_end)&(detail.date<=val_end)&detail.execution_bps.notna()
    test = (detail.date>val_end)&detail.execution_bps.notna()
    candidates=[]
    for alpha in [.1,1.,10.,100.]:
        model=cost_model(alpha).fit(detail.loc[train],detail.loc[train,"execution_bps"])
        mae=mean_absolute_error(detail.loc[val,"execution_bps"],model.predict(detail.loc[val]))
        candidates.append((float(mae),alpha,model))
    validation_mae,alpha,model = min(candidates,key=lambda item:item[0])
    # Keep the training-only model so the calibration residuals remain held out.
    detail["expected_execution_bps"] = model.predict(detail)
    detail["residual_bps"] = detail.execution_bps-detail.expected_execution_bps
    detail["alpha_error_bps"] = detail.ideal_pnl_usd/detail.decision_notional*10000-detail.forecast_bps
    # Group-level detector has a separate held-out calibration distribution per venue / book.
    venue_daily = detail.loc[detail.execution_bps.notna()].groupby(["date","venue"]).agg(
        residual_bps=("residual_bps","mean"),latency_ms=("latency_ms","median"),
        observed_bps=("execution_bps","mean"),expected_bps=("expected_execution_bps","mean"),
        orders=("order_id","size")).reset_index()
    book_daily = detail.groupby(["date","strategy"]).agg(
        alpha_error_bps=("alpha_error_bps","mean"),orders=("order_id","size")).reset_index()
    calibrations={}
    for frame,group,value,direction in [(venue_daily,"venue","residual_bps",1),
                                        (book_daily,"strategy","alpha_error_bps",-1)]:
        frame["score"]=0.
        frame["alert"]=False
        for label,part in frame.groupby(group):
            calibration=part.loc[(part.date>train_end)&(part.date<=val_end),value]
            centre=float(calibration.median())
            scale=max(float(np.median(np.abs(calibration-centre))*1.4826),.05)
            idx=frame[group]==label
            frame.loc[idx,"score"]=direction*(frame.loc[idx,value]-centre)/scale
            frame.loc[idx,"alert"]=(frame.loc[idx,"score"]>4)&(frame.loc[idx,"date"]>val_end)
            calibrations[f"{group}:{label}"]={"median":centre,"robust_sigma":scale,"threshold_sigma":4}
    # Ground truth only joins after all scores and thresholds have been frozen.
    labels=detail[["order_id","date","venue","strategy"]].merge(truth,on="order_id",validate="one_to_one")
    router_truth=labels.groupby(["date","venue"]).router_incident.max().rename("incident")
    alpha_truth=labels.groupby(["date","strategy"]).alpha_incident.max().rename("incident")
    venue_daily=venue_daily.merge(router_truth,on=["date","venue"],validate="one_to_one")
    book_daily=book_daily.merge(alpha_truth,on=["date","strategy"],validate="one_to_one")
    evaluation={}
    for name,frame in [("execution",venue_daily),("alpha",book_daily)]:
        hold=frame.loc[frame.date>val_end]
        tp=int((hold.alert&hold.incident).sum());fp=int((hold.alert&~hold.incident).sum())
        fn=int((~hold.alert&hold.incident).sum());tn=int((~hold.alert&~hold.incident).sum())
        evaluation[name]={"tp":tp,"fp":fp,"fn":fn,"tn":tn,
            "precision":tp/(tp+fp) if tp+fp else 0.,"recall":tp/(tp+fn) if tp+fn else 0.,
            "unit":"held-out session by venue" if name=="execution" else "held-out session by book"}
    venue_summary=detail.loc[detail.date>val_end].groupby("venue").agg(
        observed_bps=("execution_bps","mean"),expected_bps=("expected_execution_bps","mean"),
        residual_bps=("residual_bps","mean"),orders=("order_id","size"))
    rng=np.random.default_rng(config.seed+1)
    intervals=[]
    for venue,part in venue_daily.loc[venue_daily.date>val_end].groupby("venue"):
        lo,hi=block_interval(part.residual_bps,rng,config.bootstrap_samples)
        intervals.append({"venue":venue,"residual_mean_bps":float(part.residual_bps.mean()),
                          "ci_low":lo,"ci_high":hi})
    tests=detail.loc[test]
    components={k:float(detail[k].sum()) for k in
                ["delay_usd","market_usd","execution_usd","opportunity_usd","fees","is_usd","ideal_pnl_usd","net_pnl_usd"]}
    metrics={"seed":config.seed,"data_type":"SYNTHETIC ORDERS, QUOTES, FILLS AND INCIDENTS",
        "orders":len(orders),"fills":len(fills),"sessions":len(dates),
        "start":dates[0],"end":dates[-1],"train_end":train_end,"validation_end":val_end,
        "test_start":dates[config.train_days+config.validation_days],
        "test_sessions":len(dates)-config.train_days-config.validation_days,
        "ridge_alpha":alpha,"validation_mae_bps":float(validation_mae),
        "test_mae_bps":float(mean_absolute_error(tests.execution_bps,tests.expected_execution_bps)),
        "fill_rate":float(detail.filled_qty.sum()/detail.qty.sum()),
        "quality":quality,"reconciliation":reconciliation,"components_usd":components,
        "alert_evaluation":evaluation,"calibration":calibrations,
        "venue_intervals":intervals,
        "decision_notional":float(detail.decision_notional.sum()),
        "test_mean_residual_bps":float(tests.residual_bps.mean())}
    # Persist only reviewable summaries and a small consistent clean ledger example.
    daily.to_csv(output/"daily.csv",index=False,float_format="%.8f")
    venue_daily.to_csv(output/"venue_monitor.csv",index=False,float_format="%.8f")
    book_daily.to_csv(output/"signal_monitor.csv",index=False,float_format="%.8f")
    venue_summary.to_csv(output/"venue_summary.csv",float_format="%.8f")
    orders.iloc[:100].to_csv(output/"sample_orders.csv",index=False,float_format="%.10f")
    fills.loc[fills.order_id<100].to_csv(output/"sample_fills.csv",index=False,float_format="%.10f")
    coef=model.named_steps["ridge"].coef_
    feature_names=model.named_steps["features"].get_feature_names_out()
    pd.DataFrame({"feature":feature_names,"coefficient":coef}).to_csv(output/"model_coefficients.csv",index=False)
    (output/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
    return metrics,daily,venue_daily,book_daily

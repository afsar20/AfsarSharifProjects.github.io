"""Predeclared sensitivity experiments; conclusions retain all configurations."""
import argparse
import json
from dataclasses import replace
from tempfile import TemporaryDirectory
from pathlib import Path

import numpy as np
import pandas as pd

from . import OUTPUT
from .data import load_data
from .execution import ExecutionConfig,run_execution
from .portfolio import RiskConfig,make_books,walk_forward


def run_robustness():
    industries,factors=load_data()
    execution=[]
    # Independent seeds; fewer orders per day deliberately reduces statistical power.
    # A zero execution-cost shift is a sham control, despite changed latency/fill rate.
    with TemporaryDirectory() as temp:
        for seed in [71,113,997]:
            for shift in [0.,.25,.5,1.,6.]:
                config=ExecutionConfig(seed=seed,orders_per_day=100,bootstrap_samples=100,
                                       router_shift_bps=shift)
                metrics,*_=run_execution(factors,config,Path(temp))
                score=metrics["alert_evaluation"]["execution"]
                execution.append({"seed":seed,"shift_bps":shift,"orders_per_day":100,
                    **{k:score[k] for k in ["tp","fp","fn","tn","precision","recall"]}})
    risk=[]
    for lookback in [126,252,504]:
        config=replace(RiskConfig(),lookback=lookback)
        books,_=make_books(industries,factors,config)
        daily,_,_=walk_forward(books,factors,config)
        for method,part in daily.groupby("method"):
            r=part["return"].to_numpy()
            risk.append({"lookback":lookback,"method":method,
                "volatility":float(np.std(r,ddof=1)*np.sqrt(252)),
                "cagr":float(np.prod(1+r)**(252/len(r))-1),
                "var99_exception_rate":float(np.mean(r < -part.var99.to_numpy()))})
    base=pd.read_csv(OUTPUT/"portfolio/walk_forward.csv")
    paired=base.pivot(index="date",columns="method",values="return")
    values=paired[["minimum_variance","equal"]].to_numpy()
    rng=np.random.default_rng(8901);block=20;samples=1500;n=len(values)
    starts=rng.integers(0,n-block+1,(samples,int(np.ceil(n/block))))
    indices=(starts[...,None]+np.arange(block)).reshape(samples,-1)[:,:n]
    boot=values[indices]
    ratios=boot[:,:,0].std(axis=1,ddof=1)/boot[:,:,1].std(axis=1,ddof=1)
    confidence={"quantity":"realised volatility ratio: minimum variance / equal allocation",
        "point":float(values[:,0].std(ddof=1)/values[:,1].std(ddof=1)),
        "ci95":np.quantile(ratios,[.025,.975]).tolist(),"block_sessions":block,
        "replicates":samples,"seed":8901,
        "limitation":"Conditional sampling uncertainty; does not cover design choices, source revisions or future regimes."}
    pd.DataFrame(execution).to_csv(OUTPUT/"execution/sensitivity.csv",index=False)
    pd.DataFrame(risk).to_csv(OUTPUT/"portfolio/lookback_sensitivity.csv",index=False)
    (OUTPUT/"portfolio/volatility_ratio_interval.json").write_text(json.dumps(confidence,indent=2)+"\n")
    print(json.dumps({"execution_experiments":len(execution),"risk_configurations":len(risk),
                      "volatility_ratio_interval":confidence},indent=2))


if __name__=="__main__":run_robustness()

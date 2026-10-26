"""Real daily industry returns; illustrative books and causal capital allocation.

The books are fixed, disclosed industry tilts, not hedge-fund returns. Backtests
use only rows strictly before each forecast/rebalance. Historical public files
are revised, so this is a walk-forward research exercise, not point-in-time proof.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize,LinearConstraint
from scipy.special import xlogy
from scipy.stats import chi2, norm
from sklearn.covariance import LedoitWolf

from . import OUTPUT
from .data import FACTORS, INDUSTRIES

BOOK_NAMES=["Technology tilt","Digital consumer","Defensive spread", "Cyclical spread","Consumer relative","Diversified equity"]
BOOK_WEIGHTS=np.array([
    [0,0,-.20,-.20,.50,.10,0,0,0,0],
    [-.15,.10,0,0,.30,0,.30,0,-.15,0],
    [.20,-.20,-.20,0,0,0,0,.20,.20,0],
    [-.15,0,.25,.25,0,0,0,0,-.20,.15],
    [0,.25,0,0,0,-.25,.25,0,0,-.25],
    [.10,.10,.10,.10,.10,.10,.10,.10,.10,.10],
])

@dataclass(frozen=True)
class RiskConfig:
    lookback: int = 252
    evaluation_start: str = "2020-01-01"
    cap: float = .35
    floor: float = .03
    one_way_turnover_limit: float = .15
    trading_cost_bps: float = 2.
    borrow_bps_annual: float = 50.
    nav_usd: float = 10_000_000.


def make_books(industries, factors, config=RiskConfig()):
    """Excess P&L per unit allocated capital, net of stylised costs.

    A sleeve has 100% gross initial industry exposure. Uninvested capital and
    short proceeds earn RF. The short borrow fee is constant and disclosed.
    Constant industry weights rebalance daily, with turnover from prior drift.
    """
    excess=industries.subtract(factors.RF,axis=0)
    gross=excess.to_numpy()@BOOK_WEIGHTS.T
    short_gross=np.maximum(-BOOK_WEIGHTS,0).sum(axis=1)
    borrow=short_gross*config.borrow_bps_annual/10000/252
    # Prior session's price drift determines today's internal rebalance trades.
    costs=np.zeros_like(gross);net=np.zeros_like(gross)
    rates=factors.RF.to_numpy();industry_values=industries.to_numpy()
    for i in range(len(industries)):
        if i==0:
            turnover=np.abs(BOOK_WEIGHTS).sum(axis=1) # initial gross deployment
        else:
            previous_total=rates[i-1]+net[i-1]
            drift=BOOK_WEIGHTS*(1+industry_values[i-1])/(1+previous_total[:,None])
            turnover=np.abs(BOOK_WEIGHTS-drift).sum(axis=1)
        costs[i]=turnover*config.trading_cost_bps/10000
        net[i]=gross[i]-borrow-costs[i]
    return pd.DataFrame(net,index=industries.index,columns=BOOK_NAMES),pd.DataFrame(
        costs,index=industries.index,columns=BOOK_NAMES)


def covariance(returns):
    fitted=LedoitWolf().fit(np.ascontiguousarray(returns,dtype=float))
    return fitted.covariance_,float(fitted.shrinkage_)


def risk_contributions(weights,cov):
    w=np.asarray(weights);sigma=float(np.sqrt(max(w@cov@w,0)))
    if sigma<=0:
        raise ValueError("Portfolio volatility is zero")
    contributions=w*(cov@w)/sigma
    return sigma,contributions


def allocate(cov,previous,method,config=RiskConfig()):
    """Minimise annual variance or distance to a capped baseline.

    All methods use the same position bounds and 15% one-way monthly turnover
    budget. No expected return estimate or future information enters this step.
    """
    previous=np.asarray(previous,dtype=float);n=len(previous)
    if method=="equal":
        target=np.full(n,1/n)
    elif method=="inverse_vol":
        target=1/np.sqrt(np.diag(cov));target/=target.sum()
    elif method!="minimum_variance":
        raise ValueError("Unknown allocation method")
    # Epigraph variables z_i >= |w_i-previous_i| turn the L1 budget into
    # linear inequalities. Analytic gradients avoid unstable finite differences
    # at the turnover kink and keep identical histories numerically reproducible.
    objective=(lambda x:float(252*x[:n]@cov@x[:n])) if method=="minimum_variance" else (
        lambda x:float(np.sum((x[:n]-target)**2)))
    jac=(lambda x:np.r_[504*cov@x[:n],np.zeros(n)]) if method=="minimum_variance" else (
        lambda x:np.r_[2*(x[:n]-target),np.zeros(n)])
    rows=np.vstack([np.r_[np.ones(n),np.zeros(n)],np.r_[np.zeros(n),np.ones(n)],
                    np.hstack([np.eye(n),-np.eye(n)]),np.hstack([-np.eye(n),-np.eye(n)])])
    lo=np.r_[1.,-np.inf,np.full(2*n,-np.inf)]
    hi=np.r_[1.,2*config.one_way_turnover_limit,previous,-previous]
    # Split equalities and inequalities for the SLSQP interface.
    constraints=[LinearConstraint(rows[:1],lo[:1],hi[:1]),
                 LinearConstraint(rows[1:],lo[1:],hi[1:])]
    initial_w=np.clip(previous,config.floor,config.cap)
    initial=np.r_[initial_w,np.abs(initial_w-previous)+1e-8]
    result=minimize(objective,initial,jac=jac,method="SLSQP",
                    bounds=[(config.floor,config.cap)]*n+[(0,None)]*n,
                    constraints=constraints,options={"ftol":1e-12,"maxiter":500})
    if not result.success:
        raise RuntimeError(f"Allocation failed: {result.message}")
    w=result.x[:n]
    if (abs(w.sum()-1)>1e-7 or w.min()<config.floor-1e-7 or w.max()>config.cap+1e-7
        or np.abs(w-previous).sum()/2>config.one_way_turnover_limit+1e-7):
        raise ArithmeticError("Optimiser returned infeasible allocation")
    return w


def bernoulli_log_likelihood(successes,total,probability):
    return float(xlogy(successes,probability)+xlogy(total-successes,1-probability))


def coverage_tests(exceptions,alpha=.01):
    """Kupiec unconditional coverage and Christoffersen independence LR tests."""
    hit=np.asarray(exceptions,dtype=int);n=len(hit);k=int(hit.sum())
    if n<2:
        raise ValueError("Need at least two risk forecasts")
    uc=max(0.,2*(bernoulli_log_likelihood(k,n,k/n)-bernoulli_log_likelihood(k,n,alpha)))
    transition=np.zeros((2,2),dtype=int)
    for a,b in zip(hit[:-1],hit[1:]):transition[a,b]+=1
    n0=transition[0].sum();n1=transition[1].sum()
    p01=transition[0,1]/n0 if n0 else 0.
    p11=transition[1,1]/n1 if n1 else 0.
    p=(transition[0,1]+transition[1,1])/(n-1)
    alternative=bernoulli_log_likelihood(transition[0,1],n0,p01)+bernoulli_log_likelihood(transition[1,1],n1,p11)
    independent=bernoulli_log_likelihood(transition[:,1].sum(),n-1,p)
    lr_ind=max(0.,2*(alternative-independent))
    return {"observations":n,"exceptions":k,"expected_exceptions":n*alpha,
        "exception_rate":k/n,"uc_lr":uc,"uc_p":float(chi2.sf(uc,1)),
        "independence_lr":lr_ind,"independence_p":float(chi2.sf(lr_ind,1)),
        "conditional_coverage_p":float(chi2.sf(uc+lr_ind,2)),"transitions":transition.tolist()}


def walk_forward(books,factors,config=RiskConfig()):
    rows=[];allocations=[]
    first=int(books.index.searchsorted(pd.Timestamp(config.evaluation_start)))
    if first<config.lookback:raise ValueError("Insufficient training history")
    weights={key:np.full(len(BOOK_NAMES),1/len(BOOK_NAMES)) for key in ["equal","inverse_vol","minimum_variance"]}
    previous_month=None
    for i in range(first,len(books)):
        date=books.index[i]
        history=books.iloc[i-config.lookback:i] # strict exclusion of current return
        cov,shrinkage=covariance(history)
        month=(date.year,date.month)
        rebalance=month!=previous_month
        for method,drift in weights.items():
            old=drift.copy()
            if rebalance:
                # Existing drift can marginally escape the bounds. Constraints are
                # enforced on the new target, not on the pre-trade market drift.
                w=allocate(cov,old,method,config)
            else:w=old
            traded_gross=float(np.abs(w-old).sum())
            if i==first:traded_gross=1. # initial deployment of the allocated capital
            cost=traded_gross*config.trading_cost_bps/10000
            rf=float(factors.RF.iloc[i])
            actual=float(rf+w@books.iloc[i].to_numpy()-cost)
            # Today's realised RF is used only in the realised return. The
            # forecast uses the latest published prior-session cash return.
            forecast_rf=float(factors.RF.iloc[i-1])
            scenarios=forecast_rf+history.to_numpy()@w-cost
            hist95=max(0.,float(-np.quantile(scenarios,.05)))
            hist99=max(0.,float(-np.quantile(scenarios,.01)))
            threshold=np.quantile(scenarios,.01)
            es99=max(0.,float(-scenarios[scenarios<=threshold].mean()))
            sigma=float(np.sqrt(w@cov@w))
            normal99=max(0.,float(norm.ppf(.99)*sigma-forecast_rf+cost))
            rows.append({"date":date,"method":method,"return":actual,"excess_return":actual-rf,
                "var95":hist95,"var99":hist99,"es99":es99,"normal_var99":normal99,
                "vol_forecast":sigma*np.sqrt(252),"rebalance":rebalance,
                "traded_gross":traded_gross,"allocation_cost":cost,"shrinkage":shrinkage,
                "forecast_max_date":history.index[-1],
                **{f"weight_{j}":float(v) for j,v in enumerate(w)}})
            if rebalance:
                allocations.append({"date":date,"method":method,"one_way_turnover":traded_gross/2,
                    "is_initial_deployment":i==first,**dict(zip(BOOK_NAMES,w))})
            # Self-financing sleeve weights drift between monthly reallocations.
            # Costs reduce cash rather than silently changing risky notionals.
            weights[method]=w*(1+rf+books.iloc[i].to_numpy())/(1+actual)
        previous_month=month
    return pd.DataFrame(rows),pd.DataFrame(allocations),weights


def factor_decomposition(books,factors,weights):
    """OLS sensitivities, intercept and residual covariance; no alpha claims."""
    x=factors[FACTORS].to_numpy();design=np.column_stack([np.ones(len(x)),x])
    coef=np.linalg.lstsq(design,books.to_numpy(),rcond=None)[0]
    residual=books.to_numpy()-design@coef
    betas=coef[1:].T
    fcov=np.cov(x,rowvar=False,ddof=1)
    rcov=np.cov(residual,rowvar=False,ddof=1)
    port_beta=np.asarray(weights)@betas
    common=float(port_beta@fcov@port_beta)
    specific=float(np.asarray(weights)@rcov@np.asarray(weights))
    # Equalities use sample covariance with an intercept, not a shrunken matrix.
    sample_var=float(np.asarray(weights)@np.cov(books.to_numpy(),rowvar=False)@np.asarray(weights))
    error=abs(sample_var-common-specific)
    if error>1e-10:raise ArithmeticError("Factor covariance decomposition failed")
    return {"book_betas":betas.tolist(),"portfolio_beta":port_beta.tolist(),
        "daily_intercepts":coef[0].tolist(),"common_variance":common,
        "specific_variance":specific,"common_share":common/(common+specific),
        "reconciliation_error":error,"r_squared":[float(1-np.var(residual[:,j])/np.var(books.iloc[:,j])) for j in range(books.shape[1])]}


def scenario_risk(cov,weights,vol_multiplier=1.,correlation_blend=0.,leverage=1.):
    """PSD-preserving blend towards +1 correlation, holding marginal vols fixed."""
    if not (0<=correlation_blend<=1) or vol_multiplier<0 or leverage<0:
        raise ValueError("Invalid scenario parameters")
    d=np.sqrt(np.diag(cov));corr=cov/np.outer(d,d)
    stressed=(1-correlation_blend)*corr+correlation_blend*np.ones_like(corr)
    matrix=stressed*np.outer(d,d)*vol_multiplier**2
    vol=float(np.sqrt(np.asarray(weights)@matrix@np.asarray(weights))*np.sqrt(252)*leverage)
    var=float(norm.ppf(.99)*vol/np.sqrt(252))
    return vol,var,matrix


def run_portfolio(industries,factors,config=RiskConfig(),output=OUTPUT/"portfolio"):
    output.mkdir(parents=True,exist_ok=True)
    books,internal_costs=make_books(industries,factors,config)
    daily,allocations,last_weights=walk_forward(books,factors,config)
    performance=[];coverage={}
    for method,part in daily.groupby("method",sort=False):
        part=part.sort_values("date");r=part["return"].to_numpy()
        wealth=np.cumprod(1+r);peak=np.maximum.accumulate(np.r_[1,wealth])[1:]
        performance.append({"method":method,"cagr":float(wealth[-1]**(252/len(r))-1),
            "annual_vol":float(np.std(r,ddof=1)*np.sqrt(252)),
            "excess_sharpe":float(part.excess_return.mean()/part.excess_return.std()*np.sqrt(252)),
            "max_drawdown":float(np.min(wealth/peak-1)),"total_return":float(wealth[-1]-1),
            "allocation_cost_bps":float(part.allocation_cost.sum()*10000),
            "mean_one_way_turnover":float(allocations.loc[(allocations.method==method)&~allocations.is_initial_deployment,"one_way_turnover"].mean())})
        coverage[method]={}
        for key,a in [("var95",.05),("var99",.01),("normal_var99",.01)]:
            coverage[method][key]=coverage_tests(part["return"].to_numpy() < -part[key].to_numpy(),a)
    # Snapshot is at the final close, forecasting the next session.
    window=books.iloc[-config.lookback:];cov,shrinkage=covariance(window)
    w=last_weights["minimum_variance"];w=w/w.sum() # capital allocation shares at close
    sigma,rc=risk_contributions(w,cov)
    factor=factor_decomposition(window,factors.loc[window.index],w)
    corr=window.corr().to_numpy()
    eig=np.linalg.eigvalsh(corr)
    abs_rc=np.abs(rc);risk_shares=abs_rc/abs_rc.sum()
    positions=w@BOOK_WEIGHTS
    gross_before_netting=float(w@np.abs(BOOK_WEIGHTS).sum(axis=1))
    scenarios=[]
    for name,start,end in [("COVID sell-off","2020-02-19","2020-03-23"),
                            ("2022 rates repricing","2022-01-03","2022-12-30"),
                            ("April 2025 sell-off","2025-04-02","2025-04-08")]:
        period=books.loc[start:end]
        # Frozen starting capital weights, compounded sleeves without rebalancing.
        sleeve_total=period.add(factors.loc[period.index,"RF"],axis=0)
        sleeve_wealth=(1+sleeve_total).prod(axis=0).to_numpy()
        pnl=float(w@(sleeve_wealth-1))
        scenarios.append({"name":name,"start":start,"end":end,"sessions":len(period),
            "return":pnl,"pnl_usd":pnl*config.nav_usd})
    severity=[]
    for blend in [0,.25,.5,.75,1.]:
        vol,var,_=scenario_risk(cov,w,1.,blend,1.)
        severity.append({"correlation_blend":blend,"annual_vol":vol,"normal_var99":var})
    # Risk-size capacity proxy: no volume data means no market-impact claim.
    cost_sensitivity=[]
    base=daily.loc[daily.method=="minimum_variance"]
    for extra_bps in [0,2,5,10]:
        adjusted=base["return"]-base.traded_gross*extra_bps/10000
        cost_sensitivity.append({"extra_allocation_cost_bps":extra_bps,
            "cagr":float(np.prod(1+adjusted)**(252/len(adjusted))-1)})
    metrics={"data_type":"REAL INDUSTRY/FACTOR RETURNS; ILLUSTRATIVE FIXED BOOKS",
        "as_of":str(books.index[-1].date()),"data_start":str(books.index[0].date()),
        "evaluation_start":str(daily.date.min().date()),"evaluation_end":str(daily.date.max().date()),
        "lookback":config.lookback,"sessions":int(daily.groupby("method").size().iloc[0]),
        "nav_usd":config.nav_usd,"book_names":BOOK_NAMES,"factor_names":FACTORS,
        "industries":INDUSTRIES,"book_weights":BOOK_WEIGHTS.tolist(),"weights":w.tolist(),
        "snapshot_weights":{key:(value/value.sum()).tolist() for key,value in last_weights.items()},
        "covariance_daily":cov.tolist(),"correlation":corr.tolist(),"shrinkage":shrinkage,
        "annual_vol":sigma*np.sqrt(252),"risk_contributions_annual":(rc*np.sqrt(252)).tolist(),
        "risk_shares_absolute":risk_shares.tolist(),"effective_risk_books":float(1/np.sum(risk_shares**2)),
        "largest_pc_share":float(eig[-1]/eig.sum()),"net_industry_weights":positions.tolist(),
        "gross_before_netting":gross_before_netting,"gross_after_netting":float(np.abs(positions).sum()),
        "net_exposure":float(positions.sum()),"factor_model":factor,
        "performance":performance,"coverage":coverage,"historical_stress":scenarios,
        "correlation_sensitivity":severity,"cost_sensitivity":cost_sensitivity,
        "assumptions":{"one_way_allocation_cost_bps":config.trading_cost_bps,
            "borrow_cost_bps_annual":config.borrow_bps_annual,"allocation_cap":config.cap,
            "allocation_floor":config.floor,"monthly_one_way_turnover_cap":config.one_way_turnover_limit},
        "risk_reconciliation_error":float(abs(rc.sum()-sigma)),
        "data_caveat":"Revised research indices, not directly tradable assets or real hedge fund books."}
    daily.to_csv(output/"walk_forward.csv",index=False,float_format="%.10f",date_format="%Y-%m-%d")
    allocations.to_csv(output/"allocations.csv",index=False,float_format="%.10f",date_format="%Y-%m-%d")
    books.to_csv(output/"book_returns.csv",float_format="%.10f")
    pd.DataFrame(performance).to_csv(output/"performance.csv",index=False,float_format="%.8f")
    (output/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
    return metrics,daily,books

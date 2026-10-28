"""Build publication figures and standalone static research pages from results."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from . import ROOT,OUTPUT

IMAGE=ROOT/"assets/images/strategist"
LABELS={"equal":"Equal amounts","inverse_vol":"More to lower-risk portfolios","minimum_variance":"Lowest combined risk"}
COLORS=["#19232d","#985141","#234d70"]


def style():
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.titlesize":12,
        "axes.titleweight":"normal","axes.labelcolor":"#59636d","text.color":"#19232d",
        "xtick.color":"#59636d","ytick.color":"#59636d","axes.edgecolor":"#dce0e4",
        "axes.spines.top":False,"axes.spines.right":False,"figure.facecolor":"#ffffff",
        "axes.facecolor":"#ffffff","grid.alpha":.17,"grid.color":"#59636d",
        "svg.fonttype":"none","svg.hashsalt":"afsar-strategist-v1","savefig.bbox":"tight"})


def save(fig,name):
    IMAGE.mkdir(parents=True,exist_ok=True)
    path=IMAGE/f"{name}.svg"
    fig.savefig(path,metadata={"Date":None,"Creator":"Afsar Sharif | Strategist Lab"})
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines())+"\n")
    plt.close(fig)


def dates(ax):
    locator=mdates.AutoDateLocator(minticks=4,maxticks=7)
    ax.xaxis.set_major_locator(locator);ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.grid(axis="y");ax.tick_params(axis="both",labelsize=10)


def figures(e,p):
    style()
    daily=pd.read_csv(OUTPUT/"execution/daily.csv",parse_dates=["date"])
    monitor=pd.read_csv(OUTPUT/"execution/venue_monitor.csv",parse_dates=["date"])
    signal=pd.read_csv(OUTPUT/"execution/signal_monitor.csv",parse_dates=["date"])
    walk=pd.read_csv(OUTPUT/"portfolio/walk_forward.csv",parse_dates=["date"])
    fig,axes=plt.subplots(2,1,figsize=(12,6.5),sharex=True,layout="constrained")
    for (venue,part),color in zip(monitor.groupby("venue"),COLORS):
        axes[0].plot(part.date,part.residual_bps,label=venue,color=color,lw=1.5)
        axes[1].plot(part.date,part.latency_ms,label=venue,color=color,lw=1.5)
    axes[0].set_title("Execution cost and processing delay",loc="left",pad=18)
    axes[0].set_ylabel("Extra execution cost (bps)");axes[1].set_ylabel("Typical delay (milliseconds)")
    axes[0].legend(ncol=3,frameon=False,loc="upper left")
    for ax in axes:
        ax.axvline(pd.Timestamp(e["test_start"]),color="#7a858a",ls="--",lw=1)
        dates(ax)
    axes[1].set_xlabel("2025 simulated trading days · dashed line starts the final test")
    save(fig,"execution-monitor")
    fig,ax=plt.subplots(figsize=(12,4.1),layout="constrained")
    for (book,part),color in zip(signal.groupby("strategy"),COLORS):
        ax.plot(part.date,part.alpha_error_bps,label={"Momentum":"Group A (affected)","Rebalance":"Group B","StatArb":"Group C"}[book],color=color,lw=1.4)
    ax.set_title("Price moves compared with the trading forecast",loc="left",pad=18)
    ax.set_ylabel("Price move minus forecast (bps)");ax.legend(ncol=3,frameon=False)
    dates(ax);save(fig,"signal-decay")
    parts=["delay_usd","market_usd","execution_usd","opportunity_usd","fees"]
    costs=[e["components_usd"][k]/e["decision_notional"]*10000 for k in parts]
    fig,ax=plt.subplots(figsize=(12,4),layout="constrained")
    ax.bar(["Decision delay","Market move","Execution","Missed opportunity","Fees"],costs,
           color=["#8aa0aa","#b1bfbd","#234d70","#985141","#19232d"],width=.58)
    ax.set_title("Where the total trading shortfall comes from",loc="left",pad=18)
    ax.set_ylabel("Cost / intended trading value (bps)");ax.grid(axis="y")
    save(fig,"cost-bridge")
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,layout="constrained")
    for (method,part),color in zip(walk.groupby("method",sort=False),COLORS):
        wealth=(1+part["return"]).cumprod().to_numpy()
        peak=np.maximum.accumulate(np.r_[1,wealth])[1:]
        axes[0].plot(part.date,wealth,label=LABELS[method],color=color,lw=1.5)
        axes[1].plot(part.date,wealth/peak-1,color=color,lw=1.3)
    axes[0].set_title("Allocation changes both risk and return",loc="left",pad=18)
    axes[0].set_ylabel("Growth of $1, after assumed costs");axes[1].set_ylabel("Fall from earlier high")
    axes[1].yaxis.set_major_formatter(PercentFormatter(1));axes[0].legend(frameon=False,ncol=1,fontsize=9)
    for ax in axes:dates(ax)
    save(fig,"portfolio-performance")
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout="constrained")
    short=["Technology","Technology + retail","Defensive industries","Cyclical industries","Consumer industries","Broad equities"]
    axes[0].barh(short,p["weights"],color="#19232d",height=.6)
    axes[0].set_title("Money allocated",loc="left");axes[0].xaxis.set_major_formatter(PercentFormatter(1))
    axes[1].barh(short,np.array(p["risk_contributions_annual"])*100,color="#234d70",height=.6)
    axes[1].set_title("Contribution to total volatility",loc="left")
    axes[1].set_xlabel("Percentage points; negative values reduce risk")
    for ax in axes:ax.invert_yaxis();ax.grid(axis="x")
    save(fig,"risk-contributions")
    fig,ax=plt.subplots(figsize=(9,6.7),layout="constrained")
    matrix=np.array(p["correlation"])
    from matplotlib.colors import LinearSegmentedColormap
    palette=LinearSegmentedColormap.from_list("risk_relationships",["#985141","#ffffff","#234d70"])
    im=ax.imshow(matrix,cmap=palette,vmin=-1,vmax=1)
    ax.set_xticks(range(6),short,rotation=35,ha="right");ax.set_yticks(range(6),short)
    for i in range(6):
        for j in range(6):ax.text(j,i,f"{matrix[i,j]:.2f}",ha="center",va="center",fontsize=10,
                                  color="white" if abs(matrix[i,j])>.6 else "#19232d")
    ax.set_title("How the six portfolios move together",loc="left",pad=18)
    fig.colorbar(im,ax=ax,shrink=.8,label="Correlation · last 252 trading days")
    save(fig,"correlation")
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout="constrained")
    beta=p["factor_model"]["portfolio_beta"]
    axes[0].bar(p["factor_names"],beta,color=["#234d70" if x>=0 else "#985141" for x in beta])
    axes[0].set_title("Sensitivity to common market influences",loc="left");axes[0].set_ylabel("Estimated sensitivity")
    severity=pd.DataFrame(p["correlation_sensitivity"])
    axes[1].plot(severity.correlation_blend,severity.annual_vol,color="#234d70",marker="o",lw=2)
    axes[1].set_title("Portfolios moving more closely together",loc="left")
    axes[1].xaxis.set_major_formatter(PercentFormatter(1));axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].set_xlabel("Move towards perfectly shared movements");axes[1].set_ylabel("Annual volatility")
    for ax in axes:ax.grid(axis="y")
    save(fig,"factor-stress")
    part=walk.loc[walk.method=="minimum_variance"]
    fig,ax=plt.subplots(figsize=(12,4.5),layout="constrained")
    ax.plot(part.date,-part["return"],color="#8aa0aa",alpha=.7,lw=.7,label="Actual daily loss")
    ax.plot(part.date,part.var99,color="#234d70",lw=1.4,label="99% threshold from earlier returns")
    breach=part["return"] < -part.var99
    ax.scatter(part.loc[breach,"date"],-part.loc[breach,"return"],color="#985141",s=24,label="Loss above the threshold",zorder=3)
    ax.yaxis.set_major_formatter(PercentFormatter(1));ax.legend(frameon=False,ncol=1,loc="upper right",fontsize=9)
    ax.set_title("Forecast loss thresholds and actual daily losses",loc="left",pad=18)
    dates(ax);save(fig,"var-backtest")


def build_reports():
    ep=OUTPUT/"execution/metrics.json";pp=OUTPUT/"portfolio/metrics.json"
    if not ep.exists() or not pp.exists():return
    e=json.loads(ep.read_text());p=json.loads(pp.read_text())
    figures(e,p)
    from research.portfolio_site import build_site
    from research.site_figures import build_figures
    build_figures()
    build_site(render_figures=False)
    perf={row["method"]:row for row in p["performance"]}
    tail=p["coverage"]["minimum_variance"]["var99"]
    brief=f'''# Research findings

## Execution costs and trading results

The study separates trading costs from the quality of the original price forecast. It uses {e['orders']:,} simulated orders, including partial fills, unfilled orders and deliberately invalid records.

Two different problems were introduced: a temporary increase in one venue's execution costs and a later deterioration in one strategy group's forecasts. Separate checks identified them. The main incidents were deliberately large; smaller changes were harder to detect in the follow-up experiments.

The practical lesson is to investigate the execution process and the trading forecast separately. A decline in final profit alone cannot explain which has changed. These results validate the designed example, rather than accuracy on real trades.

## Portfolio risk and allocation

The study compares three ways of dividing money between six example industry portfolios. The underlying industry returns are real public data; the portfolios and costs are illustrative.

Equal amounts produced {perf['equal']['cagr']:.2%} annualised return and {perf['equal']['annual_vol']:.2%} annual volatility over 2020–2025. The lowest-risk allocation produced {perf['minimum_variance']['cagr']:.2%} return and {perf['minimum_variance']['annual_vol']:.2%} volatility. Volatility measures how widely returns vary. The largest falls from earlier highs were {abs(perf['equal']['max_drawdown']):.2%} and {abs(perf['minimum_variance']['max_drawdown']):.2%}, respectively.

The lower risk came with a lower return. The loss forecast also needs improvement: the 99% historical threshold was exceeded on {tail['exceptions']} days, versus {tail['expected_exceptions']:.1f} expected. Large losses occurred too often and clustered in time.

The practical lesson is to compare money weights with actual risk contributions, retain useful offsets, and test the loss model against subsequent outcomes. The study is a historical illustration, not a directly tradable strategy.
'''
    (ROOT/"research/strategist_lab/DECISION_BRIEF.md").write_text(brief)


if __name__=="__main__":build_reports()

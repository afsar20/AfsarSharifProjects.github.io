"""Build publication figures and standalone static research pages from results."""
from __future__ import annotations

import html
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from . import ROOT,OUTPUT,DATA

IMAGE=ROOT/"assets/images/strategist"
REPO="https://github.com/afsar20/AfsarSharifProjects.github.io/tree/main/research/strategist_lab"
LABELS={"equal":"Equal allocation","inverse_vol":"Inverse volatility","minimum_variance":"Minimum variance"}
COLORS=["#10253a","#ef8553","#087f78"]


def style():
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":11,"axes.titlesize":14,
        "axes.titleweight":"bold","axes.labelcolor":"#42566a","text.color":"#10253a",
        "xtick.color":"#42566a","ytick.color":"#42566a","axes.edgecolor":"#c9d2d3",
        "axes.spines.top":False,"axes.spines.right":False,"figure.facecolor":"#fffdf8",
        "axes.facecolor":"#fffdf8","grid.alpha":.17,"grid.color":"#42566a",
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
    axes[0].set_title("An execution incident changes cost and latency together",loc="left",pad=18)
    axes[0].set_ylabel("Mean cost residual (bps)");axes[1].set_ylabel("Median latency (ms)")
    axes[0].legend(ncol=3,frameon=False,loc="upper left")
    for ax in axes:
        ax.axvline(pd.Timestamp(e["test_start"]),color="#7a858a",ls="--",lw=1)
        dates(ax)
    axes[1].set_xlabel("2025 synthetic sessions · dashed line starts held-out monitoring")
    save(fig,"execution-monitor")
    fig,ax=plt.subplots(figsize=(12,4.1),layout="constrained")
    for (book,part),color in zip(signal.groupby("strategy"),COLORS):
        ax.plot(part.date,part.alpha_error_bps,label=book,color=color,lw=1.4)
    ax.set_title("A separate signal-decay episode appears in the opportunity P&L",loc="left",pad=18)
    ax.set_ylabel("Signed end move − forecast (bps)");ax.legend(ncol=3,frameon=False)
    dates(ax);save(fig,"signal-decay")
    parts=["delay_usd","market_usd","execution_usd","opportunity_usd","fees"]
    costs=[e["components_usd"][k]/e["decision_notional"]*10000 for k in parts]
    fig,ax=plt.subplots(figsize=(12,4),layout="constrained")
    ax.bar(["Decision delay","Market move","Execution","Unfilled opportunity","Fees"],costs,
           color=["#8aa0aa","#b1bfbd","#087f78","#ef8553","#10253a"],width=.58)
    ax.set_title("The full shortfall includes the cost of unfilled orders",loc="left",pad=18)
    ax.set_ylabel("Contribution / decision notional (bps)");ax.grid(axis="y")
    save(fig,"cost-bridge")
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,layout="constrained")
    for (method,part),color in zip(walk.groupby("method",sort=False),COLORS):
        wealth=(1+part["return"]).cumprod().to_numpy()
        peak=np.maximum.accumulate(np.r_[1,wealth])[1:]
        axes[0].plot(part.date,wealth,label=LABELS[method],color=color,lw=1.5)
        axes[1].plot(part.date,wealth/peak-1,color=color,lw=1.3)
    axes[0].set_title("Less risk also means less return in this sample",loc="left",pad=18)
    axes[0].set_ylabel("Growth of $1, costs included");axes[1].set_ylabel("Drawdown")
    axes[1].yaxis.set_major_formatter(PercentFormatter(1));axes[0].legend(frameon=False,ncol=3)
    for ax in axes:dates(ax)
    save(fig,"portfolio-performance")
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout="constrained")
    short=["Technology","Digital consumer","Defensive","Cyclical","Consumer relative","Diversified"]
    axes[0].barh(short,p["weights"],color="#10253a",height=.6)
    axes[0].set_title("Capital allocation",loc="left");axes[0].xaxis.set_major_formatter(PercentFormatter(1))
    axes[1].barh(short,np.array(p["risk_contributions_annual"])*100,color="#087f78",height=.6)
    axes[1].set_title("Contribution to annual volatility",loc="left")
    axes[1].set_xlabel("Percentage points (signed Euler contribution)")
    for ax in axes:ax.invert_yaxis();ax.grid(axis="x")
    save(fig,"risk-contributions")
    fig,ax=plt.subplots(figsize=(9,6.7),layout="constrained")
    matrix=np.array(p["correlation"])
    im=ax.imshow(matrix,cmap="BrBG",vmin=-1,vmax=1)
    ax.set_xticks(range(6),short,rotation=35,ha="right");ax.set_yticks(range(6),short)
    for i in range(6):
        for j in range(6):ax.text(j,i,f"{matrix[i,j]:.2f}",ha="center",va="center",fontsize=10,
                                  color="white" if abs(matrix[i,j])>.6 else "#10253a")
    ax.set_title("Book labels conceal shared and offsetting industry risks",loc="left",pad=18)
    fig.colorbar(im,ax=ax,shrink=.8,label="Daily return correlation · last 252 sessions")
    save(fig,"correlation")
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout="constrained")
    beta=p["factor_model"]["portfolio_beta"]
    axes[0].bar(p["factor_names"],beta,color=["#087f78" if x>=0 else "#ef8553" for x in beta])
    axes[0].set_title("Portfolio factor sensitivities",loc="left");axes[0].set_ylabel("OLS beta")
    severity=pd.DataFrame(p["correlation_sensitivity"])
    axes[1].plot(severity.correlation_blend,severity.annual_vol,color="#087f78",marker="o",lw=2)
    axes[1].set_title("Correlations moving towards +1",loc="left")
    axes[1].xaxis.set_major_formatter(PercentFormatter(1));axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].set_xlabel("Blend towards perfect positive correlation");axes[1].set_ylabel("Annual volatility")
    for ax in axes:ax.grid(axis="y")
    save(fig,"factor-stress")
    part=walk.loc[walk.method=="minimum_variance"]
    fig,ax=plt.subplots(figsize=(12,4.5),layout="constrained")
    ax.plot(part.date,-part["return"],color="#8aa0aa",alpha=.7,lw=.7,label="Realised daily loss")
    ax.plot(part.date,part.var99,color="#087f78",lw=1.4,label="Prior-history 99% historical VaR")
    breach=part["return"] < -part.var99
    ax.scatter(part.loc[breach,"date"],-part.loc[breach,"return"],color="#ef8553",s=24,label="Exception",zorder=3)
    ax.yaxis.set_major_formatter(PercentFormatter(1));ax.legend(frameon=False,ncol=3,loc="upper right")
    ax.set_title("A risk forecast must be checked against realised losses",loc="left",pad=18)
    dates(ax);save(fig,"var-backtest")


def table(headers,rows):
    return '<div class="lab-table-wrap"><table class="lab-table"><thead><tr>'+''.join(
        f'<th scope="col">{html.escape(str(h))}</th>' for h in headers)+'</tr></thead><tbody>'+''.join(
        '<tr>'+''.join(f'<td>{html.escape(str(c))}</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def figure(name,caption):
    return f'<figure class="lab-figure"><img loading="lazy" src="../assets/images/strategist/{name}.svg" alt="{html.escape(caption)}"><figcaption>{caption}</figcaption></figure>'


def stats(items):
    return '<div class="lab-summary">'+''.join(f'<div class="lab-stat"><strong>{a}</strong><span>{b}</span></div>' for a,b in items)+'</div>'


def section(id,title,body,eyebrow=""):
    return f'<section class="lab-section" id="{id}"><div class="shell">'+(f'<p class="eyebrow">{eyebrow}</p>' if eyebrow else '')+f'<h2>{title}</h2>{body}</div></section>'


def page(title,eyebrow,lede,status,body,links,data,public=False):
    anchors=''.join(f'<a href="#{key}">{label}</a>' for key,label in links)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{html.escape(lede)}"><title>{title} | Afsar Sharif</title>
<link rel="stylesheet" href="../assets/css/portfolio.css?v=4"><link rel="stylesheet" href="../assets/css/strategist-lab.css?v=1"></head>
<body><header class="site-header"><nav class="nav shell" aria-label="Primary navigation"><a class="brand" href="../index.html"><span class="brand-mark">AS</span><span>Afsar Sharif</span></a><ul class="nav-links"><li><a href="../index.html#work">Selected work</a></li><li><a href="{REPO}">Research code</a></li></ul></nav></header>
<main><section class="project-hero"><div class="shell"><div class="breadcrumbs"><a href="../index.html">Portfolio</a> / Quantitative research</div><span class="lab-status {'public' if public else ''}">{status}</span><p class="eyebrow">{eyebrow}</p><h1>{title}</h1><p class="lede">{lede}</p><div class="lab-anchor-nav">{anchors}</div></div></section>{body}</main>
<footer class="site-footer"><div class="shell footer-grid"><p>Reproducible research · assumptions and source data disclosed</p><div class="footer-links"><a href="../index.html">Portfolio</a><a href="{REPO}">GitHub source</a></div></div></footer>
<script id="lab-data" type="application/json">{json.dumps(data,separators=(',',':')).replace('</','<\\/')}</script><script src="../assets/js/strategist-lab.js?v=1"></script></body></html>'''


def execution_page(e):
    monitor=pd.read_csv(OUTPUT/"execution/venue_monitor.csv")
    sensitivity=pd.read_csv(OUTPUT/"execution/sensitivity.csv") if (OUTPUT/"execution/sensitivity.csv").exists() else None
    total=e["components_usd"]["is_usd"]/e["decision_notional"]*10000
    summary=stats([(f'{e["orders"]:,}',"Simulated parent orders across 2025"),
                   (f'{e["fills"]:,}',"Clean child fills, audited in SQLite"),
                   (f'{e["test_sessions"]}',"Sessions held out for monitoring")])+f'''
<p>A desk sees weaker net trading P&amp;L. Is the cause a more difficult order mix, an execution problem, or a fading signal? This project builds a production-style diagnostic layer to separate those explanations and support a focused investigation.</p>
<div class="lab-note"><p><strong>What the experiment establishes.</strong> The ledger reconciles exactly and the frozen monitors detect the deliberately injected episodes. Every order, quote, fill, signal and incident is synthetic. These results do not establish real venue quality, trading alpha or live detection performance.</p></div>
<p><strong>Management takeaway:</strong> investigate the Venue B execution path during its joint cost/latency break; investigate Momentum signal calibration during its later opportunity-P&amp;L break. The evidence supports two separate investigations rather than one blanket trading-cost explanation.</p>'''
    dashboard='''<p>Filter the frozen experiment by venue and evaluation period. The baseline adjusts for observable order conditions. It does not include incident labels or realised latency.</p>
<div class="lab-panel"><div class="lab-controls"><label>Venue<select id="venue-filter"><option>All</option><option>Venue A</option><option>Venue B</option><option>Venue C</option></select></label><label>Period<select id="period-filter"><option value="test" selected>Held-out monitoring</option><option value="validation">Validation / calibration</option><option value="train">Training</option><option value="all">Full experiment</option></select></label></div>
<div class="lab-summary" aria-live="polite"><div class="lab-stat"><strong id="exec-residual">—</strong><span>Mean execution residual, weighted by parent count</span></div><div class="lab-stat"><strong id="exec-latency">—</strong><span>Parent-weighted mean of session median latencies</span></div><div class="lab-stat"><strong id="exec-alerts">—</strong><span>Flagged venue sessions; alerts active only in holdout</span></div></div>
<p id="exec-live" class="lab-live" aria-live="polite"></p><svg id="execution-chart" class="lab-line-chart" viewBox="0 0 920 260" role="img" aria-label="Daily execution cost residual"></svg><noscript><p>Interactive filters require JavaScript. All findings and figures below remain available.</p></noscript></div>'''
    attribution=f'''<p>Implementation shortfall measures the difference between the intended decision-price trade and the actual outcome. Positive cost is worse. Unfilled quantity is marked at the order horizon, so an apparently cheap partial fill cannot hide a large missed opportunity.</p>
<details class="lab-method"><summary>The accounting identity</summary><p>For side <var>s</var> (+1 buy, −1 sell), intended quantity <var>Q</var>, filled quantity <var>q</var>, decision price <var>P₀</var>, arrival price <var>Pₐ</var>, synthetic horizon benchmark <var>Pᵦ</var> and terminal mid <var>Pₜ</var>:</p><p><code>IS = s[Σ qᵢPᵢ + (Q−q)Pₜ − QP₀] + fees</code></p><p><code>IS = decision delay + market move + execution + unfilled opportunity + fees</code></p><p><code>Ideal decision P&amp;L − realised net P&amp;L = IS</code></p><p>Each component uses the same decision notional. Fees are positive costs for both trade directions. A favourable market move can make a component negative.</p></details>'''+figure("cost-bridge",f"Full-sample cost attribution: {total:.2f} bps of total decision notional. All costs, benchmarks and trading opportunities are simulated.")+table(
        ["Control","Published result"],[["Exact retry messages removed",f'{e["quality"]["exact_retries_removed"]:,}'],
         ["Orphan / invalid-price rows quarantined",f'{e["quality"]["orphan_rows"]} / {e["quality"]["invalid_rows"]}'],
         ["Maximum order-level cost-bridge error",f'${e["reconciliation"]["max_cost_error_usd"]:.2e}'],
         ["Maximum ideal-to-net P&L error",f'${e["reconciliation"]["max_pnl_error_usd"]:.2e}']])
    methods=f'''<ol class="lab-list"><li><strong>Generate and audit.</strong> Create {e['sessions']} sessions with buy/sell parents, three-child partial fills, fees, no fills, retries and invalid feed rows. Only lagged historical market volatility comes from real data. Conflicting duplicate IDs and overfills stop accounting.</li>
<li><strong>Freeze a conditional cost baseline.</strong> Train Ridge regression through {e['train_end']}. Features are spread, lagged volatility, square-root participation, urgency, venue and book. Choose regularisation on the next 63 sessions, ending {e['validation_end']}. Retain the training-only fit so calibration errors remain held out.</li>
<li><strong>Score new sessions.</strong> Within each venue, compare the session mean residual to its validation median and median absolute deviation. A one-sided score above four robust standard deviations raises an execution alert. Monitor signed opportunity return minus forecast separately by book.</li>
<li><strong>Evaluate without label leakage.</strong> Join hidden simulator truth only after predictions, calibration and scores are frozen. Report every held-out venue session and book session. Latency is supporting evidence, not an input that explains away the injected cost break.</li>
<li><strong>Quantify uncertainty.</strong> Bootstrap five-session blocks of daily venue means, rather than treating child fills as independent observations. Preserve the serial dependence within each sampled block.</li></ol>'''+figure("execution-monitor","The execution-cost and latency series move together during the simulated Venue B routing episode. The dashed line marks the first held-out session.")+figure("signal-decay","The Momentum signal has a separate late-sample forecast error. Its incident is injected independently of the execution-cost shift.")
    intervals=table(["Venue","Held-out mean residual","95% block-bootstrap interval"],[[r["venue"],f'{r["residual_mean_bps"]:.2f} bps',f'[{r["ci_low"]:.2f}, {r["ci_high"]:.2f}] bps'] for r in e["venue_intervals"]])
    evaluation=table(["Monitor","True positives","False positives","Missed incidents","True negatives"],[
        [name.title(),v["tp"],v["fp"],v["fn"],v["tn"]] for name,v in e["alert_evaluation"].items()])
    sensitivity_html=''
    if sensitivity is not None:
        agg=sensitivity.groupby("shift_bps")[["tp","fp","fn","tn"]].sum()
        sensitivity_html='<h3>Weaker shifts and independent seeds</h3><p>The challenge suite uses three independent seeds, 100 orders per day and five cost-shift sizes. Thresholds stay fixed at four robust standard deviations. The zero-shift case is a sham control. All configurations are reported.</p>'+table(
            ["Injected cost shift","Flagged incident windows / 45","False alerts outside incident windows"],
            [[f'{shift:.2f} bps',f'{int(row.tp)} / 45',int(row.fp)] for shift,row in agg.iterrows()])
    robustness=evaluation+'<p>The primary incidents are deliberately strong (+6 bps execution cost and −13 bps signal decay). Perfect classification in that seeded experiment is a simulator check, not a claim of real-world precision.</p>'+intervals+sensitivity_html
    limits='''<ul class="lab-list"><li><strong>Benchmark availability:</strong> the horizon benchmark is available after the order finishes. It supports post-trade diagnosis, not a pre-trade executable price forecast.</li><li><strong>Confounding:</strong> conditional venue residuals are descriptive. Unobserved selection, order-book state and information leakage could invalidate venue comparisons in real data. This is not a causal venue ranking.</li><li><strong>Monitoring:</strong> group alerts do not control family-wise false alarms across an unlimited number of venues and books. Correlated monitoring, persistence rules, alert triage and regime recalibration would need live validation.</li><li><strong>Data requirements:</strong> production use needs event-time and receipt-time stamps, decision snapshots, cancels/corrections, corporate actions, FX, genuine market benchmarks and reconciled broker fees. The current synthetic schema intentionally exposes where those adapters belong.</li><li><strong>Statistical design:</strong> the baseline is linear and the simulator is close to its specification. Nonlinear impact, changing routing policy and abrupt market regimes would be harder tests.</li></ul>'''
    reproduce=f'''<p>Everything needed for an offline reproduction is included: frozen public volatility inputs, deterministic generator, SQL views, sample order/fill records, model coefficients, daily monitoring tables and validation tests.</p><pre class="lab-code">python -m pip install -r research/strategist_lab/requirements.txt
python -m research.strategist_lab --project execution --keep-db
python -m research.strategist_lab.robustness
python -m unittest discover -s research/strategist_lab/tests -v</pre>
<p>The full generated ledger stays local. The website is static and contains no credentials or broker connection.</p>
<div class="lab-downloads"><a href="{REPO}/execution.py">Python implementation</a><a href="{REPO}/sql/diagnostics.sql">SQL accounting</a><a href="../research/strategist_lab/results/execution/daily.csv">Daily results CSV</a><a href="../research/strategist_lab/results/execution/metrics.json">Full metrics JSON</a><a href="{REPO}/METHODOLOGY.md">Methodology and assumptions</a></div>
<p class="lab-foot">Source for lagged market volatility: <a href="https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html">Kenneth French Data Library</a>, daily market excess return. Latest revised source vintage is recorded in the <a href="../data/strategist_lab/manifest.json">input manifest</a>. All trading records are synthetic.</p>'''
    body=section("question","Where did the trading edge go?",summary,"Research question")+section("monitor","Explore the production monitor",dashboard,"Interactive snapshot")+section("accounting","Account for every dollar",attribution,"P&L reconciliation")+section("method","Separate execution from signal performance",methods,"Research design")+section("validation","Measure detection rather than admire a chart",robustness,"Held-out validation")+section("limits","What the experiment cannot establish",limits,"Limitations")+section("code","Run, inspect and extend the study",reproduce,"Reproducibility")
    records=json.loads(monitor.round(6).to_json(orient="records"))
    return page("Trading Performance Diagnostics","Execution quality · P&L attribution · production monitoring",
        "An audited order-to-P&L research system that distinguishes trading-cost deterioration from signal decay, with frozen validation and an interactive production monitor.",
        "SYNTHETIC TRADING RECORDS · REAL LAGGED VOLATILITY INPUT",body,
        [("question","Question"),("monitor","Monitor"),("accounting","Accounting"),("method","Methods"),("validation","Validation"),("code","Code")],
        {"project":"execution","rows":records,"train_end":e["train_end"],"validation_end":e["validation_end"]})


def portfolio_page(p):
    perf={row["method"]:row for row in p["performance"]}
    minimum=perf["minimum_variance"];equal=perf["equal"]
    reduction=1-minimum["annual_vol"]/equal["annual_vol"]
    interval_path=OUTPUT/"portfolio/volatility_ratio_interval.json"
    interval=json.loads(interval_path.read_text()) if interval_path.exists() else None
    summary=stats([("2015–2025","Frozen public daily input window"),("6 books","Disclosed industry tilts with overlapping exposures"),(f'{p["sessions"]:,}',"Walk-forward evaluation sessions, 2020–2025")])+f'''
<p>Six book names can create an impression of diversification while sharing the same market, growth or industry exposures. This study asks how much risk is actually diversified, which books contribute to losses, and what happens when capital allocation changes.</p>
<p><strong>Main finding:</strong> in this historical illustration, minimum-variance allocation reduced realised annual volatility by {reduction:.0%}, from {equal['annual_vol']:.2%} to {minimum['annual_vol']:.2%}. Its annualised return also fell, from {equal['cagr']:.2%} to {minimum['cagr']:.2%}. Risk reduction comes with an observable return trade-off.</p>
<div class="lab-note"><p><strong>Data distinction.</strong> Industry and factor returns are real public research data. Book definitions, capital allocations, financing and transaction costs are illustrative. The industry indices are not directly tradable and the books are not QRT or hedge-fund performance.</p></div>'''
    dashboard=f'''<p>Change the final capital allocation, marginal volatility, common correlation shock or exposure scale. Calculations use the last 252 sessions available at {p['as_of']}; the snapshot forecasts the following session. Historical backtest returns below do not change when these controls move.</p>
<div class="lab-panel"><div class="lab-controls"><label>Capital allocation<select id="allocation-filter"><option value="minimum_variance">Minimum variance</option><option value="equal">Equal allocation</option><option value="inverse_vol">Inverse volatility</option></select></label>
<label>Volatility multiplier <output id="vol-value">1.00×</output><input id="vol-multiplier" type="range" min="50" max="250" step="5" value="100"></label>
<label>Correlation blend to +1 <output id="corr-value">0%</output><input id="correlation-blend" type="range" min="0" max="100" step="5" value="0"></label>
<label>Exposure scale <output id="leverage-value">1.00×</output><input id="leverage" type="range" min="50" max="200" step="5" value="100"></label></div>
<div class="lab-summary" aria-live="polite"><div class="lab-stat"><strong id="risk-vol">—</strong><span>Modelled annual volatility</span></div><div class="lab-stat"><strong id="risk-var">—</strong><span>Normal 99% one-day VaR on $10m NAV</span></div><div class="lab-stat"><strong id="risk-budget">—</strong><span>Capital deployed before netting book exposures</span></div></div>
<p class="lab-live" id="risk-live" aria-live="polite"></p><div class="lab-table-wrap"><table class="lab-table"><thead><tr><th scope="col">Book</th><th scope="col">Capital weight</th><th scope="col">Annual volatility contribution</th></tr></thead><tbody id="risk-table-body"></tbody></table></div>
<p class="lab-foot">The correlation shock is a convex blend towards a matrix of ones, preserving a valid covariance matrix. Exposure scaling multiplies risk linearly; funding costs and market-impact feedback are excluded from this instantaneous scenario.</p><noscript><p>Enable JavaScript to explore scenarios. Static results are available below.</p></noscript></div>'''
    research='''<ol class="lab-list"><li><strong>Inputs and books.</strong> Use ten value-weighted US industry return series and the five Fama–French factors. Define six fixed 100%-gross industry books with disclosed long and short weights. Add cash financing, a 50 bps annual short-borrow assumption and daily internal rebalance costs.</li>
<li><strong>Risk estimation.</strong> Estimate book covariance with Ledoit–Wolf shrinkage from the previous 252 sessions. Estimate factor sensitivities by OLS on the same window and reconcile common-factor and residual sample variance separately from the shrinkage model.</li>
<li><strong>Capital decisions.</strong> At the first session of each month, compare equal allocation, inverse volatility and minimum variance under identical 3%–35% book bounds and a 15% one-way turnover budget. Between decisions, sleeve weights drift self-financingly with returns.</li>
<li><strong>Costs and chronology.</strong> Charge 2 bps per dollar of gross allocation trading, including initial deployment. Each forecast and allocation excludes the current session return; forecast cash carry uses the prior session RF. The implementation records the maximum input date for every forecast.</li>
<li><strong>Evaluation.</strong> Evaluate 2020–2025 using rules fixed in code, without optimising expected return. Compare realised volatility, drawdown, return, turnover, tail-risk exceptions, fixed-exposure historical stresses and lookback sensitivity.</li></ol>
<details class="lab-method"><summary>Risk contributions and factor attribution</summary><p>For book weights <var>w</var> and daily covariance <var>Σ</var>, daily volatility is <code>σ = √(wᵀΣw)</code>. Book <var>i</var> contributes <code>RCᵢ = wᵢ(Σw)ᵢ / σ</code>. Contributions sum exactly to portfolio volatility; a negative contribution is a hedge.</p><p>The factor model is <code>book excess return = intercept + β × factor returns + residual</code>. OLS with an intercept makes factor and residual covariance orthogonal in the fitted sample. The intercept is a sample residual mean, not proof of skill.</p><p>Historical VaR is the negative 1% empirical return quantile of 252 prior scenarios at the current starting allocation. Expected shortfall averages the scenarios at or below that quantile. Normal VaR uses zero expected excess return and shrunken covariance. These are different models and are assessed separately.</p></details>'''
    performance=figure("portfolio-performance","All three allocations use the same disclosed book universe, costs and constraints. This is a retrospective walk-forward exercise on revised source files, not a pristine historical point-in-time test.")+table(
        ["Capital rule","Annualised return","Annual volatility","Maximum drawdown","Excess Sharpe"],
        [[LABELS[m],f'{r["cagr"]:.2%}',f'{r["annual_vol"]:.2%}',f'{r["max_drawdown"]:.2%}',f'{r["excess_sharpe"]:.2f}'] for m,r in perf.items()])
    if interval:
        performance+=f'<p>A paired 20-session moving-block bootstrap estimates a minimum-variance/equal-allocation volatility ratio of {interval["point"]:.2f}, with a 95% interval [{interval["ci95"][0]:.2f}, {interval["ci95"][1]:.2f}]. This describes sampling uncertainty conditional on the chosen books and rules; it excludes design and model uncertainty.</p>'
    exposures=figure("risk-contributions","Final capital weights and signed Euler contributions. Capital allocation is not the same quantity as risk allocation.")+figure("correlation","Last-window return correlations reveal similar and offsetting books; this is return co-movement, not evidence of external-manager crowding.")+figure("factor-stress","Market, size, value, profitability and investment betas describe common exposures. The correlation shock changes co-movement while preserving the individual book volatilities.")+f'<p>At the final snapshot, {p["factor_model"]["common_share"]:.0%} of fitted sample variance is explained by the five-factor common component. The underlying industry exposure is {p["gross_after_netting"]:.0%} gross after cross-book netting, versus {p["gross_before_netting"]:.0%} before netting. Return correlations alone cannot identify shared stock holdings.</p>'
    cover=p["coverage"]["minimum_variance"]
    tail=cover["var99"]
    validation=f'<div class="lab-note"><p><strong>Adverse finding:</strong> historical 99% VaR produced {tail["exceptions"]} exceptions versus {tail["expected_exceptions"]:.1f} expected, with an exception rate of {tail["exception_rate"]:.2%}. Coverage and independence tests both reject at the 5% level in this sample. The model understates and clusters tail losses; this warrants a different volatility or tail specification before operational use.</p></div>'+figure("var-backtest","Historical 99% VaR exceptions are checked against realised returns. Clusters of exceptions can expose slow adaptation even when average coverage looks reasonable.")+table(
        ["Minimum-variance risk model","Exceptions / expected","Exception rate","Kupiec p","Independence p"],
        [[{"var95":"Historical 95%","var99":"Historical 99%","normal_var99":"Normal 99%"}[key],
          f'{r["exceptions"]} / {r["expected_exceptions"]:.1f}',f'{r["exception_rate"]:.2%}',f'{r["uc_p"]:.3f}',f'{r["independence_p"]:.3f}'] for key,r in cover.items()])+'''<p>Kupiec tests average exception coverage; Christoffersen tests dependence between consecutive exception indicators. Small p-values are evidence against the respective model property. These asymptotic diagnostics have limited power for rare events; a large p-value does not validate a tail model.</p>'''+table(
        ["Historical scenario","Window","Frozen final-allocation return","P&L on $10m"],
        [[r["name"],r["start"]+' to '+r["end"],f'{r["return"]:.2%}',f'${r["pnl_usd"]:,.0f}'] for r in p["historical_stress"]])+'''<p>Historical stresses replay each book’s compounded returns using the final allocation without reallocating between books. They are counterfactual exposures to past shocks, not the portfolio’s realised returns in those windows. Daily internal book maintenance and borrow assumptions remain in the book returns.</p>'''
    path=OUTPUT/"portfolio/lookback_sensitivity.csv"
    if path.exists():
        sensitivity=pd.read_csv(path)
        validation+='<h3>Keep the full lookback comparison</h3>'+table(["Prior sessions","Equal volatility","Inverse-volatility volatility","Minimum-variance volatility"],[
            [n]+[f'{group.loc[group.method==key,"volatility"].iloc[0]:.2%}' for key in LABELS] for n,group in sensitivity.groupby("lookback")])
    limits='''<ul class="lab-list"><li><strong>Revised indices:</strong> the frozen 2015–2025 inputs were downloaded in 2026. The source uses revised CRSP data and changed its US research-return process in 2025. Availability dates and historical vintages are not reconstructed.</li><li><strong>Book construction:</strong> these fixed tilts were selected for an interpretable risk exercise. Their labels do not represent discovered alpha strategies, a current-stock survivor universe or live hedge-fund books. There is no untouched prospective holdout.</li><li><strong>Implementation:</strong> industry portfolios are research indices. Real replication needs securities, corporate actions, borrow availability, spreads, volume, funding, FX and transaction-level impact. The cost grid is an assumption check, not an estimate of trading capacity.</li><li><strong>Risk model:</strong> linear factors, 252-session covariance and normal scenarios miss nonlinear payoffs, jump risk and fast regime changes. A historical 99% tail in 252 sessions rests on only a few observations.</li><li><strong>Crowding interpretation:</strong> this measures internal exposure overlap and return co-movement. It does not measure how many outside funds hold the same positions or predict a crowded unwind.</li><li><strong>Decision scope:</strong> a minimum-variance allocation is a risk-budget illustration. It ignores expected alpha, liquidity horizons, manager capacity and the cost of withdrawing capital, so it is not an investment recommendation.</li></ul>'''
    reproduction=f'''<p>The frozen inputs, source hashes, book weights, daily forecasts, monthly allocation decisions, risk metrics and sensitivity results are committed alongside the code.</p><pre class="lab-code">python -m pip install -r research/strategist_lab/requirements.txt
python -m research.strategist_lab --project portfolio
python -m research.strategist_lab.robustness
python -m unittest discover -s research/strategist_lab/tests -v</pre>
<div class="lab-downloads"><a href="{REPO}/portfolio.py">Python risk engine</a><a href="../research/strategist_lab/results/portfolio/walk_forward.csv">Daily forecasts CSV</a><a href="../research/strategist_lab/results/portfolio/allocations.csv">Allocation history CSV</a><a href="../research/strategist_lab/results/portfolio/metrics.json">Full metrics JSON</a><a href="{REPO}/METHODOLOGY.md">Methods and accounting</a></div>
<p class="lab-foot">Primary sources: <a href="https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html">Kenneth French Data Library</a>, <a href="https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_10_ind_port.html">ten-industry portfolio construction</a>, and <a href="https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html">Ledoit–Wolf implementation</a>. Underlying data copyright: Eugene F. Fama and Kenneth R. French. Download vintage and hashes: <a href="../data/strategist_lab/manifest.json">manifest</a>.</p>'''
    body=section("question","Are six books really six independent risks?",summary,"Research question")+section("scenario","Explore the risk budget",dashboard,"Interactive stress tool")+section("method","Build an auditable capital-allocation experiment",research,"Research design")+section("results","Assess the risk and return trade-off",performance,"Walk-forward evidence")+section("exposure","Look through book labels to their exposures",exposures,"Portfolio deep dive")+section("validation","Challenge the tail model and allocation rules",validation,"Risk validation")+section("limits","Where the evidence stops",limits,"Limitations")+section("code","Reproduce the complete analysis",reproduction,"Code and data")
    return page("Portfolio Risk and Crowding Lab","Factor attribution · stress testing · capital allocation",
        "A daily risk research system that reveals shared exposures, validates tail forecasts and compares constrained capital-allocation rules on public historical data.",
        "PUBLIC HISTORICAL RETURNS · ILLUSTRATIVE BOOKS AND COSTS",body,
        [("question","Question"),("scenario","Scenarios"),("method","Methods"),("results","Results"),("validation","Validation"),("code","Code")],
        {"project":"portfolio",**p},public=True)


def build_reports():
    ep=OUTPUT/"execution/metrics.json";pp=OUTPUT/"portfolio/metrics.json"
    if not ep.exists() or not pp.exists():return
    e=json.loads(ep.read_text());p=json.loads(pp.read_text())
    figures(e,p)
    (ROOT/"projects/trading-performance.html").write_text(execution_page(e))
    (ROOT/"projects/portfolio-risk.html").write_text(portfolio_page(p))
    perf={row["method"]:row for row in p["performance"]}
    brief=f'''# Quantitative strategist research — decision brief

## Trading Performance Diagnostics

- Question: is weaker net trading performance caused by execution or signal deterioration?
- Experiment: {e['orders']:,} synthetic parent orders and {e['fills']:,} clean child fills; {e['test_sessions']} held-out sessions.
- Accounting: maximum cost-bridge error ${e['reconciliation']['max_cost_error_usd']:.2e}; retries are idempotent, invalid messages quarantined, conflicting IDs and overfills fail.
- Findings: independent simulated routing and signal-decay episodes are separated by cost residuals, latency and forecast errors. Classification tables and weaker-effect challenge cases are included.
- Decision: investigate execution routing separately from signal calibration. Venue comparisons remain descriptive.
- Limit: this validates a transparent simulator and accounting/monitoring implementation, not a live market result.

## Portfolio Risk and Crowding Lab

- Question: do different books share risk, and what changes when capital is reallocated?
- Inputs: real French industry and five-factor daily returns, 2015–2025; six disclosed illustrative books; 2020–2025 walk-forward evaluation.
- Equal allocation: {perf['equal']['cagr']:.2%} annualised return, {perf['equal']['annual_vol']:.2%} annual volatility, {perf['equal']['max_drawdown']:.2%} maximum drawdown.
- Minimum variance: {perf['minimum_variance']['cagr']:.2%} annualised return, {perf['minimum_variance']['annual_vol']:.2%} annual volatility, {perf['minimum_variance']['max_drawdown']:.2%} maximum drawdown.
- Decision: allocation changes risk and realised return together; investigate factor exposures, risk contributions and tail exceptions before changing the risk budget.
- Limit: revised public indices and illustrative books/costs, not directly tradable assets or genuine fund performance. No alpha or capacity claim.

## Role relevance

These projects demonstrate trading-data analytics, daily risk tools, strategic deep dives, continuous monitoring and communication of methods and results. They are independently designed portfolio work, with no QRT data or affiliation.
'''
    (ROOT/"research/strategist_lab/DECISION_BRIEF.md").write_text(brief)


if __name__=="__main__":build_reports()

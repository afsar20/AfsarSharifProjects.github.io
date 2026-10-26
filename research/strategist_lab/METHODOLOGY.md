# Methods, accounting and research boundaries

## 1. Shared conventions and reproducibility

- Return inputs and risk calculations use daily **decimals**, not source percentages. One basis point is 0.0001. Volatility annualisation uses 252 sessions. Dollar scenarios use $10m constant reference NAV, not a claim of deployed capital.
- The source window is 2015-01-01 to 2025-12-31, with 2,766 matching industry/factor dates. The industry parser uses the first, value-weighted daily table only and stops before the equal-weighted table.
- Source missing sentinels become missing values and fail validation if they occur in the selected sample. Dates must be unique and increasing; inputs are never forward filled. The two input calendars must match exactly.
- The manifest records original archive URLs, SHA-256 hashes, source headers, retrieval time, units and output CSV hashes. Default runs verify those hashes and use no network.
- The source files were downloaded after the evaluation period and can contain revisions. They do not reconstruct publication lags or historical CRSP vintages. This is a causal computational chronology on revised public history, not a genuine point-in-time historical dataset.
- Seeds are fixed. Dependencies are pinned to the versions used to build the published results. CSVs preserve sufficient decimal precision; accounting checks run on unrounded engine values.

## 2. Trading Performance Diagnostics

### 2.1 Research question and simulation

The goal is to distinguish deteriorating execution from deteriorating signal forecasts. The default experiment creates 400 orders on each of 250 source sessions in 2025: 100,000 parents. Three named venues and three books are fictitious.

Every decision, quote, benchmark, order size, fill, fee, latency and signal is simulated. The **only real market input** is a 20-session market-return volatility estimate shifted by one session. Signed terminal price moves are drawn from an explicit forecast-plus-noise model; they are not genuine intraday price paths.

Filled orders are split into three integer child quantities. Some parents remain unfilled. The dirty event feed contains 1% exact retry messages, an orphan fill and an invalid negative price. Exact retries are removed by fill ID. Conflicting duplicate IDs, duplicate parent IDs or parent overfills stop processing. Invalid/orphan rows are quarantined and counted before SQL aggregation. The database enforces unique keys on accepted events.

The main experiment injects two non-overlapping cost/signal mechanisms:

- Venue B: +6 bps execution cost, additional 180 ms latency and lower completion during session indices 210–224.
- Momentum: a 13 bps deterioration in the signed forecast-to-terminal move from index 235 onwards.

These intentionally strong mechanisms make a transparent accounting/monitoring validation case. They are not a realistic generative model of a full exchange order book.

### 2.2 Implementation shortfall and P&L

Let $s\in\{-1,+1\}$ denote sell/buy side, $Q$ intended shares, $q=\sum_i q_i$ filled shares, $P_0$ decision price, $P_a$ arrival mid, $P_b$ the synthetic order-horizon benchmark, and $P_T$ the final mark. All prices share one currency.

$$\mathrm{IS}=s\left[\sum_iq_iP_i+(Q-q)P_T-QP_0\right]+F.$$

The additive components are:

$$D=sq(P_a-P_0),\qquad M=sq(P_b-P_a),$$
$$E=s\left(\sum_iq_iP_i-qP_b\right),\qquad O=s(Q-q)(P_T-P_0),$$
$$\mathrm{IS}=D+M+E+O+F.$$

The ideal marked trading opportunity is $sQ(P_T-P_0)$. Realised net P&L is $s\sum_iq_i(P_T-P_i)-F$. Their difference must equal implementation shortfall for every parent, including sells, no fills and partial fills.

Positive shortfall means worse performance. Negative components are possible. Aggregate component bps divide total component dollars by total **intended decision notional**, preserving the additive identity. This differs from the regression target, which measures filled execution cost per filled share relative to decision price:

$$e=10^4s\frac{\sum_iq_iP_i/q-P_b}{P_0}.$$

Parents with no fills are excluded from that regression, but stay in total opportunity cost and P&L. Counts, share-weighted fill rates, decision-notional-weighted daily cost bps and parent-weighted diagnostic residuals are distinct statistics. The website identifies their denominators.

### 2.3 Chronological baseline and monitoring

- Training: first 126 sessions.
- Validation/calibration: next 63 sessions.
- Monitoring holdout: final 61 sessions.

Ridge predicts execution cost from spread, lagged volatility, square-root participation, urgency, venue and book. Numeric standardisation and categorical encoding are fitted **inside the training pipeline**. Regularisation candidates are 0.1, 1, 10 and 100, selected on validation MAE. The training-only fit is retained; there is no refit that would contaminate the held-out calibration errors.

Realised latency is deliberately excluded from model features. It supports a later root-cause investigation; including it could normalise away a production fault. Hidden simulator incident indicators never enter features or thresholds.

For each venue, take the daily parent mean of execution residuals. The validation distribution supplies median $m$ and robust scale $a=\max(1.4826\operatorname{MAD},0.05\text{ bps})$. The one-sided monitoring score is $(r-m)/a$; scores above four flag an execution issue. For each book, monitor the lower tail of signed terminal move minus original forecast with the same calibration method. Only holdout alerts are active.

The truth table joins **after** model fitting, calibration and scoring. Confusion matrices count venue sessions or book sessions, not independent orders. A single injected venue contributes 15 incident windows; a single affected book contributes 15 signal-decay windows.

Five-session moving-block bootstrap intervals resample daily venue means, preserving within-block dependence. There are 1,500 replicates under a fixed independent seed. The resulting interval is for a held-out mean residual in this simulator; it is not a routing treatment effect.

### 2.4 Challenge experiments and limits

The predeclared grid uses seeds 71, 113 and 997; 100 orders per day; and injected cost shifts of 0, 0.25, 0.5, 1 and 6 bps. All 15 cases retain the same detector form, thresholds and chronological split. The zero-cost-shift control still changes latency/completion, but should not systematically trigger an execution-cost detector. The table reports incident-window detections and false positives outside the labelled window. A sham-window alert is also a false positive in substantive interpretation; the published zero-shift window has none.

The simulator is close to the linear model's assumptions; strong primary-case classification is expected. No family-wide false-alert guarantee is made. Real monitoring requires independent data, policy-change controls, alert persistence, multiple-testing decisions and operational triage. Comparing residuals across chosen venues remains descriptive unless the routing assignment is credibly exogenous.

## 3. Portfolio Risk and Crowding Lab

### 3.1 Public returns and disclosed illustrative books

Ten French value-weighted US industries provide total returns. Factors are market excess, size, value, profitability and investment; RF is the daily cash return. The six books are fixed rows of the following matrix. Each has unit gross industry exposure, and some have non-zero net exposure.

| Book | NoDur | Durbl | Manuf | Enrgy | HiTec | Telcm | Shops | Hlth | Utils | Other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Technology tilt | 0 | 0 | −.20 | −.20 | .50 | .10 | 0 | 0 | 0 | 0 |
| Digital consumer | −.15 | .10 | 0 | 0 | .30 | 0 | .30 | 0 | −.15 | 0 |
| Defensive spread | .20 | −.20 | −.20 | 0 | 0 | 0 | 0 | .20 | .20 | 0 |
| Cyclical spread | −.15 | 0 | .25 | .25 | 0 | 0 | 0 | 0 | −.20 | .15 |
| Consumer relative | 0 | .25 | 0 | 0 | 0 | −.25 | .25 | 0 | 0 | −.25 |
| Diversified equity | .10 | .10 | .10 | .10 | .10 | .10 | .10 | .10 | .10 | .10 |

This deliberately creates interpretable exposure overlap. The labels are not strategy-performance claims. The selection is retrospective and there is no untouched prospective alpha holdout.

For industry weight row $W_b$, gross daily excess book P&L is $W_b(r^{industry}-r_f)$. A book's total return is $r_f$ plus net excess P&L. Short proceeds/uninvested capital earn RF; shorts cost 50 bps annually on short gross, charged as 50/252 bps daily. Daily maintenance rebalances industry weights to their fixed targets at an assumed 2 bps per gross dollar traded. Internal maintenance turnover uses prior-session industry and book value drift; the source assets are research indices, so these costs are transparent proxies.

### 3.2 Capital allocation and self-financing chronology

Evaluation is 2020–2025. Before each session, only the preceding 252 book returns enter its risk forecast. On the first trading session of each month, three policies choose capital weights:

1. Equal allocation, projected into the common feasible set.
2. Inverse standalone volatility, projected into the same feasible set.
3. Minimum annual variance, using Ledoit–Wolf covariance.

The common constraints are $\sum_b w_b=1$, $0.03\leq w_b\leq0.35$, and $\frac12\sum_b|w_b-w_b^{pretrade}|\leq0.15$. The initial reference is equal weights. Initial gross deployment is charged 2 bps; later allocation changes cost 2 bps times gross sleeve turnover. Gross turnover is twice the one-way turnover convention. No expected alpha input is estimated or optimised.

The optimiser uses explicit auxiliary variables for absolute trades and analytic gradients, making the turnover constraints linear. A failed or infeasible solve raises an error rather than silently reporting a fabricated optimum.

Between monthly decisions, weights drift with book total returns divided by realised portfolio wealth. Cash bears the financing/cost residual. Portfolio total return is daily RF plus weighted net excess book returns minus allocation trading cost. Fees are charged separately from book-level borrow and maintenance; those costs are not duplicated.

Every forecast records its latest input date. Current realised RF is used in realised P&L; **prior RF** is used for forecast carry. Future-mutation tests change later returns and RF, and require earlier decisions and forecasts to remain unchanged. Numerical reproducibility is stabilised by contiguous covariance inputs and analytic optimiser derivatives.

### 3.3 Risk, factor and overlap measures

Ledoit–Wolf shrinks the sample covariance towards a scaled identity matrix. For daily covariance $\Sigma$ and snapshot capital weights $w$:

$$\sigma_p=\sqrt{w^\top\Sigma w},\qquad RC_b=\frac{w_b(\Sigma w)_b}{\sigma_p}.$$

The signed Euler contributions sum exactly to daily portfolio volatility. Multiply both by $\sqrt{252}$ for annual units. A negative contribution is a hedge, so it is not silently clipped. The effective risk-book count uses normalised **absolute** contributions and is a descriptive concentration measure, not a count of statistically independent books.

OLS on the last 252 observations regresses excess book returns on an intercept and the five factors. The intercept ensures fitted factor and residual innovations are sample-orthogonal. Common-factor plus residual portfolio variance must reconcile to **sample** variance, not the separate shrunken variance. Betas describe common exposures; sample intercepts do not establish manager skill.

Return correlations and their leading eigenvalue reveal shared co-movement. Net industry weights are $w^\top W$. Gross exposure before netting is $\sum_bw_b\sum_j|W_{bj}|$; after netting it is $\sum_j|\sum_bw_bW_{bj}|$. Neither return correlation nor industry overlap establishes external stock-level crowding.

### 3.4 Tail forecasts and exception tests

Before session $t$, apply its beginning capital allocation to each of the previous 252 daily book scenarios, with prior-session RF and today's known allocation cost. Historical VaR95/VaR99 are the negative empirical 5%/1% return quantiles, floored at zero. ES99 is the negative mean of scenarios at or below the 1% quantile. The small tail sample is disclosed.

Normal VaR99 uses $\Phi^{-1}(0.99)\sigma_p$, adjusted for forecast cash carry and known allocation cost; no estimated positive mean is credited. The instantaneous interactive scenario uses zero mean and a $10m reference NAV.

An exception occurs when realised return is less than negative forecast VaR. Kupiec compares the observed hit rate with its nominal probability through a likelihood-ratio test. Christoffersen compares a two-state first-order hit transition model to independence. Their likelihood-ratio statistics are assessed using asymptotic chi-square reference distributions; p-values are diagnostics rather than proof of model validity. Zero/all-hit edge cases use stable $0\log 0=0$ arithmetic.

The published 99% forecasts show more exceptions than expected and temporal clustering. That is an adverse model finding requiring follow-up, not an omitted result. Normal and historical estimates are not treated as guaranteed loss limits.

### 3.5 Stress, uncertainty and sensitivity

- Historical replays use COVID (2020-02-19 to 2020-03-23), calendar 2022, and 2025-04-02 to 2025-04-08. They apply final capital weights to compounded historical book returns without capital reallocation; internal book maintenance and borrow assumptions stay in place. These are counterfactual final-exposure scenarios, not the historical realised allocation path.
- The interactive correlation matrix is $R_\rho=(1-\rho)R+\rho\mathbf1\mathbf1^\top$, $0\leq\rho\leq1$. This convex combination preserves positive semidefiniteness and unit diagonal. Covariance uses unchanged marginal volatilities times a chosen common volatility multiplier. Exposure scaling multiplies the resulting risk linearly. It excludes liquidation feedback and funding changes.
- The lookback grid is 126, 252 and 504 prior sessions, evaluated for **all three** allocation rules. No best configuration is selected after inspection.
- A paired 20-session moving-block bootstrap of the minimum-variance and equal-allocation evaluation returns estimates their realised volatility ratio; 1,500 draws under seed 8901 preserve dependence across the two allocations. It conditions on fixed book definitions/rules and excludes design uncertainty and future regimes.
- Additional allocation cost assumptions of 0, 2, 5 and 10 bps per gross dollar are retained in the metrics. They affect allocator turnover costs only and are **not** an impact/capacity model. Internal maintenance costs and short-borrow assumptions are not refitted in this grid.

### 3.6 Interpretation and extensions

Minimum variance can produce lower realised risk and lower realised return at the same time. Performance tables retain both results. Sharpe uses daily total return minus contemporaneous RF and annualises by $\sqrt{252}$; it is not selected as an optimisation target. CAGR compounds net returns; drawdown starts with wealth 1 so an initial loss is counted.

The books are linear research-index exposures. Real implementation needs position-level P&L reconciliation, tradable instruments, delisting/corporate-action treatment, liquidity, borrow availability, actual financing, security-level factors, prospective testing and nonlinear stress for derivatives. The project makes no claim about external funds, QRT methods, tradable alpha or optimal live capital allocation.

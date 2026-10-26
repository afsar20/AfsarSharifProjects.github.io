# Quantitative strategist research

Two complementary, fully implemented studies for a trading analytics / portfolio strategy role. Both provide an executive research page, inspectable Python, frozen inputs, exported results, methods, sensitivity experiments and meaningful validation tests.

| Study | Decision it supports | Main technical work |
|---|---|---|
| [Trading Performance Diagnostics](https://afsar20.github.io/AfsarSharifProjects.github.io/projects/trading-performance.html) | Investigate execution deterioration separately from signal decay | Audited order/fill ingestion, SQL cost and P&L identities, conditional Ridge baseline, chronological calibration, group monitors, block bootstrap, labelled simulator challenges |
| [Portfolio Risk and Crowding Lab](https://afsar20.github.io/AfsarSharifProjects.github.io/projects/portfolio-risk.html) | Understand common exposures, risk budgets and capital-allocation trade-offs | Public industry/factor returns, financing and cost accounting, shrinkage covariance, Euler contributions, factor attribution, constrained allocation, VaR/ES, coverage tests, historical and parametric stress |

## Why these studies fit the role

The [QRT Quantitative Strategist posting, ID 6785866002](https://www.qube-rt.com/careers/job?gh_jid=6785866002), emphasises analysing trading/production data, providing decision material to management, developing daily risk tools, sharing methodology and conducting portfolio deep dives. These projects demonstrate those activities directly. They are independent research and have no QRT affiliation or data.

The two studies are intentionally complementary: the first shows order-level production analytics; the second shows portfolio-level risk judgement. The findings include failures and trade-offs, not just favourable statistics.

## Reproduce offline

Run from the repository root, using Python 3.12 in a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r research/strategist_lab/requirements.txt
python -m research.strategist_lab
python -m research.strategist_lab.robustness
python -m research.strategist_lab.reports
python -m unittest discover -s research/strategist_lab/tests -v
```

The first command runs both studies and renders the website pages. The second runs the full predeclared sensitivity grids; the third incorporates those robustness results into the research pages. All normal runs use the committed, hashed CSV inputs and need no API key, brokerage account or internet connection. The full run takes seconds to tens of seconds on an ordinary laptop, depending on hardware.

To run one engine or retain a queryable full ledger:

```bash
python -m research.strategist_lab --project execution --keep-db
python -m research.strategist_lab --project portfolio
```

The generated SQLite database is ignored by git; query `order_diagnostics` and `daily_production` using your SQLite client. Only a small internally consistent sample of clean orders and fills is committed. Changing `--orders-per-day` changes the simulation sample size and the published execution statistics when reports are rebuilt.

To intentionally replace the frozen input vintage, use `--refresh-data`. That action downloads the current French source archives, restricts the same 2015–2025 window, rewrites the hashes and reruns the requested study. It is never performed implicitly. A future source revision may change historical results; retain the manifest with each research version.

## Read the research

- [Decision brief](DECISION_BRIEF.md): findings, action and limitations for a manager.
- [Methodology](METHODOLOGY.md): units, formulas, chronology, constraints, costs and inference limits.
- [Trading notebook](../../notebooks/trading_performance_diagnostics.ipynb).
- [Risk notebook](../../notebooks/portfolio_risk_crowding.ipynb).
- [Execution engine](execution.py), [SQL accounting](sql/diagnostics.sql), [risk engine](portfolio.py), [data provenance](data.py), [sensitivity experiments](robustness.py).
- [Tests](tests/test_research.py): ledger invariants, missing-data rejection, duplicate conflict handling, future-mutation tests, positive-semidefinite covariance, factor and Euler reconciliation, and allocation constraints.

## Data and output map

```text
data/strategist_lab/             frozen decimal daily returns and source manifest
research/strategist_lab/
  data.py                       source parsing, freezing and SHA-256 validation
  execution.py                  synthetic ledger, accounting, modelling and monitors
  sql/diagnostics.sql           auditable parent-level and session-level views
  portfolio.py                  book construction, allocation, risk and backtesting
  robustness.py                 fixed sensitivity grids and block-bootstrap interval
  reports.py                    result-driven figures, pages and decision brief
  results/execution/            daily and group monitors, ledger samples, coefficients
  results/portfolio/            daily forecasts, monthly decisions, returns and tests
  tests/                        numerical and chronology checks
```

The publication figures are SVGs generated with Matplotlib. Interactive controls run locally in the browser over an embedded research snapshot; the website does not connect to a trading service or submit orders.

## Data provenance and interpretation

The primary sources are the [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), its [ten-industry construction description](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_10_ind_port.html) and the [scikit-learn Ledoit–Wolf implementation](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html). Underlying French data remain copyright Eugene F. Fama and Kenneth R. French; this repository does not claim ownership of those data.

The committed sample spans 2015–2025 and was retrieved on 25 October 2026 from the source's August 2026 vintage. It is a revised historical research dataset, not a reconstructed historical information set. Normal runs are frozen to that sample even if newer data become available.

All trading records and incidents are simulated. Industry/factor returns are real; the risk study's books, financing, costs and allocation policies are illustrative. Neither study establishes tradable alpha, real venue superiority, real hedge-fund returns, external-manager crowding or market capacity. No employer or client information is included.

## Natural extensions

1. Replace synthetic trading records through a schema-preserving adapter; add event/receipt timestamps, corrections, currency conversion, genuine quotes and multiple horizons.
2. Test monitor persistence, multiple-testing control and regime shifts on independently sourced executions; use randomisation or a credible causal design before making routing recommendations.
3. Replace industry research books with daily real positions and reconciled P&L; model borrow recalls, liquidity horizons, nonlinear assets and manager capacity.
4. Compare volatility-responsive and heavy-tailed risk models using a prospective validation protocol; current VaR exceptions show why this matters.

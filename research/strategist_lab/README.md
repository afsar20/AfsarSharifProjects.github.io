# Execution and portfolio studies

These studies examine two different trading questions. The website gives a plain-language explanation; the source and methods files contain the calculation details.

**Execution costs and trading results.** Follow 100,000 simulated orders from the original decision to the final result. Separate execution costs from forecast quality, check that every order's profit and costs reconcile, and test alerts on later days. Large inserted problems were detected; small changes were harder to identify. All trades and incidents are simulated.

**Portfolio risk and allocation.** Divide money between six example industry portfolios using three allocation rules. Compare returns, volatility and losses, then check the risk forecasts against subsequent days. The lowest-risk rule reduced volatility and losses but also earned less. The 99% loss model was exceeded too often. Industry returns are public data; the portfolios and costs are illustrative.

## Run the studies

Use Python 3.12 and run from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r research/strategist_lab/requirements.txt
python -m research.strategist_lab
python -m research.strategist_lab.robustness
python -m research.strategist_lab.reports
python -m unittest discover -s research/strategist_lab/tests -v
```

The first analysis command runs both studies. The next repeats the comparisons under the saved alternative settings. The report command rebuilds the pages and figures from those results. Normal runs use the saved input files and do not need internet access or an API key.

To run one study or keep a full queryable order record:

```bash
python -m research.strategist_lab --project execution --keep-db
python -m research.strategist_lab --project portfolio
```

The generated SQLite database is excluded from git. It contains `order_diagnostics` and `daily_production` tables for review. A small matching sample of orders and fills is committed. Changing `--orders-per-day` changes the simulated sample size.

`--refresh-data` deliberately replaces the saved 2015–2025 input files with the current version from the original source. It is never run automatically. Because source histories can be revised, retain the data record when comparing research versions.

## Files to read

- [Findings](DECISION_BRIEF.md): the main results and their implications.
- [Full methods](METHODOLOGY.md): definitions, formulas, costs, dates and study limits.
- [Execution notebook](../../notebooks/trading_performance_diagnostics.ipynb) and [risk notebook](../../notebooks/portfolio_risk_crowding.ipynb).
- [Order and monitoring calculations](execution.py), [SQL accounting](sql/diagnostics.sql), and [portfolio calculations](portfolio.py).
- [Input validation](data.py), [alternative-setting comparisons](robustness.py), and [tests](tests/test_research.py).

Saved results are in `results/execution/` and `results/portfolio/`. Website text and layout are maintained in `research/portfolio_site.py`, and chart formatting in `reports.py` and `research/site_figures.py`. These files rebuild the public pages without replacing the saved numerical results.

## Source and interpretation

The [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) supplies the daily industry and market-factor returns. Underlying data remain copyright Eugene F. Fama and Kenneth R. French. The saved 2015–2025 subset was downloaded on 25 October 2026 from the August 2026 source version. The file hashes and source details are recorded in `data/strategist_lab/manifest.json`; hashes check that the input files have not changed.

The historical inputs contain revisions and do not recreate the exact information available at each past date. The example portfolios are industry research exposures, not directly tradable products. The studies do not establish real venue superiority, a profitable live strategy, external-fund crowding or trading capacity. No employer or client data are used.

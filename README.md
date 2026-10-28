# Afsar Sharif — equity market research

Code and results for [my research portfolio](https://afsar20.github.io/AfsarSharifProjects.github.io/).

| Study | Question | Data |
|---|---|---|
| [Execution costs and trading results](https://afsar20.github.io/AfsarSharifProjects.github.io/projects/trading-performance.html) | Did results weaken because of execution costs or the trading forecast? | 100,000 simulated orders |
| [Portfolio risk and allocation](https://afsar20.github.io/AfsarSharifProjects.github.io/projects/portfolio-risk.html) | How does dividing money differently change risk, losses and return? | Public industry returns and example portfolios |
| [US equity market activity](https://afsar20.github.io/AfsarSharifProjects.github.io/projects/us-equities.html) | Where was trading reported, and what changed on busy days? | Cboe daily US market totals for 2025 |
| [SPY option volatility](https://afsar20.github.io/AfsarSharifProjects.github.io/projects/volatility-surface.html) | How does model-implied volatility vary with option strike and expiry? | A saved Interactive Brokers market-data sample |

Each page explains the results, defines the terms used, and describes what the evidence can and cannot establish. Detailed formulas and numerical checks remain available in the code and methods files.

## Rebuild the website

The page text and shared layout are in `research/portfolio_site.py`. The two stylesheets are in `assets/css/`. To rebuild all five pages and their charts from the saved results:

```bash
python -m pip install -r research/strategist_lab/requirements.txt
python -m research.portfolio_site
```

The market-summary inputs used by the website are saved in `research/site_data/`. The original Cboe study can download the full source file separately. Changing the presentation does not rerun the execution or portfolio simulations.

## Reproduce the execution and portfolio studies

```bash
python -m research.strategist_lab
python -m research.strategist_lab.robustness
python -m research.strategist_lab.reports
python -m unittest discover -s research/strategist_lab/tests -v
```

See the [research guide](research/strategist_lab/README.md), [findings](research/strategist_lab/DECISION_BRIEF.md) and [full methods](research/strategist_lab/METHODOLOGY.md). The tests cover accounting identities, input dates, allocation constraints and risk calculations.

## Reproduce the earlier studies

```bash
python -m pip install -r requirements.txt
python code/us_equities_liquidity.py
python code/volatility_surface/render_snapshot.py code/volatility_surface/spy_iv_snapshot_sample.csv
```

The US market [notebook](notebooks/us_equities_liquidity_intelligence.ipynb) downloads the source file on its first run. The options project includes a saved CSV for offline use; live collection requires Interactive Brokers trading software, API access and appropriate data subscriptions. No credentials are stored here.

## Data

The execution records are simulated. The risk study uses real French industry and factor returns with illustrative portfolios, financing and costs. The market-activity study uses public totals, and the options example uses a saved broker-data capture. The project pages identify the source, date and relevant limits. No employer or client records are included.

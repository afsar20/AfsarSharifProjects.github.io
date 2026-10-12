# Afsar Sharif — market structure portfolio

This repository powers [Afsar's project portfolio](https://afsar20.github.io/AfsarSharifProjects.github.io/) and contains two focused Python studies:

1. **US Equities Liquidity Intelligence** — public Cboe data used to analyse exchange versus off-exchange activity, tape-specific venue leadership, concentration on high-activity sessions and venue-share monitoring.
2. **SPY Implied-Volatility Surface** — an Interactive Brokers API workflow for collecting option implied volatility, saving repeatable snapshots and visualising the surface and front-expiry skew.

## Run the US equities study

Open `notebooks/us_equities_liquidity_intelligence.ipynb`. The notebook downloads the 2025 Cboe CSV on first run and caches it under `data/raw/cboe/`.

```bash
python -m pip install -r requirements.txt
jupyter lab
```

The compact script version can also be run from the repository root:

```bash
python code/us_equities_liquidity.py
```

## Run the saved volatility snapshot

```bash
python code/volatility_surface/render_snapshot.py \
  code/volatility_surface/spy_iv_snapshot_sample.csv
```

Live collection requires Interactive Brokers Trader Workstation or IB Gateway, API access and the appropriate market-data subscription. No credentials are stored in this repository.

## Data and limitations

- Cboe is the source for the US equity market-volume data. Cboe states that the historical files are based on UTDF and CTS consolidated feeds.
- The volatility example uses a saved SPY snapshot collected through the IBKR API.
- Both projects are research demonstrations using public or user-generated data. They do not contain employer or client data and are not trading recommendations.


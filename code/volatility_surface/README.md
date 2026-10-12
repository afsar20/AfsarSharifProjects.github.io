# SPY implied-volatility surface

This project captures a compact SPY option grid from the Interactive Brokers API and turns it into a three-dimensional implied-volatility surface with a front-expiry skew view.

## Files

- `live_surface.py` connects to Trader Workstation or IB Gateway, resolves the option chain, requests implied volatility and refreshes an interactive desktop chart.
- `snapshot_export.py` records repeated observations to CSV and Excel for reproducible offline work.
- `offline_surface.py` recreates the original saved-snapshot chart.
- `render_snapshot.py` creates the static chart used by the portfolio site.
- `spy_iv_snapshot_sample.csv` is a short saved capture used for the published example.

## Requirements

1. Interactive Brokers Trader Workstation or IB Gateway running locally.
2. API connections enabled on `127.0.0.1:7497` (the paper-trading default used in the example).
3. A market-data subscription that supplies the underlying and option calculations.
4. Python packages in the repository-level `requirements.txt`.

No Interactive Brokers username, password or API credential is placed in the code. The API session is authorised through the locally running Trader Workstation or Gateway.

## Method notes

The live example selects the next four expiries and up to nine strikes within roughly ±6% of spot. It requests puts below spot and calls at or above spot, then uses IBKR's model implied volatility. Missing grid values are interpolated only for visualisation; the surface is not a calibrated pricing model.


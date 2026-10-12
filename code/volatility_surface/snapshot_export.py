import time
import pandas as pd
from pathlib import Path

from live_surface import start_app

symbol = 'SPY'

capture_seconds = 30
capture_interval = 2

app = start_app(symbol)

print()
print("Connected. Waiting for IV data...")

timeout = time.time() + 30

while len(app.iv_dict) < 10 and time.time() < timeout:
    print(f"IV points available: {len(app.iv_dict)}")
    time.sleep(1)

if len(app.iv_dict) == 0:
    app.disconnect()
    raise RuntimeError("No implied volatility data received from IBKR.")

print()
print(f"Starting {capture_seconds} second capture...")

all_data = []
end_time = time.time() + capture_seconds

while time.time() < end_time:

    snapshot_time = pd.Timestamp.now(tz='Europe/London')

    for rid, iv in list(app.iv_dict.items()):

        if rid not in app.id_map:
            continue

        option_info = app.id_map[rid]

        exp = option_info[0]
        strike = option_info[1]
        right = option_info[2] if len(option_info) > 2 else ''

        all_data.append({
            'snapshot_time': snapshot_time.isoformat(),
            'symbol': symbol,
            'spot': app.spot_price,
            'expiration': exp,
            'strike': float(strike),
            'right': right,
            'iv': float(iv)
        })

    print(f"{snapshot_time.strftime('%H:%M:%S')} | IV points captured: {len(app.iv_dict)}")
    time.sleep(capture_interval)

app.disconnect()

df = pd.DataFrame(all_data)

if df.empty:
    raise RuntimeError("No data was captured.")

df = df.sort_values(['snapshot_time', 'expiration', 'strike']).reset_index(drop=True)

save_dir = Path.home() / "Documents" / "Volatility Surface"
save_dir.mkdir(parents=True, exist_ok=True)

timestamp = time.strftime('%Y%m%d_%H%M%S')

excel_file = save_dir / f'{symbol.lower()}_iv_snapshot_{timestamp}.xlsx'
csv_file = save_dir / f'{symbol.lower()}_iv_snapshot_{timestamp}.csv'

df.to_excel(excel_file, index=False)
df.to_csv(csv_file, index=False)

print()
print(df.head())
print()
print(f"Rows saved: {len(df)}")
print(f"Excel file: {excel_file}")
print(f"CSV file:   {csv_file}")
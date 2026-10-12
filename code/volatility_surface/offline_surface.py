import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

plt.style.use('dark_background')

base_dir = Path(__file__).resolve().parent
file_path = Path(sys.argv[1]) if len(sys.argv) > 1 else base_dir / 'spy_iv_snapshot_20260904_165949.xlsx'

df = pd.read_excel(file_path)

required_columns = ['spot', 'expiration', 'strike', 'iv']

missing_columns = [column for column in required_columns if column not in df.columns]

if len(missing_columns) > 0:
    raise ValueError(f"Missing columns: {missing_columns}")


df['strike'] = pd.to_numeric(df['strike'])
df['iv'] = pd.to_numeric(df['iv'])
df['expiration'] = df['expiration'].astype(str)


if 'snapshot_time' in df.columns:

    latest_snapshot = df['snapshot_time'].max()

    surface_data = df[
        df['snapshot_time'] == latest_snapshot
    ].copy()

else:

    latest_snapshot = 'Saved Snapshot'
    surface_data = df.copy()


surface_data = surface_data.dropna(
    subset=['expiration', 'strike', 'iv']
)


spot = float(
    surface_data['spot'].dropna().iloc[0]
)


if 'symbol' in surface_data.columns:

    symbol = surface_data['symbol'].dropna().iloc[0]

else:

    symbol = 'SPY'


pivot = surface_data.pivot_table(
    index='expiration',
    columns='strike',
    values='iv'
)

pivot = pivot.sort_index().sort_index(axis=1)

pivot = pivot.interpolate(
    method='linear',
    axis=1,
    limit_direction='both'
)

pivot = pivot.bfill(axis=1).ffill(axis=1)

pivot = pivot.interpolate(
    method='linear',
    axis=0,
    limit_direction='both'
)

pivot = pivot.bfill(axis=0).ffill(axis=0)


if pivot.shape[0] < 2 or pivot.shape[1] < 3:
    raise RuntimeError("Not enough IV observations to construct the surface.")


X, Y_idx = np.meshgrid(
    pivot.columns.astype(float),
    np.arange(len(pivot.index))
)

Z = pivot.values * 100


fig = plt.figure(figsize=(16, 9))

fig.canvas.manager.set_window_title(
    'Saved Implied Volatility Surface'
)

fig.patch.set_facecolor('#0b0d0f')


ax_3d = plt.subplot2grid(
    (1, 3),
    (0, 0),
    colspan=2,
    projection='3d'
)

ax_skew = plt.subplot2grid(
    (1, 3),
    (0, 2)
)


ax_3d.set_facecolor('#0b0d0f')

ax_3d.plot_surface(
    X,
    Y_idx,
    Z,
    cmap='magma',
    edgecolor='white',
    lw=0.1,
    alpha=0.9
)

ax_3d.set_xlabel('Strike')
ax_3d.set_ylabel('Expiration')
ax_3d.set_zlabel('Implied Volatility (%)')

ax_3d.set_yticks(
    np.arange(len(pivot.index))
)

ax_3d.set_yticklabels(
    pivot.index
)

ax_3d.set_title(
    f'{symbol} Implied Volatility Surface - Saved Snapshot',
    color='white'
)


nearest_exp = pivot.index[0]

skew_data = pivot.iloc[0] * 100


ax_skew.set_facecolor('#161b22')

ax_skew.plot(
    skew_data.index.astype(float),
    skew_data.values,
    marker='o',
    color='#00f2ff'
)

ax_skew.axvline(
    x=spot,
    color='#ff3e3e',
    linestyle='--',
    label=f'Spot {spot:.2f}'
)

ax_skew.set_title(
    f'Front Month Skew ({nearest_exp})',
    color='white'
)

ax_skew.set_xlabel('Strike')
ax_skew.set_ylabel('Implied Volatility (%)')

ax_skew.grid(alpha=0.15)
ax_skew.legend()


plt.tight_layout()
plt.show()
"""Render a saved SPY implied-volatility snapshot for the portfolio page."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"spot", "expiration", "strike", "iv"}


def load_latest_snapshot(path: Path) -> tuple[pd.DataFrame, float, str, str]:
    """Load and validate the latest observation in a CSV or Excel capture."""

    if path.suffix.lower() == ".csv":
        data = pd.read_csv(path)
    else:
        data = pd.read_excel(path)

    missing = sorted(REQUIRED_COLUMNS.difference(data.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if "snapshot_time" in data:
        latest_time = data["snapshot_time"].max()
        data = data.loc[data["snapshot_time"].eq(latest_time)].copy()
    else:
        latest_time = "Saved snapshot"

    data["expiration"] = pd.to_datetime(data["expiration"].astype(str), format="%Y%m%d")
    data["strike"] = pd.to_numeric(data["strike"], errors="raise")
    data["iv"] = pd.to_numeric(data["iv"], errors="raise")
    data = data.dropna(subset=["expiration", "strike", "iv"])

    spot = float(data["spot"].dropna().iloc[0])
    symbol = str(data.get("symbol", pd.Series(["SPY"])).dropna().iloc[0])
    return data, spot, symbol, str(latest_time)


def build_surface(data: pd.DataFrame) -> pd.DataFrame:
    """Pivot observed IV points and interpolate gaps for visualisation only."""

    surface = data.pivot_table(index="expiration", columns="strike", values="iv")
    surface = surface.sort_index().sort_index(axis=1)
    surface = surface.interpolate(axis=1, limit_direction="both").bfill(axis=1).ffill(axis=1)
    surface = surface.interpolate(axis=0, limit_direction="both").bfill(axis=0).ffill(axis=0)
    if surface.shape[0] < 2 or surface.shape[1] < 3:
        raise ValueError("At least two expiries and three strikes are required.")
    return surface


def render(path: Path, output: Path) -> None:
    data, spot, symbol, latest_time = load_latest_snapshot(path)
    surface = build_surface(data)

    strikes, expiry_index = np.meshgrid(
        surface.columns.to_numpy(dtype=float), np.arange(len(surface.index))
    )
    iv_percent = surface.to_numpy() * 100

    figure = plt.figure(figsize=(14, 7.5), facecolor="#07111f")
    grid = figure.add_gridspec(1, 3, width_ratios=[2.15, 0.06, 1], wspace=0.18)
    axis_3d = figure.add_subplot(grid[0, 0], projection="3d")
    axis_skew = figure.add_subplot(grid[0, 2])

    axis_3d.set_facecolor("#07111f")
    axis_3d.plot_surface(
        strikes,
        expiry_index,
        iv_percent,
        cmap="magma",
        edgecolor="white",
        linewidth=0.15,
        antialiased=True,
        alpha=0.94,
    )
    axis_3d.set_xlabel("Strike", labelpad=10)
    axis_3d.set_ylabel("Expiry", labelpad=12)
    axis_3d.set_zlabel("Implied volatility (%)", labelpad=9)
    axis_3d.set_yticks(np.arange(len(surface.index)))
    axis_3d.set_yticklabels([value.strftime("%d %b") for value in surface.index])
    axis_3d.set_title(
        f"{symbol} implied-volatility surface",
        loc="left",
        pad=18,
        weight="bold",
        color="white",
    )
    axis_3d.view_init(elev=27, azim=-60)

    front = surface.iloc[0] * 100
    axis_skew.set_facecolor("#0d1b2a")
    axis_skew.plot(front.index, front.values, color="#2dd4bf", marker="o", linewidth=2.1)
    axis_skew.axvline(spot, color="#f28e5b", linestyle="--", linewidth=1.5, label=f"Spot {spot:.2f}")
    axis_skew.set_title(
        f"Front-expiry skew\n{surface.index[0].strftime('%d %b %Y')}",
        loc="left",
        weight="bold",
        color="white",
    )
    axis_skew.set_xlabel("Strike")
    axis_skew.set_ylabel("Implied volatility (%)")
    axis_skew.grid(alpha=0.16)
    legend = axis_skew.legend(frameon=False)
    plt.setp(legend.get_texts(), color="#d9e2ec")

    for axis in [axis_3d, axis_skew]:
        axis.tick_params(colors="#d9e2ec")
        axis.xaxis.label.set_color("#d9e2ec")
        axis.yaxis.label.set_color("#d9e2ec")
    axis_3d.zaxis.label.set_color("#d9e2ec")

    figure.text(
        0.015,
        0.02,
        f"Latest capture: {latest_time}  |  Interpolation is for display, not pricing.",
        color="#9fb3c8",
        fontsize=9,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path, default=Path("assets/images/volatility_surface.png"))
    args = parser.parse_args()
    render(args.snapshot, args.output)


if __name__ == "__main__":
    main()

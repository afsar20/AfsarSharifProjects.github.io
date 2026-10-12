"""Compact US equity liquidity-intelligence study using Cboe market-volume data.

The analysis is intentionally based on public daily aggregates. It describes the
market landscape and produces monitoring signals; it does not claim to measure
order-level execution quality, latency, price improvement or causality.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
import numpy as np
import pandas as pd
import seaborn as sns


BASE_URL = (
    "https://cdn.cboe.com/resources/us/equities/"
    "market-statistics/historical-market-volume"
)

VENUE_CLASSIFICATION = {
    "24X National Exchange (G)": "Exchange",
    "BYX Equities (Y)": "Exchange",
    "BZX Equities (Z)": "Exchange",
    "EDGA Equities (J)": "Exchange",
    "EDGX Equities (K)": "Exchange",
    "Investors Exchange (V)": "Exchange",
    "LTSE (L)": "Exchange",
    "MIAX Pearl (H)": "Exchange",
    "Members Exchange (U)": "Exchange",
    "NASDAQ (Q)": "Exchange",
    "NASDAQ BX (B)": "Exchange",
    "NASDAQ PSX (X)": "Exchange",
    "NYSE (N)": "Exchange",
    "NYSE American (A)": "Exchange",
    "NYSE Arca (P)": "Exchange",
    "NYSE National (C)": "Exchange",
    "NYSE Texas (M)": "Exchange",
    "FINRA / NYSE TRF (DN)": "Off-exchange (TRF)",
    "FINRA / Nasdaq TRF Carteret (DQ)": "Off-exchange (TRF)",
    "FINRA / Nasdaq TRF Chicago (DB)": "Off-exchange (TRF)",
}

REQUIRED_COLUMNS = {
    "Day",
    "Market Participant",
    "Tape A Notional",
    "Tape B Notional",
    "Tape C Notional",
    "Total Notional",
    "Total Shares",
    "Total Trade Count",
}


def download_cboe_volume(year: int, destination: Path) -> Path:
    """Download and cache one year of Cboe US equity market-volume data."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return destination

    url = f"{BASE_URL}/market_history_{year}.csv"
    pd.read_csv(url).to_csv(destination, index=False)
    return destination


def load_and_validate(path: Path) -> pd.DataFrame:
    """Load the source and fail visibly when the schema or venue map changes."""

    data = pd.read_csv(path, parse_dates=["Day"])

    missing_columns = sorted(REQUIRED_COLUMNS.difference(data.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    if data.duplicated(["Day", "Market Participant"]).any():
        raise ValueError("Duplicate Day / Market Participant rows found.")

    unmapped = sorted(set(data["Market Participant"]) - set(VENUE_CLASSIFICATION))
    if unmapped:
        raise ValueError(
            "Update VENUE_CLASSIFICATION before continuing. "
            f"Unmapped participants: {unmapped}"
        )

    tape_total = data[
        ["Tape A Notional", "Tape B Notional", "Tape C Notional"]
    ].sum(axis=1)
    if not np.allclose(tape_total, data["Total Notional"], rtol=1e-10, atol=0.05):
        raise ValueError("Tape notionals do not reconcile to Total Notional.")

    data = data.copy()
    data["Venue Type"] = data["Market Participant"].map(VENUE_CLASSIFICATION)
    return data.sort_values(["Day", "Market Participant"]).reset_index(drop=True)


def build_metrics(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return daily market metrics and daily on-exchange venue shares."""

    venue_type = data.pivot_table(
        index="Day",
        columns="Venue Type",
        values="Total Notional",
        aggfunc="sum",
        fill_value=0,
    ).sort_index()

    venue_type["Total Notional"] = venue_type.sum(axis=1)
    venue_type["Off-exchange share"] = (
        venue_type["Off-exchange (TRF)"] / venue_type["Total Notional"]
    )
    venue_type["Off-exchange share (20D)"] = (
        venue_type["Off-exchange share"].rolling(20, min_periods=10).mean()
    )

    exchange_notional = data.loc[data["Venue Type"].eq("Exchange")].pivot_table(
        index="Day",
        columns="Market Participant",
        values="Total Notional",
        aggfunc="sum",
        fill_value=0,
    ).sort_index()
    exchange_share = exchange_notional.div(exchange_notional.sum(axis=1), axis=0)

    venue_type["Exchange HHI"] = exchange_share.pow(2).sum(axis=1) * 10_000
    venue_type["Effective venue count"] = 10_000 / venue_type["Exchange HHI"]
    return venue_type, exchange_share


def annual_tape_share(data: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    """Calculate each exchange's annual share within Tape A, B and C."""

    exchange = data.loc[data["Venue Type"].eq("Exchange")]
    tape_columns = ["Tape A Notional", "Tape B Notional", "Tape C Notional"]
    tape = exchange.groupby("Market Participant")[tape_columns].sum()
    tape = tape.div(tape.sum(axis=0), axis=1)
    tape.columns = ["Tape A", "Tape B", "Tape C"]

    leaders = tape.sum(axis=1).nlargest(top_n).index
    display = tape.loc[leaders].copy()
    display.loc["Other exchanges"] = tape.drop(leaders).sum()
    return display


def quarterly_share_change(exchange_share: pd.DataFrame) -> pd.DataFrame:
    """Compare average daily on-exchange share in Q4 with Q1."""

    quarterly = exchange_share.groupby(exchange_share.index.to_period("Q")).mean().T
    output = pd.DataFrame(
        {
            "Q1 share": quarterly[pd.Period("2025Q1")],
            "Q4 share": quarterly[pd.Period("2025Q4")],
        }
    )
    output["Change (pp)"] = (output["Q4 share"] - output["Q1 share"]) * 100
    return output.sort_values("Change (pp)")


def latest_share_monitor(exchange_share: pd.DataFrame) -> pd.DataFrame:
    """Create a trailing baseline monitor for the latest observation."""

    long = exchange_share.stack().rename("Daily share").reset_index()
    long = long.sort_values(["Market Participant", "Day"])
    grouped = long.groupby("Market Participant")["Daily share"]
    long["Prior 20D mean"] = grouped.transform(
        lambda values: values.shift(1).rolling(20, min_periods=15).mean()
    )
    long["Prior 20D volatility"] = grouped.transform(
        lambda values: values.shift(1).rolling(20, min_periods=15).std()
    )
    long["Change (pp)"] = (long["Daily share"] - long["Prior 20D mean"]) * 100
    long["z-score"] = (
        (long["Daily share"] - long["Prior 20D mean"])
        / long["Prior 20D volatility"]
    )

    latest = long.loc[long["Day"].eq(long["Day"].max())].copy()
    return latest.sort_values("Change (pp)", key=lambda values: values.abs(), ascending=False)


def bootstrap_regime_difference(
    daily: pd.DataFrame,
    column: str,
    n_boot: int = 20_000,
    seed: int = 7,
) -> tuple[float, float, float]:
    """Bootstrap the top-decile minus other-days mean difference."""

    high_volume = daily["Total Notional"] >= daily["Total Notional"].quantile(0.90)
    high = daily.loc[high_volume, column].to_numpy()
    other = daily.loc[~high_volume, column].to_numpy()

    rng = np.random.default_rng(seed)
    differences = np.empty(n_boot)
    for index in range(n_boot):
        differences[index] = (
            rng.choice(high, size=len(high), replace=True).mean()
            - rng.choice(other, size=len(other), replace=True).mean()
        )

    estimate = high.mean() - other.mean()
    lower, upper = np.quantile(differences, [0.025, 0.975])
    return float(estimate), float(lower), float(upper)


def save_figures(
    data: pd.DataFrame,
    daily: pd.DataFrame,
    exchange_share: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Save the four figures used in the notebook and portfolio page."""

    output_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="talk")
    navy, teal, orange, grey = "#12263A", "#0E8A83", "#F28E5B", "#8492A6"

    figure, axes = plt.subplots(2, 1, figsize=(13, 9), sharex=True)
    axes[0].plot(daily.index, daily["Total Notional"] / 1e9, color=navy, linewidth=1.6)
    axes[0].fill_between(
        daily.index,
        daily["Total Notional"] / 1e9,
        color=navy,
        alpha=0.10,
    )
    axes[0].set_ylabel("Notional ($bn)")
    axes[0].set_title("US equity trading activity and off-exchange share, 2025", loc="left", weight="bold")

    axes[1].plot(
        daily.index,
        daily["Off-exchange share"],
        color=grey,
        linewidth=1.0,
        alpha=0.75,
        label="Daily",
    )
    axes[1].plot(
        daily.index,
        daily["Off-exchange share (20D)"],
        color=teal,
        linewidth=2.5,
        label="20-day average",
    )
    average_share = daily["Off-exchange share"].mean()
    axes[1].axhline(average_share, color=orange, linestyle="--", linewidth=1.8, label="2025 mean")
    axes[1].annotate(
        f"2025 mean: {average_share:.1%}",
        xy=(daily.index[-1], average_share),
        xytext=(-12, 10),
        textcoords="offset points",
        ha="right",
        color=orange,
        fontsize=11,
    )
    axes[1].yaxis.set_major_formatter(PercentFormatter(1.0))
    axes[1].set_ylabel("Off-exchange share")
    axes[1].legend(frameon=False, ncol=3, loc="lower left")
    axes[1].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    sns.despine(figure)
    figure.tight_layout()
    figure.savefig(output_dir / "us_market_overview.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    tape = annual_tape_share(data)
    figure, axis = plt.subplots(figsize=(10.5, 7.5))
    sns.heatmap(
        tape * 100,
        annot=True,
        fmt=".1f",
        cmap=sns.light_palette(teal, as_cmap=True),
        linewidths=0.7,
        linecolor="white",
        cbar_kws={"label": "Share of on-exchange notional (%)"},
        ax=axis,
    )
    axis.set_title("Venue leadership differs sharply by listing tape", loc="left", weight="bold", pad=16)
    axis.set_xlabel("")
    axis.set_ylabel("")
    figure.tight_layout()
    figure.savefig(output_dir / "us_tape_structure.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    high_volume = daily["Total Notional"] >= daily["Total Notional"].quantile(0.90)
    regime = pd.DataFrame(
        {
            "Session": np.where(high_volume, "Top-decile notional", "Other sessions"),
            "Off-exchange share": daily["Off-exchange share"],
            "Exchange HHI": daily["Exchange HHI"],
        },
        index=daily.index,
    )
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    order = ["Other sessions", "Top-decile notional"]
    sns.boxplot(data=regime, x="Session", y="Off-exchange share", order=order, color=teal, width=0.55, ax=axes[0])
    sns.stripplot(data=regime, x="Session", y="Off-exchange share", order=order, color=navy, alpha=0.35, size=3, ax=axes[0])
    axes[0].yaxis.set_major_formatter(PercentFormatter(1.0))
    axes[0].set_xlabel("")
    axes[0].set_title("Off-exchange share", weight="bold")

    sns.boxplot(data=regime, x="Session", y="Exchange HHI", order=order, color=orange, width=0.55, ax=axes[1])
    sns.stripplot(data=regime, x="Session", y="Exchange HHI", order=order, color=navy, alpha=0.35, size=3, ax=axes[1])
    axes[1].set_xlabel("")
    axes[1].set_title("On-exchange concentration", weight="bold")
    figure.suptitle("High-activity sessions shift the liquidity mix", x=0.06, ha="left", weight="bold")
    sns.despine(figure)
    figure.tight_layout()
    figure.savefig(output_dir / "us_activity_regimes.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    changes = quarterly_share_change(exchange_share)
    material = pd.concat([changes.head(5), changes.tail(5)]).sort_values("Change (pp)")
    colors = [orange if value < 0 else teal for value in material["Change (pp)"]]
    figure, axis = plt.subplots(figsize=(10.5, 6.5))
    axis.barh(material.index, material["Change (pp)"], color=colors)
    axis.axvline(0, color=navy, linewidth=1)
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:+.1f} pp"))
    axis.set_xlabel("Change in average daily on-exchange share")
    axis.set_ylabel("")
    axis.set_title("Largest venue-share changes: Q4 versus Q1 2025", loc="left", weight="bold")
    sns.despine(figure, left=True)
    figure.tight_layout()
    figure.savefig(output_dir / "us_share_shifts.png", dpi=180, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--data", type=Path, default=Path("data/raw/market_history_2025.csv"))
    parser.add_argument("--figures", type=Path, default=Path("assets/images"))
    args = parser.parse_args()

    source = download_cboe_volume(args.year, args.data)
    data = load_and_validate(source)
    daily, exchange_share = build_metrics(data)
    save_figures(data, daily, exchange_share, args.figures)

    off_exchange = daily["Off-exchange share"].mean()
    annual_exchange = (
        data.loc[data["Venue Type"].eq("Exchange")]
        .groupby("Market Participant")["Total Notional"]
        .sum()
        .sort_values(ascending=False)
    )
    top_three = annual_exchange.head(3).sum() / annual_exchange.sum()
    estimate, lower, upper = bootstrap_regime_difference(daily, "Off-exchange share")

    print(f"Validated {len(data):,} rows across {data['Day'].nunique()} trading days.")
    print(f"Average off-exchange notional share: {off_exchange:.2%}")
    print(f"Top-three exchange share of on-exchange notional: {top_three:.2%}")
    print(
        "Top-decile activity difference in off-exchange share: "
        f"{estimate * 100:+.2f} pp (bootstrap 95% CI {lower * 100:+.2f}, {upper * 100:+.2f})"
    )


if __name__ == "__main__":
    main()

"""Download, freeze and validate public daily research returns.

Only the first (value weighted) industry-return table is used. Source percentages
are converted to decimals exactly once. Missing-value sentinels are rejected.
The frozen subset has a SHA-256 manifest; default runs never download anything.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd

from . import DATA

SOURCES = {
    "industries": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/10_Industry_Portfolios_daily_CSV.zip",
    "factors": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
}
FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
INDUSTRIES = ["NoDur", "Durbl", "Manuf", "Enrgy", "HiTec", "Telcm", "Shops", "Hlth", "Utils", "Other"]


def parse_french(text: str, start="2015-01-01", end="2025-12-31") -> pd.DataFrame:
    """Parse the first daily table; stop before an equal-weighted second table."""
    lines = text.splitlines()
    header = next((i for i, line in enumerate(lines) if line.startswith(",")),None)
    if header is None:
        raise ValueError("Daily table header was not found")
    rows = []
    for line in lines[header + 1:]:
        if re.match(r"^\s*\d{8},", line):
            rows.append(line)
        elif rows:
            break
    if not rows:
        raise ValueError("No daily observations in source")
    frame = pd.read_csv(io.StringIO(lines[header] + "\n" + "\n".join(rows)), index_col=0)
    frame.index = pd.to_datetime(frame.index.astype(str), format="%Y%m%d")
    frame.index.name = "date"
    frame.columns = frame.columns.str.strip()
    if frame.isin([-99.99, -999]).any().any():
        # The full early history can contain missing industry observations.
        frame = frame.replace({-99.99: np.nan, -999: np.nan})
    frame = frame.loc[start:end] / 100.0
    validate_returns(frame)
    return frame


def validate_returns(frame: pd.DataFrame) -> None:
    if frame.empty or not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError("Dates must be non-empty, unique and increasing")
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Missing or non-finite return; no forward filling is permitted")
    if (frame.abs() >= 1).any().any():
        raise ValueError("Return outside (-1,1); check percentage/decimal units")


def freeze_sources(cache: Path | None = None) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    metadata = {"retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "start": "2015-01-01", "end": "2025-12-31",
                "units": "daily decimal total returns; factors are zero-investment returns except RF",
                "revision_note": "Latest revised public files, not a point-in-time historical database.",
                "copyright": "Underlying source data: Eugene F. Fama and Kenneth R. French.",
                "sources": {}}
    for name, url in SOURCES.items():
        raw = (cache / f"{name}.raw").read_bytes() if cache else urlopen(url, timeout=45).read()
        archive = zipfile.ZipFile(io.BytesIO(raw))
        source_text = archive.read(archive.namelist()[0]).decode("utf-8-sig")
        frame = parse_french(source_text)
        path = DATA / f"{name}.csv"
        frame.to_csv(path, float_format="%.6f", date_format="%Y-%m-%d")
        metadata["sources"][name] = {
            "url": url, "source_header": source_text.splitlines()[0],
            "archive_sha256": hashlib.sha256(raw).hexdigest(),
            "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rows": len(frame), "columns": list(frame.columns)}
    (DATA / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    load_data()
    return metadata


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = json.loads((DATA / "manifest.json").read_text())
    frames = []
    for name, cols in [("industries", INDUSTRIES), ("factors", FACTORS + ["RF"])]:
        path = DATA / f"{name}.csv"
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sources"][name]["csv_sha256"]:
            raise ValueError(f"Frozen {name} data failed its SHA-256 check")
        frame = pd.read_csv(path, index_col=0, parse_dates=True)
        validate_returns(frame)
        if list(frame.columns) != cols:
            raise ValueError(f"Unexpected {name} schema")
        frames.append(frame)
    if not frames[0].index.equals(frames[1].index):
        raise ValueError("Industry and factor calendars differ")
    return frames[0], frames[1]

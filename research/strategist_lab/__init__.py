"""Trading diagnostics and portfolio risk research, with explicit data provenance."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "strategist_lab"
OUTPUT = ROOT / "research" / "strategist_lab" / "results"

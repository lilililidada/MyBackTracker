"""Runtime configuration objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


@dataclass(frozen=True)
class BacktestConfig:
    """Backtest configuration."""

    symbol: str = "600519"
    start: str = "20200101"
    end: str = "20251231"
    adjust: str = "qfq"
    data_source: Literal["akshare", "csv", "tickflow"] = "akshare"
    csv: Optional[Path] = None
    cash: float = 100_000.0
    commission: float = 0.0003
    stake: int = 100
    fast_period: int = 20
    slow_period: int = 60
    report: Path = Path("reports/phase1_quantstats.html")
    benchmark: Optional[str] = None
    skip_report: bool = False

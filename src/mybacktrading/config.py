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
    # --- 策略选择 ---
    strategy: str = "sma_cross"  # "sma_cross" | "etf_trend"

    # --- ETF 趋势跟踪策略参数 ---
    ma_period: int = 30
    buy_pullback_pct: float = 0.1
    buy_cash_pct: float = 0.50
    tp_mode: Literal["none", "trailing", "partial", "atr"] = "none"
    tp_trail_pct: float = 0.05
    tp_partial_1_pct: float = 0.05
    tp_partial_1_ratio: float = 0.33
    tp_partial_2_pct: float = 0.10
    tp_partial_2_ratio: float = 0.33
    tp_partial_3_pct: float = 0.15
    tp_partial_3_ratio: float = 0.34
    tp_atr_multiple: float = 3.0
    tp_atr_period: int = 14

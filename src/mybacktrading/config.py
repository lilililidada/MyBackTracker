"""Runtime configuration objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class BacktestConfig:
    """回测参数配置。

    Attributes:
        symbol: A 股代码，例如 "600519"。
        start: 回测开始日期，格式 YYYYMMDD。
        end: 回测结束日期，格式 YYYYMMDD。
        adjust: 复权方式，"qfq" 为前复权。
        csv: 可选本地 OHLCV CSV 路径，用于外汇或自有数据。
        cash: 初始资金。
        commission: 交易佣金率，0.0003 表示万分之三。
        stake: 每次下单数量，A 股通常为 100 的整数倍。
        fast_period: 快速均线周期。
        slow_period: 慢速均线周期。
        report: QuantStats HTML 报告路径。
        benchmark: 可选 QuantStats 基准代码。
        skip_report: 是否跳过 QuantStats 报告生成，常用于 CI 或排查依赖问题。
    """

    symbol: str = "600519"
    start: str = "20200101"
    end: str = "20251231"
    adjust: str = "qfq"
    csv: Optional[Path] = None
    cash: float = 100_000.0
    commission: float = 0.0003
    stake: int = 100
    fast_period: int = 20
    slow_period: int = 60
    report: Path = Path("reports/phase1_quantstats.html")
    benchmark: Optional[str] = None
    skip_report: bool = False

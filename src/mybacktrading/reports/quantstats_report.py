"""QuantStats report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def returns_to_series(timereturn_analysis: dict) -> pd.Series:
    """将 Backtrader TimeReturn 字典转换为 QuantStats 可识别的 Series。"""
    returns = pd.Series(timereturn_analysis, name="strategy_return")
    returns.index = pd.to_datetime(returns.index)
    returns = returns.sort_index().astype(float)
    returns = returns.replace([float("inf"), float("-inf")], pd.NA).dropna()
    return returns


def generate_quantstats_report(
    returns: pd.Series,
    output_path: Path,
    title: str,
    benchmark: Optional[str] = None,
) -> None:
    """生成 QuantStats HTML 报告。"""
    import quantstats as qs

    output_path.parent.mkdir(parents=True, exist_ok=True)
    qs.extend_pandas()
    qs.reports.html(
        returns,
        benchmark=benchmark,
        output=str(output_path),
        title=title,
    )

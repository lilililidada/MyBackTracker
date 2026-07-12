"""Market data download and cleaning."""

from __future__ import annotations

from pathlib import Path

import akshare as ak
import pandas as pd


BACKTRADER_COLUMNS = ["open", "high", "low", "close", "volume", "openinterest"]


def fetch_akshare_stock_daily(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """下载并清洗 A 股日线数据。

    Args:
        symbol: A 股股票代码，例如 "600519"。
        start_date: 开始日期，格式为 YYYYMMDD。
        end_date: 结束日期，格式为 YYYYMMDD。
        adjust: 复权方式，"qfq" 表示前复权，"hfq" 表示后复权，"" 表示不复权。

    Returns:
        满足 bt.feeds.PandasData 标准格式的 DataFrame。
    """
    raw = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )

    if raw.empty:
        raise ValueError(f"AKShare 未返回数据: symbol={symbol}, {start_date}-{end_date}")

    column_map = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }
    data = raw.rename(columns=column_map)
    return clean_ohlcv_dataframe(data)


def load_csv_ohlcv(csv_path: Path) -> pd.DataFrame:
    """加载通用 OHLCV CSV，方便未来接入外汇、期货或自有数据。

    CSV 至少需要包含:
    date, open, high, low, close, volume
    """
    data = pd.read_csv(csv_path)
    data.columns = [col.strip().lower() for col in data.columns]
    return clean_ohlcv_dataframe(data)


def clean_ohlcv_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """清洗 OHLCV 数据为 Backtrader PandasData 标准结构。"""
    required_columns = ["date", "open", "high", "low", "close", "volume"]
    missing_columns = [col for col in required_columns if col not in data.columns]
    if missing_columns:
        raise KeyError(f"行情数据字段缺失: {missing_columns}")

    cleaned = data[required_columns].copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"])
    cleaned["openinterest"] = 0

    cleaned[BACKTRADER_COLUMNS] = cleaned[BACKTRADER_COLUMNS].apply(pd.to_numeric, errors="coerce")
    cleaned = cleaned.dropna(subset=["open", "high", "low", "close"])
    cleaned = cleaned.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    cleaned = cleaned.set_index("date")

    return cleaned[BACKTRADER_COLUMNS]

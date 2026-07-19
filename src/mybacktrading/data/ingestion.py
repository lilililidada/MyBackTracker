"""Market data download and cleaning."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd

from mybacktrading.data.tickflow_adapter import fetch_a_stock_history_daily

BACKTRADER_COLUMNS = ["open", "high", "low", "close", "volume", "openinterest"]


def fetch_akshare_stock_daily(
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
) -> pd.DataFrame:
    """下载并清洗 A 股日线数据。"""
    if ak is None:
        raise ImportError("akshare is required for fetch_akshare_stock_daily()")

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

def fetch_etf_minute_data(
    symbol: str,
    period: str = "1",
    adjust: str = "qfq",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    获取 ETF 分钟级别行情数据（东方财富数据源）

    参数:
        symbol (str): ETF代码，需带市场前缀，如 "sh510300"（沪市）或 "sz159919"（深市）
        period (str): 分钟周期，可选值: "1", "5", "15", "30", "60"，默认 "1"
        adjust (str): 复权方式，"qfq" 前复权 / "hfq" 后复权，默认 "qfq"
        start_date (str, optional): 开始日期，格式 "YYYY-MM-DD"，如 "2025-01-01"
        end_date (str, optional): 结束日期，格式 "YYYY-MM-DD"，如 "2025-12-31"

    返回:
        pd.DataFrame: 包含以下字段的分钟线数据
            - 时间: 分钟时间戳
            - 开盘价 / 收盘价 / 最高价 / 最低价
            - 成交量 / 成交额

    示例:
        # 获取沪深300ETF（510300）的1分钟数据
        df = get_etf_minute_data("sh510300", period="1")
        print(df.head())

        # 获取指定日期范围的5分钟数据
        df = get_etf_minute_data(
            symbol="sh510300",
            period="5",
            start_date="2026-07-01",
            end_date="2026-07-19"
        )
    """
    try:
        df = ak.fund_etf_hist_min_em(
            symbol=symbol,
            period=period,
            adjust=adjust,
            start_date=start_date,
            end_date=end_date
        )
        return df
    except Exception as e:
        print(f"获取ETF分钟数据失败: {e}")
        return pd.DataFrame()

class TickFlowDataSource:

    def __init__(self):
        super().__init__()

    def get_a_stock_history_daily(self, symbol: str, start_date: str, end_date: str, adjust: str = "none") -> pd.DataFrame:
        df = fetch_a_stock_history_daily(symbol, start_date, end_date, adjust)
        return self._clean_ohlcv_dataframe(df)

    def get_a_stock_history_minute(self):
        pass

    def _clean_ohlcv_dataframe(self, data: pd.DataFrame) -> pd.DataFrame:
        required_columns = ["trade_time", "open", "high", "low", "close", "volume", "amount"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise KeyError(f"行情数据字段缺失: {missing_columns}")

        cleaned: pd.DataFrame = data[required_columns].copy()
        cleaned.rename(columns={"trade_time": "date"}, inplace=True)
        cleaned["date"] = pd.to_datetime(cleaned["date"])
        cleaned["openinterest"] = 0

        cleaned[BACKTRADER_COLUMNS] = cleaned[BACKTRADER_COLUMNS].apply(pd.to_numeric, errors="coerce")

        return cleaned


def load_csv_ohlcv(csv_path: Path) -> pd.DataFrame:
    """加载通用 OHLCV CSV，适用于外汇、期货或自有数据。"""
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

if __name__ == '__main__':
    df = fetch_etf_minute_data("588170", "1", "", "2026-07-17 08:30:00", "2026-07-17 16:32:00")
    print(df.tail())

"""Market data download and cleaning."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd
from sympy import false

from mybacktrading.data.db.csv_file_db import save_min_data_as_csv
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



def fetch_benchmark_data(benchmark: str, start_date: str, end_date: str):
    """TODO: 自行实现基准指数行情获取，返回含 close 列的 DataFrame。
    """
    raise NotImplementedError(
        f"请实现 fetch_benchmark_data(benchmark={benchmark!r}, ...) 以获取基准行情。"
    )


if __name__ == '__main__':
    tf = TickFlowDataSource()
    df = tf.get_a_stock_history_daily("588170", "2020-07-17 08:30:00", "2026-09-17 16:32:00", "forward")
    df.to_csv("588170_1.csv", index=false)

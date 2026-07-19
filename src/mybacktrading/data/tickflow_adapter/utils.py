import re
from datetime import datetime, timezone
import os

import pandas as pd
from dotenv import load_dotenv
from tickflow import TickFlow

from mybacktrading.data.tickflow_adapter.stock_identification import get_stock_exchange

load_dotenv()

api_key = os.getenv("TICK_FLOW_API_KEY")
tf = TickFlow(api_key=api_key)

exchange_map = {
    "SSE": "SH",
    "SZSE": "SZ",
    "BSE": "BJ",
}


def fetch_a_stock_history_daily(
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "none",
) -> pd.DataFrame:
    start_timestamp = day_time_str_to_timestamp(start_date)
    end_timestamp = day_time_str_to_timestamp(end_date)
    return tf.klines.get(symbol=f"{symbol}.{get_stock_suffix(symbol)}",
                         period="1d",
                         count=10000,
                         start_time=start_timestamp,
                         end_time=end_timestamp,
                         adjust=adjust,
                         as_dataframe=True)


def fetch_a_stock_history_minute(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    start_timestamp = day_time_str_to_timestamp(start_date)
    end_timestamp = day_time_str_to_timestamp(end_date)
    return tf.klines.get(symbol=f"{symbol}.{get_stock_suffix(symbol)}",
                         period="1m",
                         count=10000,
                         start_time=start_timestamp,
                         end_time=end_timestamp,
                         adjust="none",
                         as_dataframe=True)


def day_time_str_to_timestamp(day_time_str: str, utc: bool = False) -> int:
    # 尝试完整格式，失败则用日期格式（默认时间为 00:00:00）
    try:
        dt = datetime.strptime(day_time_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        dt = datetime.strptime(day_time_str, "%Y-%m-%d")

    if utc:
        # 将 naive datetime 设置为 UTC
        dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    else:
        # naive datetime 被当作本地时间，timestamp() 会自动转换
        return int(dt.timestamp() * 1000)


def get_stock_suffix(code: str) -> str:
    """
    判断股票代码所属交易所

    Args:
        code (str): 股票代码

    Returns:
        str: 'SH' (上交所), 'SZ' (深交所), 'BJ' (北交所),
             'Unknown' (无法识别), 'Invalid' (无效输入)
    """
    t = get_stock_exchange(code)
    return exchange_map[t[0]]


if __name__ == '__main__':
    cases = ["589020", "588170"]
    df = fetch_a_stock_history_minute(cases[0], "2026-07-17 08:30:00", "2026-07-17 16:32:00")
    print(df.tail())

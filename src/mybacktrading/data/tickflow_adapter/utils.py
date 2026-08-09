import math
import os
import re
from datetime import datetime, timedelta, timezone
from time import sleep

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

MAX_KLINE_COUNT_PER_REQUEST = 10000
TRADING_DAYS_PER_YEAR = 262


def _estimate_daily_bar_count(start_date: str, end_date: str) -> int:
    """按 262 个交易日/年估算区间内的日线数量。"""
    start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
    end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
    calendar_days = max((end_dt - start_dt).days + 1, 1)
    return math.ceil(calendar_days * TRADING_DAYS_PER_YEAR / 365)


def _split_date_range(start_date: str, end_date: str):
    """按估算的 10000 条上限把日期区间拆成多个子区间。"""
    start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
    end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
    calendar_days = max((end_dt - start_dt).days + 1, 1)
    estimated_count = _estimate_daily_bar_count(start_date, end_date)
    batch_count = math.ceil(estimated_count / MAX_KLINE_COUNT_PER_REQUEST)
    batch_days = math.ceil(calendar_days / batch_count)

    ranges = []
    chunk_start = start_dt
    while chunk_start <= end_dt:
        chunk_end = min(chunk_start + timedelta(days=batch_days - 1), end_dt)
        ranges.append((
            chunk_start.strftime("%Y-%m-%d 00:00:00"),
            chunk_end.strftime("%Y-%m-%d 23:59:59"),
        ))
        chunk_start = chunk_end + timedelta(days=1)
    return ranges


def fetch_a_stock_history_daily(
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "none",
) -> pd.DataFrame:
    symbol_full = f"{symbol}.{get_stock_suffix(symbol)}"

    def fetch_chunk(start_ts: int, end_ts: int) -> pd.DataFrame:
        return tf.klines.get(symbol=symbol_full,
                             period="1d",
                             count=MAX_KLINE_COUNT_PER_REQUEST,
                             start_time=start_ts,
                             end_time=end_ts,
                             adjust=adjust,
                             as_dataframe=True)

    start_timestamp = day_time_str_to_timestamp(start_date)
    end_timestamp = day_time_str_to_timestamp(end_date)
    if _estimate_daily_bar_count(start_date, end_date) <= MAX_KLINE_COUNT_PER_REQUEST:
        return fetch_chunk(start_timestamp, end_timestamp)

    ranges = _split_date_range(start_date, end_date)
    frames = []
    for index, (range_start, range_end) in enumerate(ranges):
        chunk_start = start_date if index == 0 else range_start
        chunk_end = end_date if index == len(ranges) - 1 else range_end
        sleep(0.5)  # 避免请求过快导致被限制
        frames.append(fetch_chunk(
            day_time_str_to_timestamp(chunk_start),
            day_time_str_to_timestamp(chunk_end),
        ))
    return pd.concat(frames, ignore_index=True)


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

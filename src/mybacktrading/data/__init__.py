"""Data ingestion helpers."""
import pandas as pd

from mybacktrading.data.ingestion import TickFlowDataSource, fetch_benchmark_data

stock_data_source = TickFlowDataSource()

def fetch_a_stock_history_daily(symbol: str, start_date: str, end_date: str, adjust: str = "none") -> pd.DataFrame:
    return stock_data_source.get_a_stock_history_daily(symbol, start_date, end_date, adjust)

__all__ = [
    "fetch_a_stock_history_daily",
    "fetch_benchmark_data",
]
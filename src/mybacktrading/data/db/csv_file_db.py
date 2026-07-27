import os

import pandas as pd

base_dir = os.path.join(os.path.dirname(__file__), "csv_data")

def save_min_data_as_csv(df: pd.DataFrame, symbol: str, date: str, period: str):
    csv_dir = os.path.join(base_dir, symbol, date, period + "m")
    os.makedirs(csv_dir, exist_ok=True)
    df.to_csv(os.path.join(csv_dir, f"{symbol}_{date}.csv"), index=False)

def load_min_data_from_csv(symbol: str, date: str, period: str) -> pd.DataFrame:
    csv_dir = os.path.join(base_dir, symbol, date, period + "m")
    return pd.read_csv(os.path.join(csv_dir, f"{symbol}_{date}.csv"))

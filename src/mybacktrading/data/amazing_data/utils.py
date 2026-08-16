import os
import re
from dataclasses import dataclass
from typing import List, Dict

import AmazingData as ad
import dotenv
import pandas as pd
from AmazingData.utils.convert import Period

dotenv.load_dotenv()

username = os.getenv('AMZ_DATA_USERNAME')
password = os.getenv('AMZ_DATA_PASSWORD')
host_ip = os.getenv('AMZ_DATA_IP')
port = os.getenv('AMZ_DATA_PORT')
local_data_path = os.getenv('AMZ_LOCAL_DATA_PATH')

ad.login(username=username, password=password, host=host_ip, port=int(port))
base_data_instance = ad.BaseData()
calendar = base_data_instance.get_calendar()


def fetch_a_stock_history_daily(symbol: str, start_date: str, end_date: str, adjust: bool = True) -> pd.DataFrame:
    """
    获取股票或ETF 日线数据

    @param: symbol: stock symbol
    @param: start_date: start date
    @param: end_date: end date
    @param: adjust: 是否使用后复权
    @return: dataframe
    """
    # 检查 start_date and end_date 是否符合 "20200131" 的日期格式，不符合则抛出异常
    if not re.fullmatch(r"[0-9]{8}", start_date) or not re.fullmatch(r"[0-9]{8}", end_date):
        raise ValueError("start_date and end_date 必须符合 YYYYMMDD 格式，例如 20200131")

    # 调用AmazingData获取股票原始数据(未经过复权)
    market_data_instance = ad.MarketData(calendar)
    kline_dict = market_data_instance.query_kline([symbol], begin_date=int(start_date), end_date=int(end_date),
                                                  period=Period.day.value)
    if kline_dict[symbol].empty:
        raise ValueError(f"未获取到 {symbol} 的日线数据，请检查日期范围或股票代码是否正确。")
    kline: pd.DataFrame = kline_dict[symbol]

    if not adjust:
        return kline

    adjust_factor = get_back_adjusted_factor(symbol)
    factor = adjust_factor[symbol].copy()
    factor.index = pd.to_datetime(factor.index)

    kline_time = pd.to_datetime(kline["kline_time"])
    missing_dates = kline_time[~kline_time.isin(factor.index)]
    if not missing_dates.empty:
        raise ValueError(f"复权因子缺少 {symbol} 以下日期的数据: {missing_dates.dt.strftime('%Y-%m-%d').tolist()}")

    factor_values = factor.loc[kline_time.to_numpy()].to_numpy()
    kline["adjust_factor"] = factor_values

    # 调整价格
    kline.loc[:, ["open", "high", "low", "close"]] = kline.loc[:, ["open", "high", "low", "close"]].mul(factor_values,
                                                                                                        axis=0).round(3)
    # 调整成交量
    kline["volume"] = kline["volume"].div(factor_values, axis=0).round()

    kline.rename(columns={"kline_time": "date"}, inplace=True)
    return kline.reset_index(drop=True)


def get_back_adjusted_factor(symbol: str) -> pd.DataFrame:
    """
    获取后复权因子
    """
    save_dir = os.path.join(local_data_path, "back_adjust_factor", symbol) + '/'
    return base_data_instance.get_backward_factor(code_list=[symbol], local_path=save_dir, is_local=True)


def get_history_code_list(security_type: str, start_date: str, end_date: str) -> List[str]:
    """
    获取历史股票或ETF代码列表
    """
    save_dir = os.path.join(local_data_path, "history_code_list", security_type) + '/'
    data = base_data_instance.get_hist_code_list(security_type, start_date=int(start_date), end_date=int(end_date),
                                                 local_path=save_dir)
    return data


def get_etf_fund_nav(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取etf基金净值数据

    """
    info_data_object = ad.InfoData()
    fund_nav = info_data_object.get_fund_nav([symbol], is_local=True, local_path=local_data_path,
                                             begin_date=int(start_date), end_date=int(end_date))
    return fund_nav[symbol]


def get_a_stock_snapshot(symbol: str, begin_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
    market_data_object = ad.MarketData(calendar)
    snapshot_dict = market_data_object.query_snapshot([symbol], begin_date=int(begin_date), end_date=int(end_date))
    result = {}
    for key, value in snapshot_dict.items():
        result[str(key)] = value[symbol]
    return result


@dataclass
class StockStatusInfo:
    # 日期
    date: str

    # 前收价
    preclose: float

    # 涨停价
    high_limited: float

    # 跌停价
    low_limited: float

    # 涨停上限比率
    price_high_limited: float

    # 跌停下限比率
    price_low_limited: float

    # 是否ST
    is_st_sec: bool

    # 是否停牌
    is_suspend_sec: bool

    # 是否除息
    is_wd_sec: bool

    # 是否除权
    is_xr_sec: bool


def get_stock_history_status_info(symbol: str, begin_date: str, end_date: str) -> pd.DataFrame:
    info_data_object = ad.InfoData()
    stock_info = info_data_object.get_history_etf_status([symbol], is_local=False,
                                              local_path=local_data_path,
                                              begin_date=int(begin_date),
                                              end_date=int(end_date))
    return stock_info


if __name__ == '__main__':
    symbol = "501018.SH"
    result = get_etf_fund_nav(symbol, "20260804", "20260804")
    print(len(result))

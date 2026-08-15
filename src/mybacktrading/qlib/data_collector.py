import os
from datetime import datetime
from time import sleep

from mybacktrading.qlib.data_source import data_source

save_dir = os.path.join(os.getcwd(), "csv_data")
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

default_start_date = "20000101"


def download_a_stock_history_daily_data(symbols: list):
    """
    下载股票或ETF数据
    @param: symbols: 股票或ETF代码列表
    """
    now_date_time = datetime.now().strftime("%Y%m%d")

    target_dir = os.path.join(save_dir, "daily")
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    for symbol in symbols:
        kline_data = data_source.fetch_a_stock_history_daily(symbol, start_date=default_start_date,
                                                             end_date=now_date_time)

        # 存储数据到本地的csv文件
        code, exchange = symbol.split('.')
        kline_data.to_csv(os.path.join(target_dir, f"{exchange}{code}.csv"), index=False)
        sleep(0.5)  # 避免请求过快，防止被封IP

def convert_csv_date_to_qlib_bin():
    """
    将下载的csv数据转换为qlib可用的bin格式
    """



if __name__ == '__main__':
    etf_symbols = ["518880.SH"]
    download_a_stock_history_daily_data(etf_symbols)

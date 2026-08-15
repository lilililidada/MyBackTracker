import abc
import re

import mybacktrading.data.amazing_data.utils as amz_utils


class DataSource(abc.ABC):
    _DAILY_QUERY_RULES = (
        ("symbol", re.compile(r"^\d{6}\.(SH|SZ|BJ)$"), "6 位数字 + .SH/.SZ/.BJ，例如 588170.SH"),
        ("start_date", re.compile(r"^\d{8}$"), "YYYYMMDD，例如 20200101"),
        ("end_date", re.compile(r"^\d{8}$"), "YYYYMMDD，例如 20200131"),
    )

    @abc.abstractmethod
    def fetch_a_stock_history_daily(self, symbol: str, start_date: str, end_date: str):
        """
        从各种数据源获取数据
        :param symbol: 股票代码 如 588170.SH
        :param start_date: 开始日期 如 20200101
        :param end_date: 结束日期 如 20200131
        """
        pass

    def _validate_daily_query(self, symbol: str, start_date: str, end_date: str) -> None:
        values = {"symbol": symbol, "start_date": start_date, "end_date": end_date}
        for name, pattern, expected in self._DAILY_QUERY_RULES:
            value = values[name]
            if not isinstance(value, str) or not pattern.fullmatch(value):
                raise ValueError(f"参数 {name} 格式不正确，应为 {expected}，实际为 {value!r}")


class AmazonDataSource(DataSource):
    def fetch_a_stock_history_daily(self, symbol: str, start_date: str, end_date: str):
        self._validate_daily_query(symbol, start_date, end_date)
        kline_data = amz_utils.fetch_a_stock_history_daily(symbol, start_date, end_date, adjust=True)
        kline_data.rename(columns={"code": "symbol"}, inplace=True)
        kline_data.rename(columns={"adjust_factor": "factor"}, inplace=True)

        code, exchange = symbol.split('.')
        kline_data["symbol"] = exchange + code
        return kline_data


data_source = AmazonDataSource()

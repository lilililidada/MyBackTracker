"""Simple moving average crossover strategy."""

from __future__ import annotations

import backtrader as bt


class SmaCrossStrategy(bt.Strategy):
    """极简双均线策略模板。

    设计约定:
    - __init__ 只初始化指标，不写交易条件。
    - next 按事件驱动方式逐根 K 线处理交易逻辑。
    """

    params = (
        ("fast_period", 20),
        ("slow_period", 60),
        ("print_log", True),
    )

    def __init__(self) -> None:
        self.close_price = self.datas[0].close
        self.fast_sma = bt.indicators.SimpleMovingAverage(
            self.close_price,
            period=self.p.fast_period,
        )
        self.slow_sma = bt.indicators.SimpleMovingAverage(
            self.close_price,
            period=self.p.slow_period,
        )
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)

    def log(self, action: str, price: float) -> None:
        """打印交易日志，包含交易日期、动作、价格。"""
        if not self.p.print_log:
            return
        trade_date = self.datas[0].datetime.date(0).isoformat()
        print(f"{trade_date} | {action:<8} | price={price:.2f}")

    def next(self) -> None:
        """逐根 K 线触发的事件驱动交易逻辑。"""
        current_close = float(self.close_price[0])

        if not self.position:
            if self.crossover[0] > 0:
                self.log("BUY", current_close)
                self.buy()
            return

        if self.crossover[0] < 0:
            self.log("CLOSE", current_close)
            self.sell()

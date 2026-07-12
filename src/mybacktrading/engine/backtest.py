"""Backtrader Cerebro wiring and execution."""

from __future__ import annotations

import backtrader as bt
import pandas as pd

from mybacktrading.config import BacktestConfig
from mybacktrading.data import fetch_akshare_stock_daily, load_csv_ohlcv
from mybacktrading.reports.quantstats_report import generate_quantstats_report, returns_to_series
from mybacktrading.strategies import SmaCrossStrategy


def build_cerebro(
    data: pd.DataFrame,
    cash: float,
    commission: float,
    fast_period: int,
    slow_period: int,
    stake: int,
) -> bt.Cerebro:
    """创建并配置 Backtrader 回测引擎。"""
    cerebro = bt.Cerebro()

    feed = bt.feeds.PandasData(
        dataname=data,
        datetime=None,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest="openinterest",
    )
    cerebro.adddata(feed)

    cerebro.addstrategy(
        SmaCrossStrategy,
        fast_period=fast_period,
        slow_period=slow_period,
    )

    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=commission)
    cerebro.addsizer(bt.sizers.FixedSize, stake=stake)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn", timeframe=bt.TimeFrame.Days)

    return cerebro


def run_backtest(config: BacktestConfig) -> None:
    """执行完整回测流程。"""
    if config.csv:
        data = load_csv_ohlcv(config.csv)
        asset_name = config.csv.stem
    else:
        data = fetch_akshare_stock_daily(
            symbol=config.symbol,
            start_date=config.start,
            end_date=config.end,
            adjust=config.adjust,
        )
        asset_name = config.symbol

    if len(data) < config.slow_period + 5:
        raise ValueError("数据长度不足，无法稳定计算慢速均线，请扩大日期范围或降低 slow_period。")

    cerebro = build_cerebro(
        data=data,
        cash=config.cash,
        commission=config.commission,
        fast_period=config.fast_period,
        slow_period=config.slow_period,
        stake=config.stake,
    )

    start_value = cerebro.broker.getvalue()
    print(f"初始资金: {start_value:,.2f}")

    results = cerebro.run()
    strategy = results[0]

    end_value = cerebro.broker.getvalue()
    total_return = end_value / start_value - 1
    print(f"结束资金: {end_value:,.2f}")
    print(f"总收益率: {total_return:.2%}")

    returns = returns_to_series(strategy.analyzers.timereturn.get_analysis())
    if returns.empty:
        raise ValueError("TimeReturn 未生成收益率序列，无法生成 QuantStats 报告。")

    if config.skip_report:
        print("已跳过 QuantStats 报告生成。")
        return

    generate_quantstats_report(
        returns=returns,
        output_path=config.report,
        title=f"{asset_name} SMA Cross Backtest",
        benchmark=config.benchmark,
    )
    print(f"QuantStats 报告已生成: {config.report.resolve()}")

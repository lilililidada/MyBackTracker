"""Backtrader Cerebro wiring and execution."""

from __future__ import annotations

import backtrader as bt
import pandas as pd

from mybacktrading.config import BacktestConfig
from mybacktrading.data import (
    fetch_a_stock_history_daily,
)
from mybacktrading.engine.analyzers import print_full_analysis, SortinoRatio, CalmarRatio, MaxDrawdownRecovery
from mybacktrading.reports.quantstats_report import generate_quantstats_report, returns_to_series
from mybacktrading.strategies import SmaCrossStrategy, ETFTrendStrategy


def build_cerebro(
    data: pd.DataFrame,
    config: BacktestConfig,
) -> bt.Cerebro:
    """Create and configure a Backtrader engine."""
    cerebro = bt.Cerebro()

    feed = bt.feeds.PandasData(
        dataname=data,
        datetime=0,
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest="openinterest",
    )
    cerebro.adddata(feed)

    if config.strategy == "sma_cross":
        cerebro.addstrategy(
            SmaCrossStrategy,
            fast_period=config.fast_period,
            slow_period=config.slow_period,
        )
        cerebro.addsizer(bt.sizers.FixedSize, stake=config.stake)
    elif config.strategy == "etf_trend":
        cerebro.addstrategy(
            ETFTrendStrategy,
            ma_period=config.ma_period,
            buy_pullback_pct=config.buy_pullback_pct,
            buy_cash_pct=config.buy_cash_pct,
            tp_mode=config.tp_mode,
            tp_trail_pct=config.tp_trail_pct,
            tp_partial_1_pct=config.tp_partial_1_pct,
            tp_partial_1_ratio=config.tp_partial_1_ratio,
            tp_partial_2_pct=config.tp_partial_2_pct,
            tp_partial_2_ratio=config.tp_partial_2_ratio,
            tp_partial_3_pct=config.tp_partial_3_pct,
            tp_partial_3_ratio=config.tp_partial_3_ratio,
            tp_atr_multiple=config.tp_atr_multiple,
            tp_atr_period=config.tp_atr_period,
        )
    else:
        raise ValueError(f"Unknown strategy: {config.strategy}")

    cerebro.broker.setcash(config.cash)
    cerebro.broker.setcommission(commission=config.commission)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn", timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns", tann=252)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe",
                         timeframe=bt.TimeFrame.Days, annualize=True, riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="tradeanalyzer")
    cerebro.addanalyzer(SortinoRatio, _name="sortino", riskfreerate=0.02, annualization=252)
    cerebro.addanalyzer(CalmarRatio, _name="calmar", annualization=252)
    cerebro.addanalyzer(MaxDrawdownRecovery, _name="maxrecovery")

    cerebro.broker.set_slippage_fixed(0.02)

    return cerebro


def run_backtest(config: BacktestConfig) -> None:
    """执行完整回测流程。"""
    data = fetch_a_stock_history_daily(
        symbol=config.symbol,
        start_date=config.start,
        end_date=config.end,
        adjust=config.adjust,
    )
    asset_name = config.symbol

    # 根据策略确定所需最小数据长度
    if config.strategy == "sma_cross":
        min_bars = config.slow_period + 5
    elif config.strategy == "etf_trend":
        min_bars = config.ma_period + 5
    else:
        min_bars = 50  # 安全兜底
    if len(data) < min_bars:
        raise ValueError(
            f"数据长度不足 ({len(data)} < {min_bars})，无法稳定计算均线，"
            f"请扩大日期范围或降低对应均线周期。"
        )

    cerebro = build_cerebro(
        data=data,
        config=config,
    )

    start_value = cerebro.broker.getvalue()
    print(f"初始资金: {start_value:,.2f}")

    results = cerebro.run()
    strategy = results[0]

    end_value = cerebro.broker.getvalue()
    total_return = end_value / start_value - 1
    print(f"结束资金: {end_value:,.2f}")
    print(f"总收益率: {total_return:.2%}")

    # 计算买入持有收益率
    first_close = float(data["close"].iloc[0])
    last_close = float(data["close"].iloc[-1])
    buy_hold_return = (last_close - first_close) / first_close if first_close > 0 else 0.0

    # 尝试获取基准数据
    benchmark_return = None
    if config.benchmark:
        try:
            from mybacktrading.data.ingestion import fetch_benchmark_data
            bench_df = fetch_benchmark_data(config.benchmark, config.start, config.end)
            bf = float(bench_df["close"].iloc[0])
            bl = float(bench_df["close"].iloc[-1])
            benchmark_return = (bl - bf) / bf if bf > 0 else 0.0
        except NotImplementedError:
            print("基准行情桩方法未实现，跳过基准指标。")
        except Exception as e:
            print(f"获取基准行情失败: {e}，跳过基准指标。")

    print_full_analysis(results, buy_hold_return=buy_hold_return, benchmark_return=benchmark_return)

    returns = returns_to_series(strategy.analyzers.timereturn.get_analysis())
    if returns.empty:
        raise ValueError("TimeReturn 未生成收益率序列，无法生成 QuantStats 报告。")

    cerebro.plot(style="bar")


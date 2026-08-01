"""Command line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from mybacktrading.config import BacktestConfig
from mybacktrading.engine import run_backtest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtrader + AKShare + QuantStats modular starter")
    parser.add_argument("--symbol", default="510630", help="A 股代码会ETF，例如 600519")
    parser.add_argument("--start", default="2026-05-01", help="开始日期，格式 YYYY-MM-DD")
    parser.add_argument("--end", default="2026-07-28", help="结束日期，格式 YYYY-MM-DD")
    parser.add_argument("--adjust", default="forward", choices=["qfq", "hfq", ""], help="复权方式")
    parser.add_argument("--csv", default="", help="可选: 本地 OHLCV CSV 文件")
    parser.add_argument("--cash", type=float, default=10_000_000.0, help="初始资金")
    parser.add_argument("--commission", type=float, default=0.0003, help="交易佣金费率")
    parser.add_argument("--stake", type=int, default=500, help="每次下单股数")
    parser.add_argument("--fast-period", type=int, default=12, help="快速均线周期")
    parser.add_argument("--slow-period", type=int, default=20, help="慢速均线周期")
    parser.add_argument("--report", default="reports/phase1_quantstats.html", help="QuantStats HTML 输出路径")
    parser.add_argument("--benchmark", default=None, help="可选 QuantStats 基准，例如 SPY")
    parser.add_argument("--skip-report", action="store_true", help="跳过 QuantStats HTML 生成，仅运行回测")
    # --- 策略选择 ---
    parser.add_argument("--strategy", default="etf_trend",
                        choices=["sma_cross", "etf_trend"],
                        help="策略名称 (sma_cross | etf_trend)")

    # --- ETF 趋势跟踪策略参数 ---
    parser.add_argument("--ma-period", type=int, default=30, help="均线周期")
    parser.add_argument("--buy-pullback-pct", type=float, default=0.1, help="回撤加仓阈值")
    parser.add_argument("--buy-cash-pct", type=float, default=0.50, help="每次买入可用资金比例")
    parser.add_argument("--tp-mode", default="trailing",
                        choices=["none", "trailing", "partial", "atr"],
                        help="止盈模式")
    parser.add_argument("--tp-trail-pct", type=float, default=0.05, help="移动止盈回撤阈值")
    parser.add_argument("--tp-partial-1-pct", type=float, default=0.05, help="分批止盈第一档涨幅")
    parser.add_argument("--tp-partial-1-ratio", type=float, default=0.33, help="分批止盈第一档卖出比例")
    parser.add_argument("--tp-partial-2-pct", type=float, default=0.10, help="分批止盈第二档涨幅")
    parser.add_argument("--tp-partial-2-ratio", type=float, default=0.33, help="分批止盈第二档卖出比例")
    parser.add_argument("--tp-partial-3-pct", type=float, default=0.15, help="分批止盈第三档涨幅")
    parser.add_argument("--tp-partial-3-ratio", type=float, default=0.34, help="分批止盈第三档卖出比例")
    parser.add_argument("--tp-atr-multiple", type=float, default=3.0, help="ATR止盈倍数")
    parser.add_argument("--tp-atr-period", type=int, default=14, help="ATR周期")
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> BacktestConfig:
    return BacktestConfig(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        csv=Path(args.csv) if args.csv else None,
        cash=args.cash,
        commission=args.commission,
        stake=args.stake,
        fast_period=args.fast_period,
        slow_period=args.slow_period,
        report=Path(args.report),
        benchmark=args.benchmark,
        skip_report=args.skip_report,
        strategy=args.strategy,
        ma_period=args.ma_period,
        buy_pullback_pct=args.buy_pullback_pct,
        buy_cash_pct=args.buy_cash_pct,
        tp_mode=args.tp_mode,
        tp_trail_pct=args.tp_trail_pct,
        tp_partial_1_pct=args.tp_partial_1_pct,
        tp_partial_1_ratio=args.tp_partial_1_ratio,
        tp_partial_2_pct=args.tp_partial_2_pct,
        tp_partial_2_ratio=args.tp_partial_2_ratio,
        tp_partial_3_pct=args.tp_partial_3_pct,
        tp_partial_3_ratio=args.tp_partial_3_ratio,
        tp_atr_multiple=args.tp_atr_multiple,
        tp_atr_period=args.tp_atr_period,
    )


def main() -> None:
    run_backtest(config_from_args(parse_args()))


if __name__ == "__main__":
    main()

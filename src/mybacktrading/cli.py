"""Command line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from mybacktrading.config import BacktestConfig
from mybacktrading.engine import run_backtest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtrader + AKShare + QuantStats modular starter")
    parser.add_argument("--symbol", default="600519", help="A 股代码，例如 600519")
    parser.add_argument("--start", default="2005-01-01", help="开始日期，格式 YYYY-MM-DD")
    parser.add_argument("--end", default="2025-12-31", help="结束日期，格式 YYYY-MM-DD")
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
    )


def main() -> None:
    run_backtest(config_from_args(parse_args()))


if __name__ == "__main__":
    main()

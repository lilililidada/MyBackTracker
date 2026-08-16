"""七星 ETF 动量轮动策略。

原聚宽策略的核心思路：
  1. 在跨资产 ETF 池中，用近 25 日对数价格的加权线性回归斜率计算年化收益；
  2. 用 R^2 作为趋势稳定性的权重，得分 = 年化收益 * R^2；
  3. 依次经过停牌、盈利保护、放量、短期动量、单日跌幅、得分区间、溢价率过滤；
  4. 持有得分最高的 holdings_num 只 ETF，等权配置；无候选时切换到防御 ETF。

本策略将 OHLCV 数据交给 Backtrader 的 data feed，每个 ETF 对应一个 feed；
feed 需要由引擎侧以 `name=ETF代码` 的方式添加。聚宽特有的快照、溢价率、
交易日历等数据通过少数抽象方法获取，后续由调用方补充实现。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import backtrader as bt
import numpy as np

from mybacktrading.data.amazing_data import utils

DEFAULT_ETF_POOL = (
    # 大宗商品 ETF
    "518880.SH",  # 黄金ETF
    "159980.SZ",  # 有色ETF
    "159985.SZ",  # 豆粕ETF
    "501018.SH",  # 南方原油
    "161226.SZ",  # 白银LOF
    "159981.SZ",  # 能源化工ETF
    # 国际 ETF
    "513100.SH",  # 纳指ETF
    "159509.SZ",  # 纳指科技ETF
    "513290.SH",  # 纳指生物ETF
    "513500.SH",  # 标普500ETF
    "159529.SZ",  # 标普消费
    "513400.SH",  # 道琼斯ETF
    "513520.SH",  # 日经225ETF
    "513030.SH",  # 德国30ETF
    "513080.SH",  # 法国ETF
    "513310.SH",  # 中韩半导体ETF
    "513730.SH",  # 东南亚ETF
    # 香港 ETF
    "159792.SZ",  # 港股互联网ETF
    "513130.SH",  # 恒生科技
    "513050.SH",  # 中概互联网ETF
    "159920.SZ",  # 恒生ETF
    "513690.SH",  # 港股红利
    # 指数 ETF
    "510300.SH",  # 沪深300ETF
    "510500.SH",  # 中证500ETF
    "510050.SH",  # 上证50ETF
    "510210.SH",  # 上证ETF
    "159915.SZ",  # 创业板ETF
    "588080.SH",  # 科创50
    "512100.SH",  # 中证1000ETF
    "563360.SH",  # A500-ETF
    "563300.SH",  # 中证2000ETF
    # 风格 ETF
    "512890.SH",  # 红利低波ETF
    "159967.SZ",  # 创业板成长ETF
    "512040.SH",  # 价值ETF
    "159201.SZ",  # 自由现金流ETF
    # 债券 ETF
    "511380.SH",  # 可转债ETF
    "511010.SH",  # 国债ETF
    "511220.SH",  # 城投债ETF
)


@dataclass(frozen=True)
class SecurityInfo:
    """聚宽 get_current_data() 中与本策略相关的快照字段。"""

    name: str
    paused: bool
    high_limit: float
    low_limit: float


class SevenStarStrategy(bt.Strategy):
    """七星 ETF 动量轮动策略的 Backtrader 实现。"""

    def __init__(
            self,
            etf_pool: Iterable[str] = DEFAULT_ETF_POOL,
            lookback_days: int = 25,
            holdings_num: int = 5,
            defensive_etf: str = "511880.SH",
            min_money: float = 5000,
            enable_profit_protection: bool = True,
            profit_protection_lookback: int = 1,
            profit_protection_threshold: float = 0.05,
            loss: float = 0.97,
            min_score_threshold: float = 0.0,
            max_score_threshold: float = 100.0,
            enable_volume_check: bool = True,
            volume_lookback: int = 5,
            volume_threshold: float = 2.0,
            volume_return_limit: float = 1.0,
            use_short_momentum_filter: bool = True,
            short_lookback_days: int = 10,
            short_momentum_threshold: float = 0.0,
            enable_premium_filter: bool = True,
            premium_threshold: float = 0.20,
            rebalance_tolerance: float = 0.05,
            lot_size: int = 100,
            print_log: bool = True,
    ) -> None:
        self.etf_pool = list(etf_pool)
        self.lookback_days = lookback_days
        self.holdings_num = holdings_num
        self.defensive_etf = defensive_etf
        self.min_money = min_money

        self.enable_profit_protection = enable_profit_protection
        self.profit_protection_lookback = profit_protection_lookback
        self.profit_protection_threshold = profit_protection_threshold

        self.loss = loss
        self.min_score_threshold = min_score_threshold
        self.max_score_threshold = max_score_threshold

        self.enable_volume_check = enable_volume_check
        self.volume_lookback = volume_lookback
        self.volume_threshold = volume_threshold
        self.volume_return_limit = volume_return_limit

        self.use_short_momentum_filter = use_short_momentum_filter
        self.short_lookback_days = short_lookback_days
        self.short_momentum_threshold = short_momentum_threshold

        self.enable_premium_filter = enable_premium_filter
        self.premium_threshold = premium_threshold

        self.rebalance_tolerance = rebalance_tolerance
        self.lot_size = lot_size
        self.print_log = print_log

        self.rankings_cache = {"date": None, "data": None}
        self.pending_orders = 0
        self._orders_requested = set()
        self._clock = self.datas[0] if self.datas else None

    def _get_data(self, security: str) -> bt.feeds.DataBase | None:
        """按 ETF 代码获取对应 feed，feed 缺失时返回 None。"""
        try:
            return self.getdatabyname(security)
        except KeyError:
            return None

    def log(self, action: str, price: float | None = None, extra: str = "") -> None:
        if not self.print_log:
            return
        if self._clock is None:
            trade_date = "?"
        else:
            trade_date = self._clock.datetime.date(0).isoformat()
        if price is None:
            msg = f"{trade_date} | {action}"
        else:
            msg = f"{trade_date} | {action:<18} | price={price:.4f}"
        if extra:
            msg += f" | {extra}"
        print(msg)

    # ------------------------------------------------------------------
    #  抽象数据接口，后续由调用方实现
    # ------------------------------------------------------------------

    def _get_security_info(self, security: str) -> SecurityInfo:
        """返回证券快照，对应聚宽 get_current_data()[security]。"""

        raise NotImplementedError(
            f"_get_security_info({security!r}) 未实现，"
            f"请返回 SecurityInfo(name, paused, high_limit, low_limit)"
        )

    def _get_premium_rate(
            self, security: str, date
    ) -> tuple[float | None, float | None, float | None]:
        """返回 (溢价率, 场内价, 基金净值)，对应聚宽 get_price + get_extras('unit_net_value')。"""
        raise NotImplementedError(
            f"_get_premium_rate({security!r}, {date!r}) 未实现"
        )

    def _get_previous_trade_date(self, date):
        """返回上一个交易日，对应聚宽 get_trade_days(end_date, count=2)[0]。"""
        raise NotImplementedError(
            f"_get_previous_trade_date({date!r}) 未实现"
        )

    def _update_etf_pool(self) -> None:
        """更新 ETF 池，对应聚宽 get_all_securities + finance.FUND_PORTFOLIO。

        原策略中该月度更新被注释掉，因此默认不接入交易流程。
        """
        raise NotImplementedError("_update_etf_pool() 未实现")

    # ------------------------------------------------------------------
    #  数据与仓位辅助
    # ------------------------------------------------------------------

    def _current_price(self, security: str) -> float:
        data = self._get_data(security)
        if data is None or len(data) < 1:
            return 0.0
        return float(data.close[0])

    def _position_size(self, security: str) -> int:
        data = self._get_data(security)
        if data is None:
            return 0
        return int(self.getposition(data).size)

    def _log_positions(self) -> None:
        for security in self.etf_pool + [self.defensive_etf]:
            size = self._position_size(security)
            if size > 0:
                self.log(
                    "HOLD",
                    self._current_price(security),
                    f"{security} size={size}",
                )

    # ------------------------------------------------------------------
    #  核心计算
    # ------------------------------------------------------------------

    def _get_cached_rankings(self) -> list[dict]:
        if self._clock is None:
            return []
        today = self._clock.datetime.date(0)
        if self.rankings_cache["date"] != today:
            self.log("RERANK_ETFS")
            self.rankings_cache = {"date": today, "data": self._get_ranked_etfs()}
        return self.rankings_cache["data"]

    def _get_ranked_etfs(self) -> list[dict]:
        metrics = []
        for security in self.etf_pool:
            data = self._get_data(security)
            if data is None:
                self.log("SKIP_NO_FEED", extra=security)
                continue
            if self._is_etf_suspend(security):
                self.log("SKIP_PAUSED", extra=security)
                continue
            result = self._calculate_momentum_metrics(security, data)
            if result is not None:
                if self.min_score_threshold < result["score"] < self.max_score_threshold:
                    metrics.append(result)
                else:
                    self.log(
                        "SKIP_SCORE",
                        extra=f"{security} score={result['score']:.4f}",
                    )

        metrics.sort(key=lambda item: item["score"], reverse=True)
        return metrics

    def _is_etf_suspend(self, symbol: str):
        pass

    def _calculate_momentum_metrics(
            self,
            security: str,
            data: bt.feeds.DataBase
    ) -> dict | None:
        try:
            lookback = max(self.lookback_days, self.short_lookback_days) + 20
            required = lookback + 1
            if len(data) < required:
                self.log("SKIP_SHORT_HISTORY", extra=f"{security} len={len(data)}")
                return None

            closes = np.asarray(data.close.get(size=required), dtype=float)
            current_price = float(closes[-1])
            price_series = closes

            if self._check_profit_protection(security):
                self.log("SKIP_PROFIT_PROTECTION", extra=security)
                return None

            if self.enable_volume_check:
                volume_ratio = self._get_volume_ratio(security, data)
                if volume_ratio is not None:
                    annualized = self._get_annualized_returns(
                        price_series, self.lookback_days
                    )
                    if annualized > self.volume_return_limit:
                        self.log(
                            "SKIP_VOLUME",
                            extra=f"{security} vol_ratio={volume_ratio:.1f}",
                        )
                        return None

            if len(price_series) >= self.short_lookback_days + 1:
                short_return = (
                        price_series[-1] / price_series[-(self.short_lookback_days + 1)] - 1
                )
                short_annualized = (
                        (1 + short_return) ** (250 / self.short_lookback_days) - 1
                )
            else:
                short_annualized = 0.0

            if (
                    self.use_short_momentum_filter
                    and short_annualized < self.short_momentum_threshold
            ):
                self.log("SKIP_SHORT_MOMENTUM", extra=security)
                return None

            recent = price_series[-(self.lookback_days + 1):]
            y = np.log(recent)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            annualized_returns = math.exp(slope * 250) - 1

            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
            score = annualized_returns * r_squared

            if len(price_series) >= 4:
                day1 = price_series[-1] / price_series[-2]
                day2 = price_series[-2] / price_series[-3]
                day3 = price_series[-3] / price_series[-4]
                if min(day1, day2, day3) < self.loss:
                    self.log("SKIP_DAILY_DROP", extra=security)
                    return None

            return {
                "etf": security,
                "etf_name": security,
                "annualized_returns": float(annualized_returns),
                "r_squared": float(r_squared),
                "score": float(score),
                "current_price": current_price,
                "short_annualized": float(short_annualized),
            }
        except NotImplementedError:
            raise
        except Exception as exc:
            self.log("METRICS_ERROR", extra=f"{security}: {exc}")
            return None

    def _get_annualized_returns(
            self, price_series: np.ndarray, lookback_days: int
    ) -> float:
        recent = price_series[-(lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, _ = np.polyfit(x, y, 1, w=weights)
        return math.exp(slope * 250) - 1

    def _get_volume_ratio(self, security: str, data: bt.feeds.DataBase) -> float | None:
        required = self.volume_lookback + 1
        if len(data) < required:
            return None
        volumes = np.asarray(data.volume.get(size=required), dtype=float)
        avg_volume = float(np.mean(volumes[:-1]))
        if avg_volume <= 0:
            return None
        ratio = float(volumes[-1]) / avg_volume
        if ratio > self.volume_threshold:
            self.log("VOLUME_ALERT", extra=f"{security} ratio={ratio:.2f}")
            return ratio
        return None

    def _check_profit_protection(
            self,
            security: str,
            lookback: int | None = None,
            threshold: float | None = None,
    ) -> bool:
        if not self.enable_profit_protection:
            return False
        lookback = lookback or self.profit_protection_lookback
        threshold = threshold if threshold is not None else self.profit_protection_threshold

        data = self._get_data(security)
        if data is None or len(data) < lookback + 1:
            return False
        highs = np.asarray(data.high.get(size=lookback + 1), dtype=float)[:-1]
        if len(highs) == 0:
            return False
        max_high = float(np.max(highs))
        current_price = float(data.close[0])
        if max_high <= 0:
            return False
        return current_price <= max_high * (1 - threshold)

    def _check_defensive_etf_available(self) -> bool:
        data = self._get_data(self.defensive_etf)
        if data is None:
            return False
        info = self._get_security_info(self.defensive_etf)
        price = self._current_price(self.defensive_etf)
        if info.paused:
            return False
        if price >= info.high_limit:
            return False
        if price <= info.low_limit:
            return False
        return True

    # ------------------------------------------------------------------
    #  交易流程
    # ------------------------------------------------------------------

    def _build_targets(self, ranked: list[dict]) -> list[str]:
        targets: list[str] = []
        previous_date = None
        if self.enable_premium_filter and self._clock is not None:
            previous_date = self._get_previous_trade_date(
                self._clock.datetime.date(0)
            )

        for metrics in ranked:
            if len(targets) >= self.holdings_num:
                break
            if metrics["score"] < self.min_score_threshold:
                continue

            security = metrics["etf"]
            if self.enable_profit_protection and self._check_profit_protection(security):
                self.log("SKIP_BUY_PROFIT_PROTECTION", extra=security)
                continue

            if self.enable_premium_filter:
                premium, _, _ = self._get_premium_rate(security, previous_date)
                if premium is None:
                    self.log("SKIP_PREMIUM_UNKNOWN", extra=security)
                    continue
                if premium > self.premium_threshold:
                    self.log(
                        "SKIP_PREMIUM_HIGH",
                        extra=f"{security} premium={premium:.2%}",
                    )
                    continue

            targets.append(security)

        if not targets and self._check_defensive_etf_available():
            targets = [self.defensive_etf]
        return targets

    def _sell_profit_protection(self) -> set[str]:
        triggered = set()
        if not self.enable_profit_protection:
            return triggered
        for security in self.etf_pool + [self.defensive_etf]:
            if security in self._orders_requested:
                continue
            if self._position_size(security) <= 0:
                continue
            if self._check_profit_protection(security):
                if self._order_target_value(security, 0.0):
                    triggered.add(security)
        return triggered

    def _sell_non_targets(self, target_set: set[str]) -> None:
        for security in self.etf_pool + [self.defensive_etf]:
            if security in self._orders_requested:
                continue
            if self._position_size(security) <= 0:
                continue
            if security not in target_set:
                self._order_target_value(security, 0.0)

    def _buy_targets(self, targets: list[str]) -> None:
        if not targets:
            return
        target_set = set(targets)
        current_positions = [
            security
            for security in self.etf_pool + [self.defensive_etf]
            if self._position_size(security) > 0
        ]
        to_sell = [security for security in current_positions if security not in target_set]
        if to_sell:
            self.log("WAIT_SELL", extra=", ".join(to_sell))
            return

        total_value = self.broker.getvalue()
        target_per_etf = total_value / len(targets)
        for security in targets:
            if security in self._orders_requested:
                continue
            price = self._current_price(security)
            current_value = self._position_size(security) * price
            if (
                    abs(current_value - target_per_etf) > target_per_etf * self.rebalance_tolerance
                    or current_value == 0
            ):
                self._order_target_value(security, target_per_etf)

    def _order_target_value(self, security: str, target_value: float) -> bool:
        data = self._get_data(security)
        if data is None:
            self.log("ORDER_NO_FEED", extra=security)
            return False

        price = self._current_price(security)
        if price == 0:
            self.log("ORDER_ZERO_PRICE", extra=security)
            return False

        info = self._get_security_info(security)
        if info.paused:
            self.log("ORDER_PAUSED", price, f"{security} {info.name}")
            return False

        target_amount = int(target_value / price)
        target_amount = (target_amount // self.lot_size) * self.lot_size
        if target_amount <= 0 and target_value > 0:
            target_amount = self.lot_size

        current_amount = self._position_size(security)
        diff = target_amount - current_amount
        if diff == 0:
            return False

        if diff > 0 and price >= info.high_limit:
            self.log("ORDER_LIMIT_UP", price, f"{security} {info.name}")
            return False
        if diff < 0 and price <= info.low_limit:
            self.log("ORDER_LIMIT_DOWN", price, f"{security} {info.name}")
            return False

        trade_value = abs(diff) * price
        if 0 < trade_value < self.min_money:
            self.log("ORDER_TOO_SMALL", price, f"{security} value={trade_value:.2f}")
            return False

        if diff > 0:
            self.buy(data=data, size=diff)
            self.log("BUY", price, f"{security} {info.name} size={diff}")
        else:
            self.sell(data=data, size=abs(diff))
            self.log("SELL", price, f"{security} {info.name} size={abs(diff)}")

        self._orders_requested.add(security)
        self.pending_orders += 1
        return True

    def notify_order(self, order: bt.Order) -> None:
        if order.status in (order.Completed, order.Canceled, order.Margin, order.Rejected):
            self.pending_orders = max(0, self.pending_orders - 1)
            if order.status == order.Completed:
                security = getattr(order.data, "_name", "?")
                self.log(
                    "FILL",
                    order.executed.price,
                    f"{security} size={order.executed.size}",
                )

    # ------------------------------------------------------------------
    #  Backtrader 入口
    # ------------------------------------------------------------------

    def next(self) -> None:
        if self._clock is None:
            return
        if self.pending_orders > 0:
            self.log("WAIT_PENDING_ORDERS")
            return

        self._orders_requested.clear()
        self._log_positions()

        ranked = self._get_cached_rankings()
        targets = self._build_targets(ranked)

        profit_protection_triggered = self._sell_profit_protection()
        targets = [security for security in targets if security not in profit_protection_triggered]

        self._sell_non_targets(set(targets))
        self._buy_targets(targets)


if __name__ == '__main__':
    codes = utils.get_history_code_list("EXTRA_ETF", "20250103", "20250103")
    codes = set(codes)
    print([code in codes for code in DEFAULT_ETF_POOL])

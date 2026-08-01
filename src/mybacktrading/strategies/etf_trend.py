"""
ETF 趋势跟踪策略 — 30日均线 + 回撤加仓 + 可选止盈

核心思想:
  1. 价格上穿 30 日均线 → 首次买入（第一买点）
  2. 价格在均线上方运行时，从持仓最高收盘价回撤 X% → 加仓买入
  3. 加仓方式：按当前可用资金的固定比例买入
  4. 加仓次数：不限制
  5. 价格下穿 30 日均线 → 清仓
  6. 支持四种止盈方案（通过 tp_mode 切换）

可切换的止盈方案:
  - none:     无止盈，纯趋势跟踪
  - trailing:  移动止盈，从持仓最高价回撤 Y% 时全部平仓
  - partial:   分批止盈，依次到达利润目标时按比例卖出
  - atr:       基于 ATR 的动态止盈，从最高价回撤 N × ATR 时平仓
"""

from __future__ import annotations

import backtrader as bt


class BuyManager:
    """买入操作管理器：处理首次买入和回撤加仓。"""

    def __init__(self, strategy: bt.Strategy) -> None:
        self.strategy = strategy

    def _calc_size(self, price: float) -> int:
        cash_to_use = self.strategy.broker.getcash() * self.strategy.p.buy_cash_pct
        size = int(cash_to_use / price)
        return (size // 100) * 100

    def try_first_buy(self, price: float, above_sma_days: int, sma_value: float) -> bool:
        if above_sma_days <= 5:
            return False
        size = self._calc_size(price)
        if size <= 0:
            return False
        self.strategy.log("BUY_FIRST", price, f"sma={sma_value:.4f}, size={size}sh")
        self.strategy.buy(size=size)
        return True

    def try_pullback_buy(self, price: float, sma_value: float, peak_price: float) -> bool:
        """均线上方且从最高价回撤超过阈值 → 加仓。返回是否执行了买入。"""
        if price <= sma_value or peak_price <= 0:
            return False
        drawdown = (peak_price - price) / peak_price
        if drawdown < self.strategy.p.buy_pullback_pct:
            return False
        size = self._calc_size(price)
        if size <= 0:
            return False
        self.strategy.log("BUY_PULLBACK", price,
                          f"peak={peak_price:.4f}, drawdown={drawdown:.2%}, size={size}sh")
        self.strategy.buy(size=size)
        return True


class SellManager:
    """卖出操作管理器：处理止盈和趋势反转清仓。"""

    def __init__(self, strategy: bt.Strategy) -> None:
        self.strategy = strategy

        self.peak_price: float = 0.0
        self.partial_tiers_hit: set[int] = set()
        self.trail_stop: float = 0.0

        self.partial_targets = [
            (self.strategy.p.tp_partial_1_pct, self.strategy.p.tp_partial_1_ratio),
            (self.strategy.p.tp_partial_2_pct, self.strategy.p.tp_partial_2_ratio),
            (self.strategy.p.tp_partial_3_pct, self.strategy.p.tp_partial_3_ratio),
        ]
        self.partial_targets = [
            (pct, r) for pct, r in self.partial_targets if pct > 0 and r > 0
        ]

    def update_peak(self, current_close: float) -> None:
        """更新持仓期间最高收盘价。"""
        if current_close > self.peak_price:
            self.peak_price = current_close

    def reset_state(self) -> None:
        """无持仓时重置止盈相关状态。"""
        self.partial_tiers_hit.clear()
        self.trail_stop = 0.0

    def check_take_profit(self, price: float) -> bool:
        """检查止盈条件。返回 True 表示仓位已全部平仓。"""
        mode = self.strategy.p.tp_mode

        if mode == "none":
            return False

        if mode == "trailing":
            if self.peak_price > 0:
                drawdown = (self.peak_price - price) / self.peak_price
                if drawdown >= self.strategy.p.tp_trail_pct:
                    self.strategy.log("TP_TRAIL", price,
                                      f"peak={self.peak_price:.4f}, drawdown={drawdown:.2%}")
                    self.strategy.close()
                    return True
            return False

        if mode == "partial":
            if self.strategy.position.size <= 0:
                return False
            avg_cost = self.strategy.position.price
            profit_pct = (price - avg_cost) / avg_cost if avg_cost > 0 else 0.0
            triggered_any = False

            for i, (target_pct, sell_ratio) in enumerate(self.partial_targets):
                if profit_pct >= target_pct and i not in self.partial_tiers_hit:
                    self.partial_tiers_hit.add(i)
                    sell_size = int(self.strategy.position.size * sell_ratio)
                    if sell_size > 0:
                        self.strategy.sell(size=sell_size)
                        self.strategy.log("TP_PARTIAL", price,
                                          f"tier={i+1}, cost={avg_cost:.4f}, "
                                          f"profit={profit_pct:.2%}, sell={sell_size}sh")
                    triggered_any = True

            if len(self.partial_tiers_hit) >= len(self.partial_targets):
                if self.strategy.position.size > 0:
                    self.strategy.log("TP_PARTIAL_EXIT", price,
                                      f"remaining={self.strategy.position.size}sh")
                    self.strategy.close()
                return True
            return triggered_any

        if mode == "atr":
            atr_val = float(self.strategy.atr[0])
            if atr_val > 0 and self.peak_price > 0:
                new_stop = self.peak_price - self.strategy.p.tp_atr_multiple * atr_val
                self.trail_stop = max(self.trail_stop, new_stop)
                if price <= self.trail_stop:
                    self.strategy.log("TP_ATR", price,
                                      f"peak={self.peak_price:.4f}, "
                                      f"stop={self.trail_stop:.4f}, atr={atr_val:.4f}")
                    self.strategy.close()
                    return True
            return False

        return False

    def check_trend_exit(self, price: float, sma_value: float, cross_value: int) -> bool:
        """价格下穿均线 → 清仓。返回是否执行了平仓。"""
        if cross_value < 0:
            self.strategy.log("EXIT_MA", price, f"sma={sma_value:.4f}")
            self.strategy.close()
            return True
        return False


class ETFTrendStrategy(bt.Strategy):
    """ETF 趋势跟踪 + 回撤加仓 + 可选止盈策略。

    设计约束:
    - __init__ 只初始化指标和状态变量
    - next 按事件驱动方式逐根 K 线处理交易逻辑
    """

    params = (
        # ==================== 核心参数 ====================
        ("ma_period", 30),            # 均线周期，默认 30 日
        ("buy_pullback_pct", 0.03),   # 回撤加仓阈值 X（从最高价回撤 X% 时买入）
        ("buy_cash_pct", 0.20),       # 每次买入使用当前可用资金的比例
        ("print_log", True),          # 是否打印交易日志

        # ==================== 止盈模式选择 ====================
        # 'none'    - 无止盈，纯趋势跟踪
        # 'trailing'- 移动止盈，从持仓最高价回撤 Y%
        # 'partial' - 分批止盈，到达利润目标分批卖出
        # 'atr'     - 基于 ATR 的动态止盈
        ("tp_mode", "none"),

        # ==================== 移动止盈参数 (tp_mode='trailing') ====================
        ("tp_trail_pct", 0.05),       # 从最高价回撤 Y% 时全部平仓

        # ==================== 分批止盈参数 (tp_mode='partial') ====================
        ("tp_partial_1_pct", 0.05),   # 第一档止盈目标涨幅
        ("tp_partial_1_ratio", 0.33), # 第一档卖出比例（占总仓位）
        ("tp_partial_2_pct", 0.10),   # 第二档止盈目标涨幅
        ("tp_partial_2_ratio", 0.33), # 第二档卖出比例
        ("tp_partial_3_pct", 0.15),   # 第三档止盈目标涨幅
        ("tp_partial_3_ratio", 0.34), # 第三档卖出比例

        # ==================== ATR止盈参数 (tp_mode='atr') ====================
        ("tp_atr_multiple", 3.0),     # ATR 倍数
        ("tp_atr_period", 14),        # ATR 计算周期
    )

    def __init__(self) -> None:
        """初始化指标与运行时状态。"""

        # --- 数据引用（取第一个数据源）---
        self.close_price = self.datas[0].close

        # --- 核心指标 ---
        # 30 日均线（SimpleMovingAverage）
        self.sma = bt.indicators.SimpleMovingAverage(
            self.close_price,
            period=self.p.ma_period,
        )
        # 均线交叉信号: 1=收盘价上穿均线, -1=下穿, 0=无交叉
        self.cross_ma = bt.indicators.CrossOver(
            self.close_price, self.sma
        )
        # ATR 指标（仅 atr 模式用到，但始终计算以避免切换时的索引越界）
        self.atr = bt.indicators.ATR(
            self.datas[0],
            period=self.p.tp_atr_period,
        )

        # --- 运行时管理对象 ---
        self.buy_mgr = BuyManager(self)
        self.sell_mgr = SellManager(self)
        # 当日价格在sma上的天数
        self.above_sma_days = 0

    # ------------------------------------------------------------------
    #  辅助方法
    # ------------------------------------------------------------------

    def log(self, action: str, price: float, extra: str = "") -> None:
        """打印交易日志。

        格式: 日期 | 动作 | 价格 | 可选补充信息
        """
        if not self.p.print_log:
            return
        trade_date = self.datas[0].datetime.date(0).isoformat()
        msg = f"{trade_date} | {action:<12} | price={price:.4f}"
        if extra:
            msg += f" | {extra}"
        print(msg)

    # ------------------------------------------------------------------
    #  核心交易逻辑（每根 K 线触发一次）
    # ------------------------------------------------------------------

    def next(self) -> None:
        """逐根 K 线触发的事件驱动交易逻辑。

        执行顺序（优先级由高到低）:
          1. 更新持仓期间最高价（peak_price）
          2. 检查止盈 → 平仓
          3. 检查均线下穿 → 平仓
          4. 检查回撤加仓
          5. 检查首次买入
        """
        current_close = float(self.close_price[0])
        sma_value = float(self.sma[0])
        cross_value = self.cross_ma[0]

        # ----------------------------------------------------------------
        # 第 0 步：更新持仓期间最高价, 重置止盈相关状态
        # 必须在任何交易操作之前执行
        # ----------------------------------------------------------------
        self.sell_mgr.update_peak(current_close)

        if current_close >= sma_value:
            self.above_sma_days += 1
        else:
            self.above_sma_days = 0

        if not self.position:
            self.sell_mgr.reset_state()

        # ================================================================
        #  有持仓时的逻辑
        # ================================================================
        if self.position:

            # --- 1. 检查止盈条件 ---
            if self.sell_mgr.check_take_profit(current_close):
                return

            # --- 2. 检查趋势反转（价格下穿均线）→ 清仓 ---
            if self.sell_mgr.check_trend_exit(current_close, sma_value, cross_value):
                return

            # 回测补仓
            if self.buy_mgr.try_pullback_buy(current_close, sma_value, self.sell_mgr.peak_price):
                return
        else:
            # ================================================================
            #  无持仓时的逻辑
            # ================================================================
            # --- 1. 首次买入：收盘价上穿均线 ---
            if self.above_sma_days >= 5 and self.buy_mgr.try_pullback_buy(current_close, sma_value, self.sell_mgr.peak_price):
                self.sell_mgr.peak_price = current_close
                return

        self.log("无任何操作", current_close, f"sma={sma_value:.4f}, cross={cross_value}")

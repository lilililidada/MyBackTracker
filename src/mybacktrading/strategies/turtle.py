"""
海龟交易策略（Turtle Trading Strategy）

策略思想来自经典海龟交易法则（Richard Dennis 训练的海龟交易员），核心规则如下：

1. 唐奇安通道突破入场
   - System 1（短线）：收盘价突破前 20 日最高价买入，跌破前 10 日最低价离场
   - System 2（长线）：收盘价突破前 55 日最高价买入，跌破前 20 日最低价离场
   - 通过 entry_period / exit_period 参数切换两套系统
2. 波动率基准 N
   - N = ATR(20)，即 20 日平均真实波幅
3. 单位头寸（仓位管理）
   - 1 个单位 = 账户净值 * risk_pct / (N * dollars_per_point)
   - 单个标的同一时间最多持有 max_units 个单位
4. 金字塔加仓
   - 价格每朝有利方向移动 add_atr_multiple * N，加仓 1 个单位
5. 2N 移动止损
   - 初始止损 = 首仓入场价 - stop_atr_multiple * N
   - 持仓期间止损随最高价上移：止损 = 持仓最高价 - stop_atr_multiple * N
6. 可选过滤（System 1）
   - use_profit_filter=True 时，若上一次交易盈利，则跳过本次入场

实现说明（简化版本）：
- 入场/离场用收盘价与“前 N 日”通道极值比较，避免把当日 K 线算进通道
- 信号触发后提交市价单，默认由 broker 在下一根 K 线开盘撮合
- 若需要按突破价精确成交，可将买单改为 bt.Order.Stop 类型
"""

from __future__ import annotations

import backtrader as bt


class TurtleStrategy(bt.Strategy):
    """海龟交易策略。

    设计约定:
    - __init__ 只初始化指标和状态变量
    - next 按事件驱动方式逐根 K 线处理交易逻辑
    """

    params = (
        # ==================== 系统参数 ====================
        # 唐奇安通道参数：System 1 用 (20, 10)，System 2 用 (55, 20)
        ("entry_period", 20),          # 突破入场周期（前 N 日最高价）
        ("exit_period", 10),           # 离场周期（前 N 日最低价）
        ("atr_period", 20),            # N 值计算周期（ATR）
        ("print_log", True),           # 是否打印交易日志

        # ==================== 仓位与加仓参数 ====================
        ("risk_pct", 0.01),            # 每个单位头寸对应的账户风险比例（经典海龟为 1%）
        ("dollars_per_point", 1.0),    # 每个价格点对应的每单位金额（股票为 1，期货按合约乘数）
        ("lot_size", 1),               # 最小下单单位（A股一手 100 股可设为 100）
        ("max_units", 4),              # 单笔交易最大单位数（经典海龟为 4）
        ("add_atr_multiple", 0.5),     # 价格每朝有利方向移动 0.5N 加仓 1 个单位
        ("stop_atr_multiple", 2.0),    # 止损为 N 的倍数（经典海龟为 2N）

        # ==================== 可选规则 ====================
        ("use_profit_filter", False),  # System 1 可选：上次交易盈利则跳过本次入场
    )

    def __init__(self) -> None:
        """初始化指标与运行时状态。"""

        # --- 数据引用（取第一个数据源）---
        self.close_price = self.datas[0].close

        # --- 核心指标 ---
        # 唐奇安上轨：前 entry_period 日最高价（用 [-1] 排除当日，判断“突破”）
        self.entry_high = bt.indicators.Highest(
            self.datas[0].high, period=self.p.entry_period,
        )
        # 唐奇安下轨：前 exit_period 日最低价（同样排除当日）
        self.exit_low = bt.indicators.Lowest(
            self.datas[0].low, period=self.p.exit_period,
        )
        # N 值：ATR(20)
        self.atr = bt.indicators.ATR(
            self.datas[0], period=self.p.atr_period,
        )

        # --- 运行时状态 ---
        self.order: bt.Order | None = None   # 当前未完成的订单
        self.units: int = 0                  # 当前交易已买入的单位数
        self.entry_price: float = 0.0        # 当前交易首个单位（首仓）的成交价
        self.trade_n: float = 0.0            # 入场时锁定的 N 值
        self.highest_high: float = 0.0       # 持仓期间最高价（用于 2N 移动止损）
        self.stop_price: float = 0.0         # 当前 2N 止损价
        self.last_trade_pnl: float = 0.0     # 上一次已平仓交易的盈亏（可选过滤用）

    # ------------------------------------------------------------------
    #  辅助方法
    # ------------------------------------------------------------------

    def log(self, action: str, price: float, extra: str = "") -> None:
        """打印交易日志。格式: 日期 | 动作 | 价格 | 可选补充信息"""
        if not self.p.print_log:
            return
        trade_date = self.datas[0].datetime.date(0).isoformat()
        msg = f"{trade_date} | {action:<14} | price={price:.4f}"
        if extra:
            msg += f" | {extra}"
        print(msg)

    def _reset_trade_state(self) -> None:
        """无持仓时重置当前交易相关状态。"""
        self.units = 0
        self.entry_price = 0.0
        self.trade_n = 0.0
        self.highest_high = 0.0
        self.stop_price = 0.0

    def _calc_unit_size(self, n_value: float) -> int:
        """按海龟公式计算 1 个单位的数量。

        公式: 单位数量 = 账户净值 * risk_pct / (N * dollars_per_point)
        含义: 价格朝不利方向波动 1 个 N 时，亏损约为账户净值的 risk_pct。
        """
        equity = self.broker.getvalue()
        dollar_risk = equity * self.p.risk_pct
        if n_value <= 0 or dollar_risk <= 0:
            return 0
        unit = int(dollar_risk / (n_value * self.p.dollars_per_point))
        lot = max(1, int(self.p.lot_size))
        return (unit // lot) * lot

    # ------------------------------------------------------------------
    #  回调方法
    # ------------------------------------------------------------------

    def notify_order(self, order: bt.Order) -> None:
        """订单回调：维护待完成订单与持仓状态。"""
        if order.status in (order.Completed, order.Canceled, order.Margin, order.Rejected):
            if order.status == order.Completed:
                if order.isbuy():
                    self.units += 1
                    if self.units == 1:
                        # 首仓成交：锁定入场价、N 值并设置初始 2N 止损
                        self.entry_price = order.executed.price
                        self.trade_n = float(self.atr[0])
                        self.highest_high = order.executed.price
                        self.stop_price = self.entry_price - self.p.stop_atr_multiple * self.trade_n
                    self.log("FILL_BUY", order.executed.price,
                             f"size={order.executed.size}, unit={self.units}")
                else:
                    self.log("FILL_SELL", order.executed.price,
                             f"size={order.executed.size}")
            self.order = None

    def notify_trade(self, trade: bt.Trade) -> None:
        """交易回调：记录上一次平仓盈亏，供 System 1 可选过滤使用。"""
        if trade.isclosed:
            self.last_trade_pnl = trade.pnl

    # ------------------------------------------------------------------
    #  核心交易逻辑（每根 K 线触发一次）
    # ------------------------------------------------------------------

    def next(self) -> None:
        """逐根 K 线触发的事件驱动交易逻辑。

        执行顺序（优先级由高到低）:
          1. 有未完成订单时等待成交，不做任何操作
          2. 无持仓：检查突破入场（含可选过滤）
          3. 有持仓：更新 2N 止损 → 检查通道离场 → 检查 2N 止损 → 检查金字塔加仓
        """
        # ----------------------------------------------------------------
        # 有未完成订单时，等订单成交后再处理后续逻辑，避免重复下单
        # ----------------------------------------------------------------
        if self.order is not None:
            return

        if not self.position:
            self._reset_trade_state()
            self._check_entry()
            return

        current_close = float(self.close_price[0])
        current_high = float(self.datas[0].high[0])

        # --- 更新持仓期间最高价与 2N 移动止损 ---
        self.highest_high = max(self.highest_high, current_high)
        if self.trade_n > 0:
            trail_stop = self.highest_high - self.p.stop_atr_multiple * self.trade_n
            self.stop_price = max(self.stop_price, trail_stop)

        # --- 1. 唐奇安通道下轨离场 ---
        exit_low = float(self.exit_low[-1])
        if current_close < exit_low:
            self.log("EXIT_CHANNEL", current_close, f"exit_low={exit_low:.4f}")
            self.order = self.close()
            return

        # --- 2. 2N 移动止损 ---
        if current_close <= self.stop_price:
            self.log("EXIT_STOP", current_close, f"stop={self.stop_price:.4f}")
            self.order = self.close()
            return

        # --- 3. 金字塔加仓：价格每上涨 0.5N 加仓 1 个单位 ---
        if self.units < self.p.max_units and self.trade_n > 0:
            add_level = self.entry_price + self.p.add_atr_multiple * self.trade_n * self.units
            if current_close >= add_level:
                size = self._calc_unit_size(self.trade_n)
                if size > 0:
                    self.log("BUY_ADD", current_close,
                             f"level={add_level:.4f}, unit={self.units + 1}, size={size}")
                    self.order = self.buy(size=size)

    def _check_entry(self) -> None:
        """无持仓时检查唐奇安通道突破入场。"""
        # System 1 可选过滤：上一次交易盈利则跳过本次入场
        if self.p.use_profit_filter and self.last_trade_pnl > 0:
            return

        current_close = float(self.close_price[0])
        n_value = float(self.atr[0])
        if n_value <= 0:
            return

        # 收盘价突破前 N 日最高价 → 买入 1 个单位
        entry_high = float(self.entry_high[-1])
        if current_close > entry_high:
            size = self._calc_unit_size(n_value)
            if size <= 0:
                return
            self.log("BUY_BREAKOUT", current_close,
                     f"entry_high={entry_high:.4f}, n={n_value:.4f}, size={size}")
            self.order = self.buy(size=size)

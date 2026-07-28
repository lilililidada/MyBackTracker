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

        # --- 运行时状态变量 ---
        # 本轮持仓期间的最高收盘价（用于计算回撤和止盈）
        self.peak_price: float = 0.0
        # 分批止盈已触发的档位索引（集合，避免重复触发）
        self.partial_tiers_hit: set[int] = set()
        # ATR 模式下的移动止损线（仅当 tp_mode='atr' 时使用）
        self.trail_stop: float = 0.0

        # 从参数构建分批止盈目标列表，过滤掉无效档位（pct <= 0 或 ratio <= 0）
        self.partial_targets = [
            (self.p.tp_partial_1_pct, self.p.tp_partial_1_ratio),
            (self.p.tp_partial_2_pct, self.p.tp_partial_2_ratio),
            (self.p.tp_partial_3_pct, self.p.tp_partial_3_ratio),
        ]
        self.partial_targets = [
            (pct, r) for pct, r in self.partial_targets if pct > 0 and r > 0
        ]

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

    def _calc_buy_size(self, price: float) -> int:
        """按可用资金比例计算买入股数。

        计算方式:
          1. 买入金额 = 当前可用现金 × buy_cash_pct
          2. 股数 = 买入金额 / 当前价格
          3. 向下取整到 100 的倍数（A 股 ETF 最小交易单位 1 手 = 100 份）
        """
        cash_to_use = self.broker.getcash() * self.p.buy_cash_pct
        size = int(cash_to_use / price)
        return (size // 100) * 100

    def _check_take_profit(self, price: float) -> bool:
        """检查是否触发了止盈条件。

        返回 True 表示仓位已全部平仓（或需要外部调用者帮平）；False 表示继续持仓。
        注意：trailing/atr 模式只做判断，由外部 next() 执行 close；
              partial 模式在方法内部执行部分卖出和最终清仓。
        """
        mode = self.p.tp_mode

        # ---------- 模式 A: 无止盈 ----------
        if mode == "none":
            return False

        # ---------- 模式 B: 移动止盈 ----------
        if mode == "trailing":
            if self.peak_price > 0:
                drawdown = (self.peak_price - price) / self.peak_price
                if drawdown >= self.p.tp_trail_pct:
                    self.log("TP_TRAIL", price,
                             f"peak={self.peak_price:.4f}, drawdown={drawdown:.2%}")
                    return True
            return False

        # ---------- 模式 C: 分批止盈 ----------
        if mode == "partial":
            if self.position.size <= 0:
                return False

            avg_cost = self.position.price
            profit_pct = (price - avg_cost) / avg_cost if avg_cost > 0 else 0.0
            triggered_any = False

            for i, (target_pct, sell_ratio) in enumerate(self.partial_targets):
                if profit_pct >= target_pct and i not in self.partial_tiers_hit:
                    self.partial_tiers_hit.add(i)
                    sell_size = int(self.position.size * sell_ratio)
                    if sell_size > 0:
                        self.sell(size=sell_size)
                        self.log("TP_PARTIAL", price,
                                 f"tier={i+1}, cost={avg_cost:.4f}, "
                                 f"profit={profit_pct:.2%}, sell={sell_size}sh")
                    triggered_any = True

            if len(self.partial_tiers_hit) >= len(self.partial_targets):
                if self.position.size > 0:
                    self.log("TP_PARTIAL_EXIT", price,
                             f"remaining={self.position.size}sh")
                    self.close()
                return True

            return triggered_any  # 虽然触发过卖出，但还有剩余仓位

        # ---------- 模式 D: ATR 动态止盈 ----------
        if mode == "atr":
            atr_val = float(self.atr[0])
            if atr_val > 0 and self.peak_price > 0:
                new_stop = self.peak_price - self.p.tp_atr_multiple * atr_val
                self.trail_stop = max(self.trail_stop, new_stop)

                if price <= self.trail_stop:
                    self.log("TP_ATR", price,
                             f"peak={self.peak_price:.4f}, "
                             f"stop={self.trail_stop:.4f}, atr={atr_val:.4f}")
                    return True
            return False

        return False

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
        # 第 0 步：更新/重置持仓期间最高价
        # 必须在任何交易操作之前执行
        # ----------------------------------------------------------------
        if self.position:
            if current_close > self.peak_price:
                self.peak_price = current_close
        else:
            self.peak_price = 0.0
            self.partial_tiers_hit.clear()
            self.trail_stop = 0.0

        # ================================================================
        #  有持仓时的逻辑
        # ================================================================
        if self.position:

            # --- 1. 检查止盈条件 ---
            if self._check_take_profit(current_close):
                return  # 仓位已关闭或正在关闭

            # --- 2. 检查趋势反转（价格下穿均线）→ 清仓 ---
            if cross_value < 0:
                self.log("EXIT_MA", current_close, f"sma={sma_value:.4f}")
                self.close()
                return

            # --- 3. 检查回撤加仓条件 ---
            # 条件：仍在均线上方 + 从整体最高价回撤超过 X%
            if current_close > sma_value and self.peak_price > 0:
                drawdown = (self.peak_price - current_close) / self.peak_price
                if drawdown >= self.p.buy_pullback_pct:
                    size = self._calc_buy_size(current_close)
                    if size > 0:
                        self.log("BUY_PULLBACK", current_close,
                                 f"peak={self.peak_price:.4f}, "
                                 f"drawdown={drawdown:.2%}, size={size}sh")
                        self.buy(size=size)
                        # peak_price 不重置：用整体最高价持续衡量回撤
            return

        # ================================================================
        #  无持仓时的逻辑
        # ================================================================

        # --- 1. 首次买入：收盘价上穿均线 ---
        if cross_value > 0:
            size = self._calc_buy_size(current_close)
            if size > 0:
                self.log("BUY_FIRST", current_close,
                         f"sma={sma_value:.4f}, size={size}sh")
                self.buy(size=size)
                self.peak_price = current_close

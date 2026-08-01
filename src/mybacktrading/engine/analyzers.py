"""Custom analyzers and formatted result printer for Backtrader backtests."""

from __future__ import annotations

import math
from datetime import date as date_type

import backtrader as bt

from mybacktrading.reports.quantstats_report import returns_to_series


# ------------------------------------------------------------------
#  SortinoRatio
# ------------------------------------------------------------------
class SortinoRatio(bt.Analyzer):
    params = (
        ("riskfreerate", 0.02),
        ("annualization", 252),
    )

    def start(self) -> None:
        self.daily_returns: list[float] = []
        self.prev_value = self.strategy.broker.getvalue()

    def next(self) -> None:
        current_value = self.strategy.broker.getvalue()
        daily_return = (current_value - self.prev_value) / self.prev_value
        self.daily_returns.append(daily_return)
        self.prev_value = current_value

    def stop(self) -> None:
        returns = self.daily_returns
        n = len(returns)
        if n < 2:
            self.ret = {"sortino": 0.0}
            return
        total_return = sum(returns)
        annual_return = (1.0 + total_return) ** (self.p.annualization / n) - 1.0
        downside = [r for r in returns if r < 0]
        if len(downside) > 1:
            mean_down = sum(downside) / len(downside)
            var_down = sum((d - mean_down) ** 2 for d in downside) / (len(downside) - 1)
            downside_std = math.sqrt(var_down) * math.sqrt(self.p.annualization)
        else:
            downside_std = 0.0
        sortino = (annual_return - self.p.riskfreerate) / downside_std if downside_std > 0 else 0.0
        self.ret = {"sortino": round(sortino, 4)}


# ------------------------------------------------------------------
#  CalmarRatio
# ------------------------------------------------------------------
class CalmarRatio(bt.Analyzer):
    params = (
        ("annualization", 252),
    )

    def start(self) -> None:
        self.values: list[float] = []
        self.peak = float("-inf")
        self.max_drawdown = 0.0

    def next(self) -> None:
        current_value = self.strategy.broker.getvalue()
        self.values.append(current_value)
        if current_value > self.peak:
            self.peak = current_value
        dd = (self.peak - current_value) / self.peak if self.peak > 0 else 0.0
        if dd > self.max_drawdown:
            self.max_drawdown = dd

    def stop(self) -> None:
        n = len(self.values)
        if n < 1:
            self.ret = {"calmar": 0.0, "annual_return": 0.0, "max_drawdown": 0.0}
            return
        start_val = self.values[0]
        end_val = self.values[-1]
        total_return = (end_val - start_val) / start_val if start_val > 0 else 0.0
        annual_return = (1.0 + total_return) ** (self.p.annualization / n) - 1.0 if n > 0 else 0.0
        calmar = annual_return / self.max_drawdown if self.max_drawdown > 0 else 0.0
        self.ret = {
            "calmar": round(calmar, 4),
            "annual_return": round(annual_return, 6),
            "max_drawdown": round(self.max_drawdown, 6),
        }


# ------------------------------------------------------------------
#  MaxDrawdownRecovery
# ------------------------------------------------------------------
class MaxDrawdownRecovery(bt.Analyzer):

    def start(self) -> None:
        self.peak_value = float("-inf")
        self.peak_date: date_type | None = None
        self.in_drawdown = False
        self.recovered_list: list[dict] = []
        self.unrecovered_peak_value = float("-inf")
        self.unrecovered_peak_date: date_type | None = None
        self.unrecovered_started = False

    def next(self) -> None:
        current_value = self.strategy.broker.getvalue()
        bar_date: date_type = self.datas[0].datetime.date(0)
        if current_value > self.peak_value:
            if self.in_drawdown and self.peak_value != float("-inf"):
                recovery_days = (bar_date - self.peak_date).days
                self.recovered_list.append({
                    "peak_date": str(self.peak_date),
                    "recovery_date": str(bar_date),
                    "recovery_days": recovery_days,
                })
            self.peak_value = current_value
            self.peak_date = bar_date
            self.in_drawdown = False
            self.unrecovered_peak_value = float("-inf")
            self.unrecovered_peak_date = None
            self.unrecovered_started = False
        else:
            if not self.unrecovered_started and self.peak_value != float("-inf"):
                self.unrecovered_peak_value = self.peak_value
                self.unrecovered_peak_date = self.peak_date
                self.unrecovered_started = True
                self.in_drawdown = True

    def stop(self) -> None:
        if self.unrecovered_started and self.unrecovered_peak_date is not None:
            last_date: date_type = self.datas[0].datetime.date(-1)
            unrecovered_days = (last_date - self.unrecovered_peak_date).days
            self.recovered_list.append({
                "peak_date": str(self.unrecovered_peak_date),
                "recovery_date": None,
                "recovery_days": unrecovered_days,
                "unrecovered": True,
            })
        max_recovered = None
        max_unrecovered = None
        for rec in self.recovered_list:
            if rec.get("unrecovered"):
                if max_unrecovered is None or rec["recovery_days"] > max_unrecovered["recovery_days"]:
                    max_unrecovered = rec
            else:
                if max_recovered is None or rec["recovery_days"] > max_recovered["recovery_days"]:
                    max_recovered = rec
        result: dict = {}
        if max_recovered is not None:
            result["max_recovery_days"] = max_recovered["recovery_days"]
            result["max_recovery_peak_date"] = str(max_recovered["peak_date"])
            result["max_recovery_recovery_date"] = str(max_recovered["recovery_date"])
        else:
            result["max_recovery_days"] = 0
            result["max_recovery_peak_date"] = None
            result["max_recovery_recovery_date"] = None
        if max_unrecovered is not None:
            result["unrecovered_days"] = max_unrecovered["recovery_days"]
            result["unrecovered_peak_date"] = str(max_unrecovered["peak_date"])
        else:
            result["unrecovered_days"] = 0
            result["unrecovered_peak_date"] = None
        self.ret = result


# ------------------------------------------------------------------
#  print_full_analysis
# ------------------------------------------------------------------

LABELS = {
    "title": "Strategy Performance Report",
    "s1": "[ Return and Risk ]",
    "s2": "[ Trade Statistics ]",
    "ic": "Initial Capital",
    "fe": "Final Equity",
    "tr": "Total Return",
    "bh": "Buy and Hold Return",
    "rb": "Relative Ret (vs BH)",
    "br": "Benchmark Return",
    "rvb": "Relative Ret (vs Bench)",
    "ar": "Annual Return",
    "av": "Annual Volatility",
    "sr": "Sharpe Ratio",
    "sortino": "Sortino Ratio",
    "calmar": "Calmar Ratio",
    "md": "Max Drawdown",
    "mdd": "Max DD Duration",
    "mrp": "Max Recovery Period",
    "cds": "Current DD Status",
    "nt": "Total Trades",
    "wr": "Win Rate",
    "pr": "Profit Ratio",
    "aw": "Avg Win (abs)",
    "al": "Avg Loss (abs)",
    "mcs": "Max Consec Wins",
    "mcl": "Max Consec Losses",
    "tc": "Total Commission",
}


def print_full_analysis(cerebro_run_result, buy_hold_return=0.0, benchmark_return=None) -> None:
    if isinstance(cerebro_run_result, list):
        strategy = cerebro_run_result[0]
    else:
        strategy = cerebro_run_result

    ret_analysis = strategy.analyzers.returns.get_analysis()
    total_return = ret_analysis.get("rtot", 0.0)
    annual_return = ret_analysis.get("rnorm", 0.0)
    daily_ret = returns_to_series(strategy.analyzers.timereturn.get_analysis())
    daily_std = daily_ret.std() if len(daily_ret) > 1 else 0.0
    annual_vol = daily_std * math.sqrt(252)
    sharpe = (strategy.analyzers.sharpe.get_analysis().get("sharperatio", 0.0) or 0.0)
    dd_a = strategy.analyzers.drawdown.get_analysis()
    max_dd_pct = abs(dd_a.get("max", {}).get("drawdown", 0.0))
    max_dd_len = dd_a.get("max", {}).get("len", 0)
    ta = strategy.analyzers.tradeanalyzer.get_analysis()
    total_trades = ta.get("total", {}).get("total", 0)
    won = ta.get("total", {}).get("won", 0)
    lost = ta.get("total", {}).get("lost", 0)
    win_rate = (won / total_trades * 100) if total_trades > 0 else 0.0
    pnl_w = ta.get("total", {}).get("won", {}).get("pnl", {}).get("total", 0.0)
    pnl_l = ta.get("total", {}).get("lost", {}).get("pnl", {}).get("total", 0.0)
    avg_w = ta.get("total", {}).get("won", {}).get("pnl", {}).get("average", 0.0)
    avg_l = ta.get("total", {}).get("lost", {}).get("pnl", {}).get("average", 0.0)
    profit_ratio = abs(pnl_w / pnl_l) if pnl_l != 0 else 0.0
    sw = ta.get("total", {}).get("streak", {}).get("won", {}).get("longest", 0)
    sl = ta.get("total", {}).get("streak", {}).get("lost", {}).get("longest", 0)
    tc = ta.get("total", {}).get("commission", 0.0) or 0.0
    sortino = strategy.analyzers.sortino.get_analysis().get("sortino", 0.0)
    calmar = strategy.analyzers.calmar.get_analysis().get("calmar", 0.0)
    ra = strategy.analyzers.maxrecovery.get_analysis()
    mrd = ra.get("max_recovery_days", 0)
    urd = ra.get("unrecovered_days", 0)
    urp = ra.get("unrecovered_peak_date", None)
    mrp = ra.get("max_recovery_peak_date", None)
    mrr = ra.get("max_recovery_recovery_date", None)
    rrbh = total_return - buy_hold_return
    rrbench = (total_return - benchmark_return) if benchmark_return is not None else None
    ic = strategy.broker.startingcash
    ev = strategy.broker.getvalue()

    L = LABELS
    sep = "-" * 54
    w = 54
    lines = [""]
    lines.append("+" + "=" * w + "+")
    lines.append("|  " + L['title'].center(w - 4) + "  |")
    lines.append("+" + "=" * w + "+")
    lines.append("|  " + L['s1'].ljust(w - 4) + "  |")
    lines.append("|" + sep + "|")
    def fm(v): return f"$ {v:,.2f}"
    def fp(v):
        s = "+" if v >= 0 else ""
        return f"{s}{v*100:.2f}%"
    lines.append(f"|  {L['ic']:<20}{fm(ic):>30} |")
    lines.append(f"|  {L['fe']:<20}{fm(ev):>30} |")
    lines.append(f"|  {L['tr']:<20}{fp(total_return):>30} |")
    lines.append(f"|  {L['bh']:<20}{fp(buy_hold_return):>30} |")
    lines.append(f"|  {L['rb']:<20}{fp(rrbh):>30} |")
    if benchmark_return is not None:
        lines.append(f"|  {L['br']:<20}{fp(benchmark_return):>30} |")
        lines.append(f"|  {L['rvb']:<20}{fp(rrbench):>30} |")
    lines.append(f"|  {L['ar']:<20}{fp(annual_return):>30} |")
    lines.append(f"|  {L['av']:<20}{fp(annual_vol):>30} |")
    lines.append(f"|  {L['sr']:<20}{sharpe:>30.4f} |")
    lines.append(f"|  {L['sortino']:<20}{sortino:>30.4f} |")
    lines.append(f"|  {L['calmar']:<20}{calmar:>30.4f} |")
    lines.append(f"|  {L['md']:<20}{fp(max_dd_pct/100):>30} |")
    lines.append(f"|  {L['mdd']:<20}{max_dd_len:>30} days |")
    if mrd and mrd > 0:
        lines.append(f"|  {L['mrp']:<20}{mrd:>30} days |")
        if mrp and mrr:
            lines.append(f"|  ({mrp} -> {mrr})".center(w - 2) + "  |")
    if urd and urd > 0 and urp:
        lines.append(f"|  {L['cds']:<20}Unrecovered ({urd} days) |")
        lines.append(f"|  (<- {urp})".center(w - 2) + "  |")
    lines.append("+" + "=" * w + "+")
    lines.append("|  " + L['s2'].ljust(w - 4) + "  |")
    lines.append("|" + sep + "|")
    lines.append(f"|  {L['nt']:<20}{total_trades:>30} |")
    lines.append(f"|  {L['wr']:<20}{win_rate:>29.2f}% |")
    lines.append(f"|  {L['pr']:<20}{profit_ratio:>30.4f} |")
    lines.append(f"|  {L['aw']:<20}{fm(abs(avg_w)):>30} |")
    lines.append(f"|  {L['al']:<20}{fm(abs(avg_l)):>30} |")
    lines.append(f"|  {L['mcs']:<20}{sw:>30} |")
    lines.append(f"|  {L['mcl']:<20}{sl:>30} |")
    lines.append(f"|  {L['tc']:<20}{fm(tc):>30} |")
    lines.append("+" + "=" * w + "+")
    lines.append("")
    print("\n".join(lines))

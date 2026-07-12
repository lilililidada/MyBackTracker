# MyBackTrading

面向 A 股、外汇和通用 OHLCV 数据的 Backtrader 回测骨架。

## 模块结构

```text
src/mybacktrading/
  config.py                  # 回测参数配置
  cli.py                     # 命令行入口
  data/ingestion.py          # AKShare/CSV 数据获取与清洗
  strategies/sma_cross.py    # 双均线策略模板
  engine/backtest.py         # Cerebro 引擎、资金、手续费、分析器
  reports/quantstats_report.py # QuantStats 报告生成
```

## 安装

```powershell
pip install -r requirements.txt
pip install -e .
```

注意：`matplotlib==3.2.2` 需要 `numpy<2`，否则 QuantStats 生成图表时会报 `_ARRAY_API` 或 `numpy.core.multiarray failed to import`。

## 运行

兼容入口：

```powershell
python phase1_backtrader_quantstats.py --symbol 600519 --start 20200101 --end 20251231
```

安装为包后的入口：

```powershell
mybacktrading --symbol 600519 --start 20200101 --end 20251231
```

仅验证回测引擎，不生成 QuantStats 报告：

```powershell
python phase1_backtrader_quantstats.py --symbol 600519 --start 20200101 --end 20251231 --skip-report
```

"""Strategy registry."""

from mybacktrading.strategies.sma_cross import SmaCrossStrategy
from mybacktrading.strategies.etf_trend import ETFTrendStrategy
from mybacktrading.strategies.seven_star_etf import SevenStarStrategy

__all__ = ["SmaCrossStrategy", "ETFTrendStrategy", "SevenStarStrategy"]

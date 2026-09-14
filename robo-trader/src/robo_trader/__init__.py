"""Robo trader para criptomoedas: dados, estrategias, backtest e execucao."""

from .backtest import BacktestConfig, BacktestEngine, BacktestResult
from .domain import Fill, Order, OrderType, Position, Side, Trade
from .risk import RiskConfig, RiskManager
from .strategies import Strategy, available, build_strategy

__version__ = "0.1.0"

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "Fill",
    "Order",
    "OrderType",
    "Position",
    "RiskConfig",
    "RiskManager",
    "Side",
    "Strategy",
    "Trade",
    "__version__",
    "available",
    "build_strategy",
]

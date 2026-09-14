"""Robo trader para criptomoedas: dados, estrategias, backtest e execucao."""

from .backtest import BacktestConfig, BacktestEngine, BacktestResult
from .config import ExchangeCredentials, load_env_file
from .domain import Fill, Order, OrderType, Position, Side, Trade
from .execution import build_execution_client
from .risk import RiskConfig, RiskManager
from .strategies import Strategy, available, build_strategy

__version__ = "0.1.0"

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "ExchangeCredentials",
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
    "build_execution_client",
    "build_strategy",
    "load_env_file",
]

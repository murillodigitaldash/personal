"""Motor de backtest, carteira simulada e metricas."""

from .engine import BacktestConfig, BacktestEngine
from .metrics import compute_metrics, drawdown_series, max_drawdown, sharpe_ratio, sortino_ratio
from .portfolio import Portfolio
from .result import BacktestResult

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "Portfolio",
    "compute_metrics",
    "drawdown_series",
    "max_drawdown",
    "sharpe_ratio",
    "sortino_ratio",
]

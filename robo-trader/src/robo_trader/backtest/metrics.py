"""Metricas de desempenho da curva de capital e dos trades fechados."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.schema import infer_periods_per_year
from ..domain import Trade

TRADING_DAYS = 365.0  # cripto negocia todos os dias


def drawdown_series(equity: pd.Series) -> pd.Series:
    """Queda percentual em relacao ao pico anterior, candle a candle."""
    peak = equity.cummax()
    return equity / peak - 1.0


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float(drawdown_series(equity).min())


def sharpe_ratio(returns: pd.Series, periods_per_year: float, risk_free: float = 0.0) -> float:
    """Sharpe anualizado. `risk_free` e a taxa anual equivalente."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free / periods_per_year
    std = excess.std(ddof=1)
    if not np.isfinite(std) or std == 0:
        return 0.0
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def sortino_ratio(returns: pd.Series, periods_per_year: float, risk_free: float = 0.0) -> float:
    """Como o Sharpe, mas punindo apenas a volatilidade negativa."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free / periods_per_year
    downside = excess[excess < 0]
    if downside.empty:
        return 0.0
    downside_std = float(np.sqrt((downside**2).mean()))
    if downside_std == 0:
        return 0.0
    return float(excess.mean() / downside_std * np.sqrt(periods_per_year))


def cagr(equity: pd.Series, periods_per_year: float) -> float:
    """Retorno anual composto equivalente."""
    if len(equity) < 2 or equity.iloc[0] <= 0 or equity.iloc[-1] <= 0:
        return 0.0
    years = (len(equity) - 1) / periods_per_year
    if years <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def trade_stats(trades: list[Trade]) -> dict[str, float]:
    """Estatisticas dos round trips fechados (PnL ja liquido de taxas)."""
    if not trades:
        return {
            "num_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
        }

    pnls = np.array([t.pnl for t in trades], dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    gross_loss = float(-losses.sum())

    return {
        "num_trades": int(len(trades)),
        "win_rate": float(len(wins) / len(pnls)),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else float("inf"),
        "avg_trade_pnl": float(pnls.mean()),
        "best_trade": float(pnls.max()),
        "worst_trade": float(pnls.min()),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
    }


def compute_metrics(
    equity: pd.Series,
    trades: list[Trade],
    weights: pd.Series | None = None,
    benchmark: pd.Series | None = None,
    periods_per_year: float | None = None,
    risk_free: float = 0.0,
) -> dict[str, float]:
    """Consolida retorno, risco e estatisticas de trade em um unico dicionario."""
    if equity.empty:
        raise ValueError("curva de capital vazia")

    ppy = periods_per_year or infer_periods_per_year(pd.DatetimeIndex(equity.index))
    returns = equity.pct_change().dropna()
    dd = max_drawdown(equity)
    annual_return = cagr(equity, ppy)

    metrics: dict[str, float] = {
        "initial_equity": float(equity.iloc[0]),
        "final_equity": float(equity.iloc[-1]),
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1),
        "cagr": annual_return,
        "annual_volatility": float(returns.std(ddof=1) * np.sqrt(ppy)) if len(returns) > 1 else 0.0,
        "sharpe": sharpe_ratio(returns, ppy, risk_free),
        "sortino": sortino_ratio(returns, ppy, risk_free),
        "max_drawdown": dd,
        "calmar": float(annual_return / abs(dd)) if dd < 0 else 0.0,
        "periods_per_year": float(ppy),
        "bars": int(len(equity)),
    }
    metrics.update(trade_stats(trades))

    if weights is not None and len(weights):
        metrics["exposure"] = float((weights.abs() > 1e-9).mean())
        metrics["avg_weight"] = float(weights.mean())

    if benchmark is not None and len(benchmark) > 1 and benchmark.iloc[0] > 0:
        buy_hold = float(benchmark.iloc[-1] / benchmark.iloc[0] - 1)
        metrics["buy_hold_return"] = buy_hold
        metrics["excess_return"] = metrics["total_return"] - buy_hold

    return metrics

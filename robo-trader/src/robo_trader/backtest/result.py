"""Resultado de um backtest e sua apresentacao."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..domain import Fill, Trade

_LABELS = [
    ("initial_equity", "Capital inicial", "money"),
    ("final_equity", "Capital final", "money"),
    ("total_return", "Retorno total", "pct"),
    ("buy_hold_return", "Buy & hold", "pct"),
    ("excess_return", "Excesso sobre buy & hold", "pct"),
    ("cagr", "Retorno anualizado (CAGR)", "pct"),
    ("annual_volatility", "Volatilidade anualizada", "pct"),
    ("sharpe", "Sharpe", "num"),
    ("sortino", "Sortino", "num"),
    ("max_drawdown", "Drawdown maximo", "pct"),
    ("calmar", "Calmar", "num"),
    ("exposure", "Tempo exposto", "pct"),
    ("num_trades", "Trades fechados", "int"),
    ("win_rate", "Acerto", "pct"),
    ("profit_factor", "Fator de lucro", "num"),
    ("avg_trade_pnl", "PnL medio por trade", "money"),
    ("best_trade", "Melhor trade", "money"),
    ("worst_trade", "Pior trade", "money"),
    ("total_fees", "Custos totais", "money"),
]


def _format(value: float, kind: str) -> str:
    if kind == "pct":
        return f"{value:>12.2%}"
    if kind == "money":
        return f"{value:>12,.2f}"
    if kind == "int":
        return f"{int(value):>12d}"
    if value == float("inf"):
        return f"{'inf':>12}"
    return f"{value:>12.2f}"


@dataclass
class BacktestResult:
    """Curva de capital, trades e metricas de uma simulacao."""

    symbol: str
    strategy: str
    equity: pd.Series
    weights: pd.Series
    trades: list[Trade]
    fills: list[Fill]
    metrics: dict[str, float]
    halted_reason: str | None = None
    meta: dict = field(default_factory=dict)

    @property
    def drawdown(self) -> pd.Series:
        from .metrics import drawdown_series

        return drawdown_series(self.equity)

    def trades_frame(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(
                columns=[
                    "symbol", "side", "quantity", "entry_time", "entry_price",
                    "exit_time", "exit_price", "fees", "pnl", "return_pct",
                ]
            )
        return pd.DataFrame(
            [
                {
                    "symbol": t.symbol,
                    "side": t.side.value,
                    "quantity": t.quantity,
                    "entry_time": t.entry_time,
                    "entry_price": t.entry_price,
                    "exit_time": t.exit_time,
                    "exit_price": t.exit_price,
                    "fees": t.fees,
                    "pnl": t.pnl,
                    "return_pct": t.return_pct,
                }
                for t in self.trades
            ]
        )

    def summary(self) -> str:
        period = f"{self.equity.index[0]:%Y-%m-%d} a {self.equity.index[-1]:%Y-%m-%d}"
        lines = [
            f"Backtest {self.strategy} em {self.symbol}",
            f"Periodo: {period}  ({self.metrics.get('bars', 0)} candles)",
            "-" * 52,
        ]
        for key, label, kind in _LABELS:
            if key in self.metrics:
                lines.append(f"{label:<30}{_format(self.metrics[key], kind)}")
        if self.halted_reason:
            lines += ["-" * 52, f"Robo interrompido: {self.halted_reason}"]
        return "\n".join(lines)

    def save(self, directory: str | Path) -> dict[str, Path]:
        """Grava curva de capital, trades e metricas em disco."""
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        equity_file = out / "equity.csv"
        trades_file = out / "trades.csv"
        metrics_file = out / "metrics.csv"

        pd.DataFrame({"equity": self.equity, "weight": self.weights}).to_csv(equity_file)
        self.trades_frame().to_csv(trades_file, index=False)
        pd.Series(self.metrics).to_csv(metrics_file, header=["value"])
        return {"equity": equity_file, "trades": trades_file, "metrics": metrics_file}

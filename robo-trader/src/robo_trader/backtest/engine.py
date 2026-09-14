"""Motor de backtest orientado a candles."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..data.schema import infer_periods_per_year, normalize_ohlcv
from ..risk import RiskConfig, RiskManager
from ..strategies.base import Strategy
from .metrics import compute_metrics
from .portfolio import Portfolio
from .result import BacktestResult


@dataclass(frozen=True)
class BacktestConfig:
    """Parametros de custo e capital da simulacao."""

    initial_cash: float = 10_000.0
    fee_rate: float = 0.001  # taker padrao da Binance spot
    slippage_rate: float = 0.0005
    risk_free_rate: float = 0.0
    close_at_end: bool = True


class BacktestEngine:
    """Roda a estrategia candle a candle, sem antecipacao de dados.

    O sinal de um candle so vira ordem na abertura do candle seguinte, e stop loss
    e take profit sao avaliados dentro do candle pelas maxima e minima. Quando os
    dois poderiam disparar no mesmo candle, o stop e considerado primeiro: e a
    hipotese pessimista, e uma simulacao otimista aqui viraria prejuizo no ar.
    """

    def __init__(
        self,
        config: BacktestConfig | None = None,
        risk: RiskConfig | RiskManager | None = None,
    ) -> None:
        self.config = config or BacktestConfig()
        if isinstance(risk, RiskManager):
            self.risk = risk
        else:
            self.risk = RiskManager(risk or RiskConfig())

    def run(
        self,
        df: pd.DataFrame,
        strategy: Strategy,
        symbol: str = "UNKNOWN",
        signals: pd.Series | None = None,
    ) -> BacktestResult:
        candles = normalize_ohlcv(df)
        if len(candles) < 2:
            raise ValueError("backtest exige ao menos 2 candles")

        raw_signals = strategy.generate_signals(candles) if signals is None else signals
        target = raw_signals.reindex(candles.index).astype(float).fillna(0.0)
        # O sinal lido no fechamento do candle t so pode ser executado em t+1.
        target = target.shift(1).fillna(0.0)

        cfg = self.config
        portfolio = Portfolio(
            symbol=symbol,
            initial_cash=cfg.initial_cash,
            fee_rate=cfg.fee_rate,
            slippage_rate=cfg.slippage_rate,
        )
        self.risk.reset()
        risk_cfg = self.risk.config

        equity_values: list[float] = []
        weight_values: list[float] = []

        opens = candles["open"].to_numpy()
        highs = candles["high"].to_numpy()
        lows = candles["low"].to_numpy()
        closes = candles["close"].to_numpy()
        targets = target.to_numpy()

        for i, timestamp in enumerate(candles.index):
            open_price = opens[i]

            if i > 0:
                self.risk.update(timestamp, portfolio.equity(open_price))
                weight = self.risk.allowed_weight(targets[i])
                portfolio.rebalance(
                    timestamp,
                    open_price,
                    weight,
                    min_notional=risk_cfg.min_trade_notional,
                    threshold=risk_cfg.rebalance_threshold,
                )
                self._apply_exit_levels(portfolio, timestamp, highs[i], lows[i])

            close_price = closes[i]
            equity_values.append(portfolio.equity(close_price))
            weight_values.append(portfolio.weight(close_price))

        if cfg.close_at_end and not portfolio.position.is_flat:
            portfolio.close(candles.index[-1], closes[-1])
            equity_values[-1] = portfolio.equity(closes[-1])
            weight_values[-1] = portfolio.weight(closes[-1])

        equity = pd.Series(equity_values, index=candles.index, name="equity")
        weights = pd.Series(weight_values, index=candles.index, name="weight")

        metrics = compute_metrics(
            equity,
            portfolio.trades,
            weights=weights,
            benchmark=candles["close"],
            periods_per_year=infer_periods_per_year(candles.index),
            risk_free=cfg.risk_free_rate,
        )
        metrics["total_fees"] = portfolio.total_fees

        return BacktestResult(
            symbol=symbol,
            strategy=strategy.describe(),
            equity=equity,
            weights=weights,
            trades=portfolio.trades,
            fills=portfolio.fills,
            metrics=metrics,
            halted_reason=self.risk.blocked_reason if self.risk.halted else None,
            meta={
                "config": self.config,
                "risk": risk_cfg,
                "warmup": strategy.warmup,
            },
        )

    def _apply_exit_levels(
        self, portfolio: Portfolio, timestamp: pd.Timestamp, high: float, low: float
    ) -> None:
        """Dispara stop loss / take profit tocados dentro do candle."""
        position = portfolio.position
        if position.is_flat:
            return

        is_long = position.quantity > 0
        stop, target = self.risk.exit_levels(position.avg_price, is_long)

        if stop is not None and ((is_long and low <= stop) or (not is_long and high >= stop)):
            portfolio.close_at_price(timestamp, stop)
            return

        if target is not None and ((is_long and high >= target) or (not is_long and low <= target)):
            portfolio.close_at_price(timestamp, target)

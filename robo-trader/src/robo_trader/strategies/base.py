"""Contrato das estrategias."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """Traduz candles em peso alvo da carteira.

    O retorno de `generate_signals` e uma serie em [-1, 1] alinhada ao indice dos
    candles: 1 significa comprado com todo o capital elegivel, -1 vendido, 0 fora.
    Cada valor deve depender apenas de informacao ate o fechamento daquele candle;
    o motor de backtest desloca a serie em um candle antes de executar, de modo que
    a ordem sai na abertura seguinte e nao ha antecipacao de dados.
    """

    name: str = "strategy"

    def __init__(self, **params) -> None:
        self.params = params

    @property
    def warmup(self) -> int:
        """Candles iniciais sem sinal confiavel (aquecimento dos indicadores)."""
        return 0

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        ...

    def _validate(self, df: pd.DataFrame) -> None:
        if len(df) <= self.warmup:
            raise ValueError(
                f"{self.name} precisa de mais de {self.warmup} candles, recebeu {len(df)}"
            )

    def describe(self) -> str:
        args = ", ".join(f"{k}={v}" for k, v in sorted(self.params.items()))
        return f"{self.name}({args})"

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return self.describe()

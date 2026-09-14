"""Reversao a media por RSI."""

from __future__ import annotations

import pandas as pd

from ..indicators import rsi
from .base import Strategy


class RsiReversion(Strategy):
    """Compra sobrevenda e zera ao voltar para a faixa neutra.

    Entra comprado quando o RSI cai abaixo de `oversold` e mantem a posicao ate o
    indice recuperar `exit_level`, evitando o zigue-zague de sair no primeiro repique.
    """

    name = "rsi_reversion"

    def __init__(self, period: int = 14, oversold: float = 30.0, exit_level: float = 55.0) -> None:
        if not 0 < oversold < exit_level < 100:
            raise ValueError("exige 0 < oversold < exit_level < 100")
        super().__init__(period=period, oversold=oversold, exit_level=exit_level)
        self.period = period
        self.oversold = oversold
        self.exit_level = exit_level

    @property
    def warmup(self) -> int:
        return self.period + 1

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        self._validate(df)
        index = rsi(df["close"], self.period)
        # Entrada e saida em niveis distintos: o estado so muda nos gatilhos.
        state = pd.Series(pd.NA, index=df.index, dtype="Float64")
        state[index < self.oversold] = 1.0
        state[index >= self.exit_level] = 0.0
        signal = state.ffill().fillna(0.0).astype(float)
        return signal.where(index.notna(), 0.0)

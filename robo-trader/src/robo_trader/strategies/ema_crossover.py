"""Seguidor de tendencia por cruzamento de medias exponenciais."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import ema
from .base import Strategy


class EmaCrossover(Strategy):
    """Comprado quando a EMA rapida esta acima da lenta.

    Com `allow_short`, inverte a posicao em vez de apenas sair.
    """

    name = "ema_crossover"

    def __init__(self, fast: int = 12, slow: int = 26, allow_short: bool = False) -> None:
        if fast >= slow:
            raise ValueError("fast deve ser menor que slow")
        super().__init__(fast=fast, slow=slow, allow_short=allow_short)
        self.fast = fast
        self.slow = slow
        self.allow_short = allow_short

    @property
    def warmup(self) -> int:
        return self.slow

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        self._validate(df)
        fast_line = ema(df["close"], self.fast)
        slow_line = ema(df["close"], self.slow)
        bullish = fast_line > slow_line
        short_leg = -1.0 if self.allow_short else 0.0
        signal = pd.Series(np.where(bullish, 1.0, short_leg), index=df.index, dtype=float)
        return signal.where(slow_line.notna(), 0.0)

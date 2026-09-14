"""Rompimento de canal de Donchian."""

from __future__ import annotations

import pandas as pd

from ..indicators import donchian
from .base import Strategy


class DonchianBreakout(Strategy):
    """Compra o rompimento da maxima de N candles e sai na minima de M candles."""

    name = "donchian_breakout"

    def __init__(self, entry: int = 20, exit: int = 10) -> None:
        if entry < 2 or exit < 2:
            raise ValueError("entry e exit devem ser >= 2")
        super().__init__(entry=entry, exit=exit)
        self.entry = entry
        self.exit = exit

    @property
    def warmup(self) -> int:
        return max(self.entry, self.exit) + 1

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        self._validate(df)
        upper, _ = donchian(df, self.entry)
        _, lower = donchian(df, self.exit)
        close = df["close"]

        state = pd.Series(pd.NA, index=df.index, dtype="Float64")
        state[close > upper] = 1.0
        state[close < lower] = 0.0
        signal = state.ffill().fillna(0.0).astype(float)
        return signal.where(upper.notna() & lower.notna(), 0.0)

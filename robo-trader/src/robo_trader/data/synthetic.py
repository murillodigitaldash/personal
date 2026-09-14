"""Gerador de candles sinteticos para testes e demonstracoes offline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import timeframe_to_timedelta


def generate_ohlcv(
    periods: int = 2000,
    timeframe: str = "1h",
    start: str = "2024-01-01",
    start_price: float = 30_000.0,
    drift: float = 0.0002,
    volatility: float = 0.01,
    seed: int = 42,
) -> pd.DataFrame:
    """Serie de candles por caminho log-normal, com OHLC coerente.

    Nao substitui dados reais: serve para exercitar o motor sem depender de rede.
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range(
        pd.Timestamp(start, tz="UTC"), periods=periods, freq=timeframe_to_timedelta(timeframe)
    )

    returns = rng.normal(drift, volatility, periods)
    close = start_price * np.exp(np.cumsum(returns))
    open_ = np.concatenate(([start_price], close[:-1]))

    span = np.abs(rng.normal(0, volatility / 2, periods)) * close
    high = np.maximum(open_, close) + span
    low = np.minimum(open_, close) - span
    volume = rng.lognormal(mean=3.0, sigma=0.4, size=periods)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=pd.DatetimeIndex(index, name="timestamp"),
    )

"""Contrato comum das fontes de candles."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from .schema import to_utc


@runtime_checkable
class MarketDataSource(Protocol):
    """Qualquer fonte de candles que o backtest e o runner sabem consumir."""

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: pd.Timestamp | str | None = None,
        until: pd.Timestamp | str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Candles normalizados com indice UTC e colunas open/high/low/close/volume."""
        ...


def slice_range(
    df: pd.DataFrame,
    since: pd.Timestamp | str | None = None,
    until: pd.Timestamp | str | None = None,
) -> pd.DataFrame:
    """Recorta a janela pedida, tratando datas soltas como UTC."""
    out = df
    if since is not None:
        out = out.loc[out.index >= to_utc(since)]
    if until is not None:
        out = out.loc[out.index <= to_utc(until)]
    return out

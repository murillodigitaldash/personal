"""Normalizacao e validacao do dataframe de candles (OHLCV)."""

from __future__ import annotations

import pandas as pd

from ..domain import OHLCV_COLUMNS

TIMEFRAME_TO_TIMEDELTA = {
    "1m": pd.Timedelta(minutes=1),
    "3m": pd.Timedelta(minutes=3),
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30),
    "1h": pd.Timedelta(hours=1),
    "2h": pd.Timedelta(hours=2),
    "4h": pd.Timedelta(hours=4),
    "6h": pd.Timedelta(hours=6),
    "12h": pd.Timedelta(hours=12),
    "1d": pd.Timedelta(days=1),
    "1w": pd.Timedelta(weeks=1),
}


class DataValidationError(ValueError):
    """Os candles recebidos nao formam uma serie utilizavel."""


def to_utc(value: pd.Timestamp | str) -> pd.Timestamp:
    """Timestamp em UTC, aceitando texto, data ingenua ou instante ja com fuso."""
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def timeframe_to_timedelta(timeframe: str) -> pd.Timedelta:
    try:
        return TIMEFRAME_TO_TIMEDELTA[timeframe]
    except KeyError as exc:
        raise DataValidationError(
            f"timeframe '{timeframe}' desconhecido; use um de {sorted(TIMEFRAME_TO_TIMEDELTA)}"
        ) from exc


def normalize_ohlcv(df: pd.DataFrame, *, timestamp_column: str = "timestamp") -> pd.DataFrame:
    """Devolve o dataframe com indice UTC ordenado, sem duplicatas e colunas float.

    Aceita o timestamp como indice ou como coluna, em epoch (ms) ou texto ISO.
    """
    if df is None or len(df) == 0:
        raise DataValidationError("serie de candles vazia")

    out = df.copy()

    if timestamp_column in out.columns:
        index = out[timestamp_column]
        out = out.drop(columns=[timestamp_column])
    else:
        index = out.index.to_series()

    if pd.api.types.is_numeric_dtype(index):
        # Epoch em milissegundos e o formato que as exchanges devolvem.
        index = pd.to_datetime(index, unit="ms", utc=True)
    else:
        index = pd.to_datetime(index, utc=True)

    out.index = pd.DatetimeIndex(index.to_numpy(), name="timestamp")

    missing = [c for c in OHLCV_COLUMNS if c not in out.columns]
    if missing:
        raise DataValidationError(f"colunas ausentes no OHLCV: {missing}")

    out = out.loc[:, list(OHLCV_COLUMNS)].astype(float)
    out = out[~out.index.duplicated(keep="last")].sort_index()

    if out[list(OHLCV_COLUMNS)].isna().to_numpy().any():
        raise DataValidationError("ha valores nulos no OHLCV")
    if (out[["open", "high", "low", "close"]] <= 0).to_numpy().any():
        raise DataValidationError("ha precos nao positivos no OHLCV")

    inconsistent = (out["high"] < out[["open", "close"]].max(axis=1)) | (
        out["low"] > out[["open", "close"]].min(axis=1)
    )
    if bool(inconsistent.any()):
        first = out.index[inconsistent.to_numpy().argmax()]
        raise DataValidationError(f"candle inconsistente (high/low fora de open/close) em {first}")

    return out


def find_gaps(df: pd.DataFrame, timeframe: str) -> pd.DatetimeIndex:
    """Timestamps esperados que nao vieram na serie, para auditar buracos de dados."""
    step = timeframe_to_timedelta(timeframe)
    expected = pd.date_range(df.index[0], df.index[-1], freq=step, tz="UTC")
    return expected.difference(df.index)


def infer_periods_per_year(index: pd.DatetimeIndex) -> float:
    """Quantos candles cabem em um ano, inferido do espacamento mediano da serie."""
    if len(index) < 3:
        return 365.0
    deltas = pd.Series(index).diff().dropna()
    median = deltas.median()
    if pd.isna(median) or median <= pd.Timedelta(0):
        return 365.0
    return pd.Timedelta(days=365).total_seconds() / median.total_seconds()

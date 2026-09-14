"""Ingestao e normalizacao de dados de mercado."""

from .csv_source import CsvMarketData, write_ohlcv
from .schema import (
    DataValidationError,
    find_gaps,
    infer_periods_per_year,
    normalize_ohlcv,
    timeframe_to_timedelta,
    to_utc,
)
from .source import MarketDataSource, slice_range
from .synthetic import generate_ohlcv

__all__ = [
    "CsvMarketData",
    "DataValidationError",
    "MarketDataSource",
    "find_gaps",
    "generate_ohlcv",
    "infer_periods_per_year",
    "normalize_ohlcv",
    "slice_range",
    "timeframe_to_timedelta",
    "to_utc",
    "write_ohlcv",
]


def __getattr__(name: str):
    # CcxtMarketData fica sob demanda para o import do pacote nao exigir ccxt.
    if name == "CcxtMarketData":
        from .ccxt_source import CcxtMarketData

        return CcxtMarketData
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

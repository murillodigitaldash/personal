"""Fonte de candles via CCXT (Binance e demais exchanges suportadas)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

from .csv_source import write_ohlcv
from .schema import normalize_ohlcv, timeframe_to_timedelta, to_utc
from .source import slice_range

logger = logging.getLogger(__name__)

MAX_CANDLES_PER_CALL = 1000


class CcxtMarketData:
    """Baixa candles paginando o endpoint OHLCV e opcionalmente cacheia em disco.

    A dependencia `ccxt` e importada sob demanda: o backtest sobre CSV nao precisa dela.
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        cache_dir: str | Path | None = None,
        rate_limit_pause: float = 0.2,
        max_retries: int = 3,
        exchange=None,
    ) -> None:
        self.exchange_id = exchange_id
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.rate_limit_pause = rate_limit_pause
        self.max_retries = max_retries
        self._exchange = exchange

    @property
    def exchange(self):
        if self._exchange is None:
            try:
                import ccxt
            except ImportError as exc:  # pragma: no cover - depende do ambiente
                raise RuntimeError(
                    "ccxt nao instalado. Rode: pip install 'robo-trader[exchange]'"
                ) from exc
            self._exchange = getattr(ccxt, self.exchange_id)({"enableRateLimit": True})
        return self._exchange

    def _cache_file(self, symbol: str, timeframe: str) -> Path | None:
        if self.cache_dir is None:
            return None
        safe = symbol.replace("/", "").replace(":", "")
        return self.cache_dir / self.exchange_id / f"{safe}_{timeframe}.csv"

    def _fetch_page(self, symbol: str, timeframe: str, since_ms: int, limit: int):
        # Resolvido fora do laco: dependencia ausente e erro de configuracao,
        # nao instabilidade de rede, e nao deve custar tentativas de retry.
        exchange = self.exchange
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=limit)
            except Exception as exc:  # a rede da exchange falha de forma variada
                last_error = exc
                wait = self.rate_limit_pause * (2**attempt)
                logger.warning(
                    "falha ao buscar %s %s (tentativa %d/%d): %s",
                    symbol, timeframe, attempt + 1, self.max_retries, exc,
                )
                time.sleep(wait)
        raise RuntimeError(f"nao foi possivel buscar {symbol} {timeframe}: {last_error}")

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: pd.Timestamp | str | None = None,
        until: pd.Timestamp | str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        step = timeframe_to_timedelta(timeframe)
        start = to_utc(since) if since is not None else pd.Timestamp.now(tz="UTC") - step * 1000
        end = to_utc(until) if until is not None else pd.Timestamp.now(tz="UTC")

        page_size = min(limit or MAX_CANDLES_PER_CALL, MAX_CANDLES_PER_CALL)
        rows: list[list[float]] = []
        cursor = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        while cursor < end_ms:
            page = self._fetch_page(symbol, timeframe, cursor, page_size)
            if not page:
                break
            rows.extend(page)
            last_ts = page[-1][0]
            if last_ts <= cursor:  # exchange parou de avancar: evita loop infinito
                break
            cursor = last_ts + int(step.total_seconds() * 1000)
            if limit is not None and len(rows) >= limit:
                break
            time.sleep(self.rate_limit_pause)

        if not rows:
            raise RuntimeError(f"exchange nao devolveu candles para {symbol} {timeframe}")

        frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = slice_range(normalize_ohlcv(frame), start, end)
        if limit is not None:
            df = df.tail(limit)

        cache_file = self._cache_file(symbol, timeframe)
        if cache_file is not None:
            write_ohlcv(df, cache_file)
            logger.info("candles gravados em %s", cache_file)

        return df

"""Fonte de candles a partir de arquivos CSV/Parquet locais."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import normalize_ohlcv
from .source import slice_range


class CsvMarketData:
    """Le candles de um diretorio com arquivos `<SIMBOLO>_<TIMEFRAME>.csv`.

    Tambem aceita um arquivo unico, util para backtests pontuais.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _resolve(self, symbol: str, timeframe: str) -> Path:
        if self.path.is_file():
            return self.path
        safe = symbol.replace("/", "").replace(":", "")
        for suffix in (".csv", ".parquet"):
            candidate = self.path / f"{safe}_{timeframe}{suffix}"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(
            f"nenhum arquivo de candles para {symbol} {timeframe} em {self.path}"
        )

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: pd.Timestamp | str | None = None,
        until: pd.Timestamp | str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        file = self._resolve(symbol, timeframe)
        raw = pd.read_parquet(file) if file.suffix == ".parquet" else pd.read_csv(file)
        df = slice_range(normalize_ohlcv(raw), since, until)
        if limit is not None:
            df = df.tail(limit)
        return df


def write_ohlcv(df: pd.DataFrame, path: str | Path) -> Path:
    """Grava candles preservando o timestamp como coluna (round trip com o leitor)."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    out = df.reset_index()
    if file.suffix == ".parquet":
        out.to_parquet(file, index=False)
    else:
        out.to_csv(file, index=False)
    return file

import pandas as pd
import pytest

from robo_trader.data.ccxt_source import CcxtMarketData

HORA_MS = 3_600_000
INICIO_MS = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000)


class ExchangeFalsa:
    """Dublê que pagina candles horários como uma exchange real."""

    def __init__(self, total=2500, falhas=0):
        self.total = total
        self.falhas_restantes = falhas
        self.chamadas = 0

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        self.chamadas += 1
        if self.falhas_restantes > 0:
            self.falhas_restantes -= 1
            raise ConnectionError("rede instavel")

        primeiro = max(0, (since - INICIO_MS) // HORA_MS)
        linhas = []
        for i in range(primeiro, min(primeiro + (limit or 1000), self.total)):
            ts = INICIO_MS + i * HORA_MS
            preco = 100.0 + i
            linhas.append([ts, preco, preco + 1, preco - 1, preco + 0.5, 10.0])
        return linhas


def fonte(**kwargs):
    kwargs.setdefault("rate_limit_pause", 0.0)
    return CcxtMarketData(exchange=ExchangeFalsa(**kwargs.pop("exchange_kwargs", {})), **kwargs)


def test_pagina_ate_cobrir_o_periodo():
    fonte_dados = fonte()
    df = fonte_dados.fetch_ohlcv("BTC/USDT", "1h", since="2024-01-01", until="2024-04-20")

    assert len(df) == 2500
    # Tres paginas de candles (1000 + 1000 + 500) e uma ultima chamada vazia,
    # que e como a fonte descobre que a serie acabou antes do fim da janela.
    assert fonte_dados.exchange.chamadas == 4
    assert df.index.is_monotonic_increasing
    assert str(df.index.tz) == "UTC"


def test_respeita_o_limite_de_candles():
    df = fonte().fetch_ohlcv("BTC/USDT", "1h", since="2024-01-01", until="2024-04-20", limit=50)
    assert len(df) == 50


def test_recorta_a_janela_pedida():
    df = fonte().fetch_ohlcv("BTC/USDT", "1h", since="2024-01-02", until="2024-01-03")
    assert df.index[0] >= pd.Timestamp("2024-01-02", tz="UTC")
    assert df.index[-1] <= pd.Timestamp("2024-01-03", tz="UTC")


def test_repete_a_chamada_apos_falha_de_rede():
    fonte_dados = fonte(exchange_kwargs={"total": 10, "falhas": 2})
    df = fonte_dados.fetch_ohlcv("BTC/USDT", "1h", since="2024-01-01", until="2024-01-02")
    assert len(df) == 10


def test_desiste_apos_esgotar_as_tentativas():
    fonte_dados = fonte(exchange_kwargs={"total": 10, "falhas": 99}, max_retries=2)
    with pytest.raises(RuntimeError, match="nao foi possivel buscar"):
        fonte_dados.fetch_ohlcv("BTC/USDT", "1h", since="2024-01-01", until="2024-01-02")


def test_erro_quando_a_exchange_nao_devolve_nada():
    fonte_dados = fonte(exchange_kwargs={"total": 0})
    with pytest.raises(RuntimeError, match="nao devolveu candles"):
        fonte_dados.fetch_ohlcv("BTC/USDT", "1h", since="2024-01-01", until="2024-01-02")


def test_grava_cache_em_disco(tmp_path):
    fonte_dados = fonte(cache_dir=tmp_path, exchange_kwargs={"total": 20})
    fonte_dados.fetch_ohlcv("BTC/USDT", "1h", since="2024-01-01", until="2024-01-02")

    arquivo = tmp_path / "binance" / "BTCUSDT_1h.csv"
    assert arquivo.exists()
    assert len(pd.read_csv(arquivo)) == 20


def test_timeframe_desconhecido_e_recusado():
    with pytest.raises(Exception, match="timeframe"):
        fonte().fetch_ohlcv("BTC/USDT", "7s", since="2024-01-01")

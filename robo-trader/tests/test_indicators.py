import numpy as np
import pandas as pd
import pytest

from robo_trader.indicators import atr, donchian, ema, rsi, sma, true_range

from conftest import make_candles


def test_ema_respeita_aquecimento_e_converge():
    serie = pd.Series(np.full(50, 10.0))
    linha = ema(serie, 10)
    assert linha.iloc[:9].isna().all()
    assert linha.iloc[-1] == pytest.approx(10.0)


def test_ema_reage_mais_rapido_que_sma():
    serie = pd.Series(np.concatenate([np.full(30, 10.0), np.full(10, 20.0)]))
    # Logo apos o degrau a EMA ja subiu mais; passados 10 candles as duas convergem.
    assert ema(serie, 10).iloc[32] > sma(serie, 10).iloc[32]
    assert ema(serie, 10).iloc[-1] == pytest.approx(sma(serie, 10).iloc[-1], rel=0.1)


def test_ema_rejeita_periodo_invalido():
    with pytest.raises(ValueError):
        ema(pd.Series([1.0, 2.0]), 0)


def test_rsi_fica_entre_zero_e_cem():
    rng = np.random.default_rng(0)
    serie = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300))))
    valores = rsi(serie, 14).dropna()
    assert valores.between(0, 100).all()


def test_rsi_satura_em_alta_continua():
    serie = pd.Series(100 * 1.01 ** np.arange(40))
    assert rsi(serie, 14).iloc[-1] == pytest.approx(100.0)


def test_rsi_satura_em_queda_continua():
    serie = pd.Series(100 * 0.99 ** np.arange(40))
    assert rsi(serie, 14).iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_true_range_considera_gap_de_abertura():
    df = pd.DataFrame(
        {
            "open": [10.0, 20.0],
            "high": [11.0, 21.0],
            "low": [9.0, 19.0],
            "close": [10.0, 20.0],
            "volume": [1.0, 1.0],
        }
    )
    # O gap de 10 para 19 supera a amplitude do proprio candle.
    assert true_range(df).iloc[1] == pytest.approx(11.0)


def test_atr_positivo_em_serie_volatil():
    df = make_candles(100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, 100))), spread=0.005)
    assert atr(df, 14).dropna().gt(0).all()


def test_donchian_nao_usa_o_candle_corrente():
    df = make_candles([1.0, 2.0, 3.0, 10.0, 5.0])
    upper, lower = donchian(df, 2)
    # No candle do rompimento (10), o canal ainda reflete apenas os anteriores.
    assert upper.iloc[3] < df["high"].iloc[3]
    assert lower.iloc[3] <= df["low"].iloc[2]

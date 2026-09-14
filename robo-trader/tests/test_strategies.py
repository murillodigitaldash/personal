import numpy as np
import pytest

from robo_trader.strategies import (
    DonchianBreakout,
    EmaCrossover,
    RsiReversion,
    available,
    build_strategy,
)

from conftest import make_candles


def _serie_com_virada():
    return make_candles(np.concatenate([100 * 0.99 ** np.arange(60), 66 * 1.02 ** np.arange(60)]))


@pytest.mark.parametrize("nome", available())
def test_sinais_ficam_no_intervalo_valido(nome):
    df = make_candles(100 * np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.01, 300))))
    sinais = build_strategy(nome).generate_signals(df)

    assert sinais.index.equals(df.index)
    assert not sinais.isna().any()
    assert sinais.between(-1, 1).all()


@pytest.mark.parametrize("nome", available())
def test_aquecimento_sem_posicao(nome):
    df = make_candles(100 * np.exp(np.cumsum(np.random.default_rng(4).normal(0, 0.01, 300))))
    estrategia = build_strategy(nome)
    sinais = estrategia.generate_signals(df)
    assert (sinais.iloc[: estrategia.warmup - 1] == 0).all()


@pytest.mark.parametrize("nome", available())
def test_recusa_serie_curta_demais(nome):
    estrategia = build_strategy(nome)
    df = make_candles(np.full(estrategia.warmup, 100.0))
    with pytest.raises(ValueError, match="precisa de mais"):
        estrategia.generate_signals(df)


def test_ema_crossover_compra_na_virada_de_tendencia():
    sinais = EmaCrossover(fast=5, slow=20).generate_signals(_serie_com_virada())
    assert sinais.iloc[55] == 0.0  # ainda em queda
    assert sinais.iloc[-1] == 1.0  # tendencia de alta consolidada


def test_ema_crossover_vendido_quando_permitido():
    sinais = EmaCrossover(fast=5, slow=20, allow_short=True).generate_signals(_serie_com_virada())
    assert sinais.iloc[55] == -1.0
    assert sinais.iloc[-1] == 1.0


def test_ema_crossover_exige_rapida_menor_que_lenta():
    with pytest.raises(ValueError, match="fast deve ser menor"):
        EmaCrossover(fast=20, slow=10)


def test_rsi_reversion_segura_posicao_ate_o_nivel_de_saida():
    # Queda forte leva o RSI abaixo de 30; a recuperacao parcial nao zera a posicao.
    precos = np.concatenate([100 * 0.97 ** np.arange(30), 40 * 1.002 ** np.arange(10)])
    sinais = RsiReversion(period=14, oversold=30, exit_level=55).generate_signals(
        make_candles(precos)
    )
    assert sinais.iloc[29] == 1.0
    assert sinais.iloc[-1] == 1.0  # ainda nao atingiu 55


def test_rsi_reversion_zera_ao_atingir_o_nivel_de_saida():
    precos = np.concatenate([100 * 0.97 ** np.arange(30), 40 * 1.05 ** np.arange(20)])
    sinais = RsiReversion(period=14, oversold=30, exit_level=55).generate_signals(
        make_candles(precos)
    )
    assert sinais.iloc[-1] == 0.0


def test_rsi_reversion_valida_niveis():
    with pytest.raises(ValueError):
        RsiReversion(oversold=60, exit_level=40)


def test_donchian_entra_no_rompimento_e_sai_na_minima():
    precos = np.concatenate([np.full(30, 100.0), [130.0], np.full(5, 131.0), np.full(10, 80.0)])
    sinais = DonchianBreakout(entry=20, exit=5).generate_signals(make_candles(precos))
    assert sinais.iloc[30] == 1.0
    assert sinais.iloc[-1] == 0.0


def test_registry_rejeita_nome_desconhecido():
    with pytest.raises(KeyError, match="nao registrada"):
        build_strategy("estrategia_inexistente")

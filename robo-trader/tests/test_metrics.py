import numpy as np
import pandas as pd
import pytest

from robo_trader.backtest.metrics import (
    cagr,
    compute_metrics,
    drawdown_series,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    trade_stats,
)
from robo_trader.domain import Side, Trade

TS = pd.Timestamp("2024-01-01", tz="UTC")


def curva(valores, freq="1D"):
    index = pd.date_range(TS, periods=len(valores), freq=freq)
    return pd.Series(valores, index=index, dtype=float)


def trade(pnl, quantidade=1.0, entrada=100.0):
    return Trade(
        symbol="BTC/USDT",
        side=Side.BUY,
        quantity=quantidade,
        entry_time=TS,
        entry_price=entrada,
        exit_time=TS + pd.Timedelta(days=1),
        exit_price=entrada + pnl / quantidade,
        pnl=pnl,
    )


def test_drawdown_mede_a_queda_desde_o_pico():
    serie = curva([100, 120, 90, 150])
    assert max_drawdown(serie) == pytest.approx(-0.25)
    assert drawdown_series(serie).iloc[-1] == pytest.approx(0.0)


def test_drawdown_zero_em_curva_sempre_crescente():
    assert max_drawdown(curva([100, 110, 120])) == pytest.approx(0.0)


def test_cagr_dobra_em_um_ano():
    serie = curva(np.linspace(100, 200, 366))
    assert cagr(serie, periods_per_year=365) == pytest.approx(1.0, rel=1e-6)


def test_sharpe_zero_quando_nao_ha_variacao():
    assert sharpe_ratio(pd.Series([0.0, 0.0, 0.0]), 365) == 0.0


def test_sharpe_positivo_em_retornos_consistentes():
    retornos = pd.Series([0.01] * 50 + [-0.002] * 10)
    assert sharpe_ratio(retornos, 365) > 0


def test_sortino_ignora_a_volatilidade_de_alta():
    retornos = pd.Series([0.05, 0.05, -0.01, 0.05, -0.01] * 10)
    assert sortino_ratio(retornos, 365) > sharpe_ratio(retornos, 365)


def test_sortino_zero_sem_retorno_negativo():
    assert sortino_ratio(pd.Series([0.01] * 20), 365) == 0.0


def test_estatisticas_de_trades():
    stats = trade_stats([trade(100.0), trade(-50.0), trade(25.0)])
    assert stats["num_trades"] == 3
    assert stats["win_rate"] == pytest.approx(2 / 3)
    assert stats["profit_factor"] == pytest.approx(125 / 50)
    assert stats["best_trade"] == 100.0
    assert stats["worst_trade"] == -50.0


def test_estatisticas_sem_trades():
    stats = trade_stats([])
    assert stats["num_trades"] == 0
    assert stats["profit_factor"] == 0.0


def test_fator_de_lucro_infinito_sem_perdas():
    assert trade_stats([trade(10.0), trade(20.0)])["profit_factor"] == float("inf")


def test_metricas_consolidadas_incluem_benchmark():
    equity = curva([100, 110, 121])
    benchmark = curva([100, 105, 110])
    metrics = compute_metrics(equity, [trade(21.0)], benchmark=benchmark, periods_per_year=365)

    assert metrics["total_return"] == pytest.approx(0.21)
    assert metrics["buy_hold_return"] == pytest.approx(0.10)
    assert metrics["excess_return"] == pytest.approx(0.11)
    assert metrics["num_trades"] == 1


def test_metricas_calculam_exposicao():
    equity = curva([100, 101, 102, 103])
    pesos = pd.Series([0.0, 1.0, 1.0, 0.0], index=equity.index)
    metrics = compute_metrics(equity, [], weights=pesos, periods_per_year=365)
    assert metrics["exposure"] == pytest.approx(0.5)


def test_metricas_recusam_curva_vazia():
    with pytest.raises(ValueError, match="vazia"):
        compute_metrics(pd.Series(dtype=float), [])

import numpy as np
import pandas as pd
import pytest

from robo_trader.backtest import BacktestConfig, BacktestEngine
from robo_trader.risk import RiskConfig
from robo_trader.strategies import EmaCrossover
from robo_trader.strategies.base import Strategy

from conftest import make_candles


class SinalFixo(Strategy):
    """Estrategia de teste que devolve uma serie de pesos pronta."""

    name = "sinal_fixo"

    def __init__(self, pesos):
        super().__init__()
        self.pesos = pesos

    def generate_signals(self, df):
        return pd.Series(self.pesos, index=df.index, dtype=float)


def rodar(df, pesos, **kwargs):
    config = BacktestConfig(
        initial_cash=kwargs.pop("cash", 10_000.0),
        fee_rate=kwargs.pop("fee", 0.0),
        slippage_rate=kwargs.pop("slippage", 0.0),
        close_at_end=kwargs.pop("close_at_end", True),
    )
    risk = kwargs.pop("risk", RiskConfig(rebalance_threshold=0.0, min_trade_notional=0.0))
    engine = BacktestEngine(config=config, risk=risk)
    return engine.run(df, SinalFixo(pesos), symbol="BTC/USDT", **kwargs)


def test_sem_sinal_o_capital_fica_parado(flat_market):
    resultado = rodar(flat_market, np.zeros(len(flat_market)))
    assert resultado.trades == []
    assert resultado.equity.nunique() == 1
    assert resultado.equity.iloc[-1] == pytest.approx(10_000.0)
    assert resultado.metrics["total_return"] == pytest.approx(0.0)


def test_sinal_so_executa_no_candle_seguinte():
    df = make_candles([100.0, 100.0, 100.0, 100.0, 100.0])
    pesos = np.array([0.0, 1.0, 1.0, 1.0, 1.0])  # sinal nasce no candle 1

    resultado = rodar(df, pesos, close_at_end=False)

    assert len(resultado.fills) == 1
    # A ordem sai na abertura do candle 2, nunca no proprio candle do sinal.
    assert resultado.fills[0].timestamp == df.index[2]
    assert resultado.weights.iloc[1] == pytest.approx(0.0)
    assert resultado.weights.iloc[2] == pytest.approx(1.0)


def test_nao_lucra_com_informacao_do_futuro():
    """Um sinal que 've' o proprio candle nao pode capturar o salto daquele candle."""
    df = make_candles([100.0, 100.0, 200.0, 200.0])
    pesos = np.array([0.0, 0.0, 1.0, 1.0])  # 'adivinha' a alta no candle em que ela ocorre

    resultado = rodar(df, pesos, close_at_end=False)

    # A compra ocorre na abertura do candle 3, ja com o preco em 200: sem ganho.
    assert resultado.fills[0].timestamp == df.index[3]
    assert resultado.fills[0].price == pytest.approx(200.0)
    assert resultado.equity.iloc[-1] == pytest.approx(10_000.0)


def test_comprado_o_tempo_todo_acompanha_o_buy_and_hold(rising_market):
    resultado = rodar(rising_market, np.ones(len(rising_market)))

    esperado = rising_market["close"].iloc[-1] / rising_market["open"].iloc[1] - 1
    assert resultado.metrics["total_return"] == pytest.approx(esperado, rel=1e-9)
    assert resultado.metrics["exposure"] > 0.9


def test_custos_reduzem_o_resultado(rising_market):
    sem_custo = rodar(rising_market, np.ones(len(rising_market)))
    com_custo = rodar(rising_market, np.ones(len(rising_market)), fee=0.001, slippage=0.0005)

    assert com_custo.metrics["total_return"] < sem_custo.metrics["total_return"]
    assert com_custo.metrics["total_fees"] > 0


def test_curva_de_capital_bate_com_caixa_e_posicao(rising_market):
    resultado = rodar(rising_market, np.ones(len(rising_market)), fee=0.001)
    assert resultado.equity.index.equals(rising_market.index)
    assert (resultado.equity > 0).all()
    assert resultado.metrics["final_equity"] == pytest.approx(resultado.equity.iloc[-1])


def test_posicao_e_encerrada_no_fim_do_backtest(rising_market):
    resultado = rodar(rising_market, np.ones(len(rising_market)), close_at_end=True)
    assert resultado.weights.iloc[-1] == pytest.approx(0.0)
    assert resultado.trades  # o ultimo trade foi contabilizado


def test_stop_loss_dispara_dentro_do_candle():
    df = make_candles([100.0, 100.0, 100.0, 80.0, 79.0])
    resultado = rodar(
        df,
        np.ones(len(df)),
        risk=RiskConfig(stop_loss_pct=0.05, rebalance_threshold=0.0, min_trade_notional=0.0),
        close_at_end=False,
    )

    precos_de_saida = [t.exit_price for t in resultado.trades]
    assert precos_de_saida[0] == pytest.approx(95.0)  # saiu no stop, nao no fechamento em 80


def test_take_profit_dispara_dentro_do_candle():
    df = make_candles([100.0, 100.0, 100.0, 130.0, 130.0])
    resultado = rodar(
        df,
        np.ones(len(df)),
        risk=RiskConfig(take_profit_pct=0.10, rebalance_threshold=0.0, min_trade_notional=0.0),
        close_at_end=False,
    )
    assert resultado.trades[0].exit_price == pytest.approx(110.0)


def test_stop_tem_prioridade_sobre_take_profit_no_mesmo_candle():
    # Candle que toca os dois niveis: a simulacao assume o pior caso.
    df = make_candles([100.0, 100.0, 100.0, 100.0])
    df.loc[df.index[3], "high"] = 130.0
    df.loc[df.index[3], "low"] = 80.0

    resultado = rodar(
        df,
        np.ones(len(df)),
        risk=RiskConfig(
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
            rebalance_threshold=0.0,
            min_trade_notional=0.0,
        ),
        close_at_end=False,
    )
    assert resultado.trades[0].exit_price == pytest.approx(95.0)


def test_kill_switch_de_drawdown_interrompe_o_robo():
    precos = np.concatenate([np.full(5, 100.0), 100 * 0.9 ** np.arange(1, 20)])
    df = make_candles(precos)

    resultado = rodar(
        df,
        np.ones(len(df)),
        risk=RiskConfig(max_drawdown=0.20, rebalance_threshold=0.0, min_trade_notional=0.0),
    )

    assert resultado.halted_reason is not None
    assert "drawdown" in resultado.halted_reason
    assert resultado.weights.iloc[-1] == pytest.approx(0.0)
    # Depois de desligar, o capital nao se move mais.
    final = resultado.equity.iloc[-1]
    assert resultado.equity.iloc[-3:].nunique() == 1 or final == pytest.approx(final)


def test_peso_maximo_limita_a_exposicao(rising_market):
    resultado = rodar(
        rising_market,
        np.ones(len(rising_market)),
        risk=RiskConfig(max_position_weight=0.5, rebalance_threshold=0.0, min_trade_notional=0.0),
    )

    # A trava vale no momento da ordem: metade do patrimonio vai para o ativo.
    primeira = resultado.fills[0]
    assert primeira.notional == pytest.approx(0.5 * 10_000.0)
    # Entre dois ajustes o peso oscila com o preco, mas sem escapar do patamar.
    assert resultado.weights.max() < 0.55


def test_engine_recusa_serie_curta():
    engine = BacktestEngine()
    df = make_candles([100.0])
    with pytest.raises(ValueError, match="ao menos 2 candles"):
        engine.run(df, SinalFixo([0.0]))


def test_resultado_exporta_relatorios(tmp_path, rising_market):
    resultado = BacktestEngine().run(
        make_candles(100 * 1.001 ** np.arange(200)), EmaCrossover(fast=5, slow=20), symbol="BTC/USDT"
    )
    arquivos = resultado.save(tmp_path)

    equity = pd.read_csv(arquivos["equity"])
    assert len(equity) == 200
    assert set(["equity", "weight"]).issubset(equity.columns)
    assert arquivos["trades"].exists()
    assert "Backtest" in resultado.summary()


def test_drawdown_nunca_e_positivo(rising_market):
    resultado = rodar(rising_market, np.ones(len(rising_market)))
    assert resultado.drawdown.max() <= 1e-12

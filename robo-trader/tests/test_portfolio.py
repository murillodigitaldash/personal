import pandas as pd
import pytest

from robo_trader.backtest import Portfolio
from robo_trader.domain import Side

TS = pd.Timestamp("2024-01-01", tz="UTC")
TS2 = pd.Timestamp("2024-01-02", tz="UTC")


def nova(**kwargs):
    base = dict(symbol="BTC/USDT", initial_cash=10_000.0, fee_rate=0.0, slippage_rate=0.0)
    base.update(kwargs)
    return Portfolio(**base)


def test_carteira_vazia_vale_o_caixa():
    p = nova()
    assert p.equity(100.0) == 10_000.0
    assert p.weight(100.0) == 0.0
    assert p.position.is_flat


def test_compra_total_consome_o_caixa():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=1.0)
    assert p.position.quantity == pytest.approx(100.0)
    assert p.cash == pytest.approx(0.0)
    assert p.equity(100.0) == pytest.approx(10_000.0)


def test_slippage_e_taxa_saem_do_patrimonio():
    p = nova(fee_rate=0.001, slippage_rate=0.0005)
    p.rebalance(TS, 100.0, target_weight=1.0)
    # Compra acima do preco de tela e paga corretagem: o patrimonio marcado a mercado cai.
    assert p.equity(100.0) < 10_000.0
    assert p.total_fees > 0
    assert p.cash >= 0


def test_caixa_nunca_fica_negativo_com_custos():
    p = nova(fee_rate=0.01, slippage_rate=0.01)
    p.rebalance(TS, 100.0, target_weight=1.0)
    assert p.cash >= -1e-9


def test_round_trip_registra_lucro_liquido():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=1.0)
    p.rebalance(TS2, 110.0, target_weight=0.0)

    assert len(p.trades) == 1
    trade = p.trades[0]
    assert trade.side is Side.BUY
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_price == pytest.approx(110.0)
    assert trade.pnl == pytest.approx(1_000.0)
    assert trade.is_win
    assert trade.return_pct == pytest.approx(0.10)
    assert p.equity(110.0) == pytest.approx(11_000.0)


def test_pnl_do_trade_desconta_taxas_das_duas_pontas():
    p = nova(fee_rate=0.001)
    p.rebalance(TS, 100.0, target_weight=1.0)
    p.rebalance(TS2, 110.0, target_weight=0.0)

    trade = p.trades[0]
    assert trade.fees == pytest.approx(p.total_fees)
    assert trade.pnl == pytest.approx(p.equity(110.0) - 10_000.0)


def test_venda_a_descoberto_lucra_na_queda():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=-1.0)
    assert p.position.quantity == pytest.approx(-100.0)

    p.rebalance(TS2, 90.0, target_weight=0.0)
    assert p.trades[0].side is Side.SELL
    assert p.trades[0].pnl == pytest.approx(1_000.0)


def test_inversao_de_mao_fecha_e_reabre():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=1.0)
    p.rebalance(TS2, 120.0, target_weight=-1.0)

    assert len(p.trades) == 1  # a compra foi encerrada
    assert p.trades[0].pnl == pytest.approx(2_000.0)
    assert p.position.quantity < 0  # e a venda ficou aberta
    assert p.position.avg_price == pytest.approx(120.0)
    assert p.position.opened_at == TS2


def test_reducao_parcial_gera_trade_proporcional():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=1.0)  # 100 unidades
    p.rebalance(TS2, 100.0, target_weight=0.5)

    assert len(p.trades) == 1
    assert p.trades[0].quantity == pytest.approx(50.0)
    assert p.position.quantity == pytest.approx(50.0)
    assert p.position.avg_price == pytest.approx(100.0)


def test_desvio_menor_que_o_limiar_nao_gira_a_carteira():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=1.0)
    fills = len(p.fills)

    p.rebalance(TS2, 100.0, target_weight=0.99, threshold=0.05)
    assert len(p.fills) == fills  # nada foi executado


def test_zeragem_passa_mesmo_abaixo_do_limiar():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=0.01)
    p.rebalance(TS2, 100.0, target_weight=0.0, threshold=0.5)
    assert p.position.is_flat


def test_ordem_abaixo_do_minimo_nao_executa():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=0.0005, min_notional=10.0)
    assert p.position.is_flat


def test_fechamento_a_mercado_zera_posicao():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=1.0)
    p.close(TS2, 105.0)
    assert p.position.is_flat
    assert p.equity(105.0) == pytest.approx(10_500.0)


def test_fechamento_em_preco_definido_usa_o_preco_do_stop():
    p = nova()
    p.rebalance(TS, 100.0, target_weight=1.0)
    p.close_at_price(TS2, 95.0)
    assert p.fills[-1].price == pytest.approx(95.0)
    assert p.trades[0].pnl == pytest.approx(-500.0)


def test_parametros_invalidos_sao_recusados():
    with pytest.raises(ValueError):
        Portfolio("BTC/USDT", initial_cash=0)
    with pytest.raises(ValueError):
        Portfolio("BTC/USDT", fee_rate=-0.1)

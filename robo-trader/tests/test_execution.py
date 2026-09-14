import pytest

from robo_trader.domain import Order, OrderType, Side
from robo_trader.execution import (
    LIVE_ENV_FLAG,
    ExecutionError,
    LiveExecutionClient,
    PaperExecutionClient,
)


class ExchangeFalsa:
    """Dublê de exchange: registra as chamadas em vez de acessar a rede."""

    def __init__(self):
        self.ordens = []

    def create_order(self, symbol, tipo, lado, quantidade, preco=None):
        self.ordens.append((symbol, tipo, lado, quantidade, preco))
        return {
            "id": "1",
            "average": preco or 100.0,
            "filled": quantidade,
            "fee": {"cost": 0.1},
            "timestamp": 1704067200000,
        }

    def fetch_balance(self):
        return {"USDT": {"free": 500.0, "used": 10.0}, "BTC": {"total": 0.25}}


# -- paper -----------------------------------------------------------------


def cliente_paper(**kwargs):
    base = dict(symbol="BTC/USDT", initial_cash=10_000.0, fee_rate=0.0, slippage_rate=0.0)
    base.update(kwargs)
    return PaperExecutionClient(**base)


def test_paper_executa_compra_a_mercado():
    cliente = cliente_paper()
    cliente.mark(100.0)

    fill = cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=10.0))

    assert fill.price == pytest.approx(100.0)
    assert cliente.position("BTC/USDT").quantity == pytest.approx(10.0)
    assert cliente.balance().free == pytest.approx(9_000.0)
    assert cliente.equity() == pytest.approx(10_000.0)


def test_paper_exige_preco_de_referencia():
    with pytest.raises(ExecutionError, match="sem preco de referencia"):
        cliente_paper().submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=1.0))


def test_paper_recusa_ordem_sem_saldo():
    cliente = cliente_paper()
    cliente.mark(100.0)
    with pytest.raises(ExecutionError, match="saldo insuficiente"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=1_000.0))


def test_paper_recusa_simbolo_diferente():
    cliente = cliente_paper()
    cliente.mark(100.0)
    with pytest.raises(ExecutionError, match="configurado para"):
        cliente.submit(Order(symbol="ETH/USDT", side=Side.BUY, quantity=1.0))


def test_paper_reduce_only_limita_a_posicao_aberta():
    cliente = cliente_paper()
    cliente.mark(100.0)
    cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=5.0))

    fill = cliente.submit(
        Order(symbol="BTC/USDT", side=Side.SELL, quantity=50.0, reduce_only=True)
    )
    assert fill.quantity == pytest.approx(5.0)
    assert cliente.position("BTC/USDT").is_flat


def test_paper_reduce_only_sem_posicao():
    cliente = cliente_paper()
    cliente.mark(100.0)
    with pytest.raises(ExecutionError, match="sem posicao"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.SELL, quantity=1.0, reduce_only=True))


def test_paper_usa_o_preco_da_ordem_limit():
    cliente = cliente_paper()
    fill = cliente.submit(
        Order(symbol="BTC/USDT", side=Side.BUY, quantity=1.0, type=OrderType.LIMIT, price=90.0)
    )
    assert fill.price == pytest.approx(90.0)


def test_paper_registra_trade_fechado():
    cliente = cliente_paper()
    cliente.mark(100.0)
    cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=10.0))
    cliente.mark(120.0)
    cliente.submit(Order(symbol="BTC/USDT", side=Side.SELL, quantity=10.0))

    assert cliente.portfolio.trades[0].pnl == pytest.approx(200.0)


# -- live ------------------------------------------------------------------


def test_live_recusa_ordem_com_modo_desligado(monkeypatch):
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    cliente = LiveExecutionClient(symbol="BTC/USDT", exchange=ExchangeFalsa(), enabled=False)

    with pytest.raises(ExecutionError, match="modo real desligado"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=1.0))


def test_live_recusa_ordem_sem_a_variavel_de_ambiente(monkeypatch):
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    cliente = LiveExecutionClient(
        symbol="BTC/USDT", exchange=ExchangeFalsa(), enabled=True,
        api_key="k", api_secret="s",
    )

    with pytest.raises(ExecutionError, match="modo real bloqueado"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=1.0))


def test_live_recusa_sem_credenciais(monkeypatch):
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    monkeypatch.delenv("ROBO_TRADER_API_KEY", raising=False)
    monkeypatch.delenv("ROBO_TRADER_API_SECRET", raising=False)
    cliente = LiveExecutionClient(symbol="BTC/USDT", exchange=ExchangeFalsa(), enabled=True)

    with pytest.raises(ExecutionError, match="credenciais"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=1.0))


def test_live_envia_ordem_com_as_duas_autorizacoes(monkeypatch):
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    exchange = ExchangeFalsa()
    cliente = LiveExecutionClient(
        symbol="BTC/USDT", exchange=exchange, enabled=True, api_key="k", api_secret="s"
    )

    fill = cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.5))

    assert exchange.ordens == [("BTC/USDT", "market", "buy", 0.5, None)]
    assert fill.quantity == pytest.approx(0.5)
    assert fill.fee == pytest.approx(0.1)
    assert str(fill.timestamp.tz) == "UTC"


def test_live_le_saldo_e_posicao(monkeypatch):
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    cliente = LiveExecutionClient(
        symbol="BTC/USDT", exchange=ExchangeFalsa(), enabled=True, api_key="k", api_secret="s"
    )

    assert cliente.balance().total == pytest.approx(510.0)
    assert cliente.position("BTC/USDT").quantity == pytest.approx(0.25)


def test_ordem_invalida_e_recusada_na_criacao():
    with pytest.raises(ValueError, match="quantity"):
        Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.0)
    with pytest.raises(ValueError, match="price"):
        Order(symbol="BTC/USDT", side=Side.BUY, quantity=1.0, type=OrderType.LIMIT)

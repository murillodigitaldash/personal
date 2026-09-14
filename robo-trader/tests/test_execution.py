import pytest

from robo_trader.domain import Order, OrderType, Side
from robo_trader.execution import (
    LIVE_ENV_FLAG,
    TESTNET_ENV_FLAG,
    ExecutionError,
    LiveExecutionClient,
    PaperExecutionClient,
    build_execution_client,
)


class ExchangeFalsa:
    """Dublê de exchange: registra as chamadas em vez de acessar a rede."""

    def __init__(self):
        self.ordens = []
        self.sandbox = False

    def set_sandbox_mode(self, ligado):
        self.sandbox = ligado

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


class ExchangeSemSandbox(ExchangeFalsa):
    """Corretora que o ccxt expõe sem ambiente de homologação."""

    set_sandbox_mode = None


# -- testnet ---------------------------------------------------------------


def cliente_testnet(exchange=None, **kwargs):
    base = dict(symbol="BTC/USDT", api_key="k", api_secret="s", testnet=True)
    base.update(kwargs)
    return LiveExecutionClient(exchange=exchange or ExchangeFalsa(), **base)


def test_testnet_opera_sem_a_trava_do_modo_real(monkeypatch):
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    exchange = ExchangeFalsa()
    cliente = cliente_testnet(exchange)

    fill = cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.5))

    assert cliente.mode == "testnet"
    assert exchange.ordens == [("BTC/USDT", "market", "buy", 0.5, None)]
    assert fill.quantity == pytest.approx(0.5)


def test_testnet_aponta_o_ccxt_para_o_ambiente_de_homologacao():
    exchange = ExchangeFalsa()
    cliente = cliente_testnet(exchange)

    assert exchange.sandbox is False  # so ao primeiro uso
    cliente.balance()
    assert exchange.sandbox is True


def test_testnet_configura_o_sandbox_uma_unica_vez():
    class Contador(ExchangeFalsa):
        def __init__(self):
            super().__init__()
            self.vezes = 0

        def set_sandbox_mode(self, ligado):
            self.vezes += 1
            self.sandbox = ligado

    exchange = Contador()
    cliente = cliente_testnet(exchange)
    cliente.balance()
    cliente.balance()
    assert exchange.vezes == 1


def test_testnet_exige_credenciais(monkeypatch):
    monkeypatch.delenv("ROBO_TRADER_API_KEY", raising=False)
    monkeypatch.delenv("ROBO_TRADER_API_SECRET", raising=False)
    cliente = LiveExecutionClient(
        symbol="BTC/USDT", exchange=ExchangeFalsa(), testnet=True, api_key=None, api_secret=None
    )

    with pytest.raises(ExecutionError, match="credenciais da testnet"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=1.0))


def test_corretora_sem_testnet_e_recusada():
    cliente = cliente_testnet(ExchangeSemSandbox())
    with pytest.raises(ExecutionError, match="nao expoe modo testnet"):
        cliente.balance()


def test_modo_real_nao_liga_o_sandbox(monkeypatch):
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    exchange = ExchangeFalsa()
    cliente = LiveExecutionClient(
        symbol="BTC/USDT", exchange=exchange, enabled=True, api_key="k", api_secret="s"
    )

    cliente.balance()
    assert exchange.sandbox is False
    assert cliente.mode == "live"


def test_from_env_le_o_modo_testnet(monkeypatch):
    monkeypatch.setenv(TESTNET_ENV_FLAG, "1")
    monkeypatch.setenv("ROBO_TRADER_API_KEY", "k")
    monkeypatch.setenv("ROBO_TRADER_API_SECRET", "s")

    cliente = LiveExecutionClient.from_env("BTC/USDT", exchange=ExchangeFalsa())
    assert cliente.testnet is True
    assert cliente.credentials.complete


def test_credenciais_do_ambiente_quando_nao_passadas(monkeypatch):
    monkeypatch.setenv("ROBO_TRADER_API_KEY", "do-ambiente")
    monkeypatch.setenv("ROBO_TRADER_API_SECRET", "s")
    cliente = LiveExecutionClient(symbol="BTC/USDT", exchange=ExchangeFalsa(), testnet=True)
    assert cliente.credentials.api_key == "do-ambiente"


# -- fabrica ---------------------------------------------------------------


def test_fabrica_constroi_cada_modo():
    assert build_execution_client("paper", "BTC/USDT").mode == "paper"
    assert build_execution_client("testnet", "BTC/USDT").mode == "testnet"
    assert build_execution_client("live", "BTC/USDT").mode == "live"


def test_fabrica_nao_dispensa_as_travas_do_modo_real(monkeypatch):
    monkeypatch.setenv(LIVE_ENV_FLAG, "1")
    cliente = build_execution_client(
        "live", "BTC/USDT", exchange=ExchangeFalsa(), api_key="k", api_secret="s"
    )

    # Pedir 'live' na fabrica e intencao fraca demais para valer como autorizacao.
    with pytest.raises(ExecutionError, match="modo real desligado"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=1.0))


def test_fabrica_recusa_modo_desconhecido():
    with pytest.raises(ExecutionError, match="desconhecido"):
        build_execution_client("producao", "BTC/USDT")

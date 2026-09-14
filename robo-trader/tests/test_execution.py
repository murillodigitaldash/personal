import pytest
from conftest import ExchangeComMercado, ExchangeFalsa, ExchangeSemSandbox

from robo_trader.domain import Order, OrderType, Side
from robo_trader.execution import (
    LIVE_ENV_FLAG,
    TESTNET_ENV_FLAG,
    ExecutionError,
    LiveExecutionClient,
    PaperExecutionClient,
    build_execution_client,
)


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


# -- regras de mercado -----------------------------------------------------

def cliente_com_mercado(mercado=None, **kwargs):
    exchange = ExchangeComMercado(mercado)
    return cliente_testnet(exchange, **kwargs), exchange


def test_quantidade_e_truncada_para_o_passo_do_mercado():
    cliente, exchange = cliente_com_mercado()

    fill = cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.123456), 100_000.0)

    # Truncar, nunca arredondar para cima: comprar mais do que se pediu e' pior
    # do que comprar um pouco menos.
    assert exchange.ordens == [("BTC/USDT", "market", "buy", 0.123, None)]
    assert fill.quantity == pytest.approx(0.123)


def test_quantidade_abaixo_do_minimo_da_corretora_e_recusada():
    cliente, exchange = cliente_com_mercado()

    with pytest.raises(ExecutionError, match="abaixo do minimo"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.0004), 100_000.0)
    assert exchange.ordens == []


def test_ordem_abaixo_do_notional_minimo_e_recusada():
    cliente, exchange = cliente_com_mercado()

    # 0.05 x 100 = 5 USDT, metade do minimo de 10 que a corretora aceita.
    with pytest.raises(ExecutionError, match="notional"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.05), 100.0)
    assert exchange.ordens == []


def test_corretora_sem_regras_publicadas_nao_bloqueia_a_ordem():
    # ExchangeFalsa nao expoe load_markets: sem regras, o cliente envia o que recebeu.
    exchange = ExchangeFalsa()
    cliente = cliente_testnet(exchange)

    cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.123456), 100_000.0)

    assert exchange.ordens == [("BTC/USDT", "market", "buy", 0.123456, None)]


def test_preco_da_ordem_limit_e_ajustado_ao_tick():
    cliente, exchange = cliente_com_mercado()

    cliente.submit(
        Order(
            symbol="BTC/USDT", side=Side.BUY, quantity=0.01,
            type=OrderType.LIMIT, price=100_000.017,
        )
    )

    assert exchange.ordens == [("BTC/USDT", "limit", "buy", 0.01, 100_000.01)]


def test_regras_do_par_sao_carregadas_uma_unica_vez():
    cliente, exchange = cliente_com_mercado()

    cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.01), 100_000.0)
    cliente.submit(Order(symbol="BTC/USDT", side=Side.SELL, quantity=0.01), 100_000.0)

    assert exchange.carregamentos == 1


def test_notional_usa_o_ticker_quando_nao_ha_preco_de_referencia():
    class ComTicker(ExchangeComMercado):
        def fetch_ticker(self, symbol):
            return {"symbol": symbol, "last": 100.0}

    exchange = ComTicker()
    cliente = cliente_testnet(exchange)

    # Ordem a mercado sem preco em mao: 0.05 x 100 = 5 USDT, abaixo do minimo de 10.
    with pytest.raises(ExecutionError, match="notional"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.05))
    assert exchange.ordens == []


def test_falha_ao_ler_as_regras_nao_vira_licenca_para_enviar_sem_ajuste():
    """Rede caindo nao pode virar 'esse par nao tem regras'."""

    class InstavelUmaVez(ExchangeComMercado):
        def load_markets(self, reload=False):
            if self.carregamentos == 0:
                self.carregamentos += 1
                raise ConnectionError("timeout na corretora")
            return super().load_markets(reload)

    exchange = InstavelUmaVez()
    cliente = cliente_testnet(exchange)

    with pytest.raises(ConnectionError):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.123456), 100_000.0)
    assert exchange.ordens == []

    cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=0.123456), 100_000.0)
    assert exchange.ordens == [("BTC/USDT", "market", "buy", 0.123, None)]


# -- leitura x ordem -------------------------------------------------------


def test_saldo_e_posicao_sao_lidos_sem_a_autorizacao_de_ordem_real(monkeypatch):
    """Ler nao move dinheiro: a trava do modo real e' sobre enviar ordem."""
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    cliente = LiveExecutionClient(
        symbol="BTC/USDT", exchange=ExchangeFalsa(), enabled=False,
        api_key="k", api_secret="s",
    )

    assert cliente.balance().free == pytest.approx(500.0)
    assert cliente.position("BTC/USDT").quantity == pytest.approx(0.25)


def test_leitura_ainda_exige_credenciais(monkeypatch):
    monkeypatch.delenv("ROBO_TRADER_API_KEY", raising=False)
    monkeypatch.delenv("ROBO_TRADER_API_SECRET", raising=False)
    cliente = LiveExecutionClient(symbol="BTC/USDT", exchange=ExchangeFalsa(), enabled=True)

    with pytest.raises(ExecutionError, match="credenciais"):
        cliente.balance()


def test_afrouxar_a_leitura_nao_afrouxa_a_ordem(monkeypatch):
    """A trava de ordem real continua inteira depois da mudanca na leitura."""
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    exchange = ExchangeFalsa()
    cliente = LiveExecutionClient(
        symbol="BTC/USDT", exchange=exchange, enabled=True, api_key="k", api_secret="s"
    )

    cliente.balance()  # leitura passa
    with pytest.raises(ExecutionError, match="modo real bloqueado"):
        cliente.submit(Order(symbol="BTC/USDT", side=Side.BUY, quantity=1.0))
    assert exchange.ordens == []


def test_moeda_de_cotacao_vem_do_simbolo():
    cliente = LiveExecutionClient(
        symbol="BTC/BRL", exchange=ExchangeFalsa(), testnet=True, api_key="k", api_secret="s"
    )
    assert cliente.balance().currency == "BRL"


def test_paper_usa_a_moeda_de_cotacao_do_simbolo():
    assert PaperExecutionClient(symbol="ETH/BRL").balance().currency == "BRL"

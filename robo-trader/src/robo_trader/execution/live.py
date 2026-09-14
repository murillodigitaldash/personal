"""Execucao via CCXT: testnet para homologacao, real desligado por padrao."""

from __future__ import annotations

import logging

import pandas as pd

from ..config import (
    EXCHANGE_ENV,
    LIVE_ENV_FLAG,
    TESTNET_ENV_FLAG,
    ExchangeCredentials,
    env_flag,
)
from ..domain import Fill, Order, OrderType, Position, quote_of
from .base import Balance, ExecutionError
from .market_rules import MarketRules

logger = logging.getLogger(__name__)


def _flag(value) -> bool | None:
    """Normaliza o booleano da corretora, que as vezes vem como texto."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1"}
    return None

__all__ = ["LIVE_ENV_FLAG", "TESTNET_ENV_FLAG", "LiveExecutionClient"]


class LiveExecutionClient:
    """Envia ordens para a corretora, na testnet ou valendo dinheiro.

    Em `testnet=True` as ordens vao para o ambiente de homologacao da corretora,
    com saldo ficticio: basta ter credenciais de testnet (que sao separadas das
    reais). Sem testnet, enviar qualquer ordem exige duas autorizacoes
    independentes — `enabled=True` no codigo e `ROBO_TRADER_ALLOW_LIVE=1` no
    ambiente — para que ninguem mande dinheiro real por engano rodando um script.
    """

    def __init__(
        self,
        symbol: str,
        exchange_id: str = "binance",
        api_key: str | None = None,
        api_secret: str | None = None,
        enabled: bool = False,
        testnet: bool = False,
        quote_currency: str | None = None,
        exchange=None,
    ) -> None:
        self.symbol = symbol
        self.exchange_id = exchange_id
        # Sem indicacao explicita, a moeda de cotacao e a do proprio par: conferir
        # saldo em USDT para quem opera BTC/BRL olharia a conta errada.
        self.quote_currency = quote_currency or quote_of(symbol)
        self.enabled = enabled
        self.testnet = testnet
        self.mode = "testnet" if testnet else "live"

        do_ambiente = ExchangeCredentials.from_env()
        self.credentials = ExchangeCredentials(
            api_key=api_key or do_ambiente.api_key,
            api_secret=api_secret or do_ambiente.api_secret,
        )

        self._exchange = exchange
        self._sandbox_applied = False
        self._market_rules: MarketRules | None = None
        self._markets_loaded = False

    @classmethod
    def from_env(cls, symbol: str, **kwargs):
        """Cliente configurado pelas variaveis de ambiente (apos `load_env_file`)."""
        import os

        kwargs.setdefault("exchange_id", os.getenv(EXCHANGE_ENV, "binance"))
        kwargs.setdefault("testnet", env_flag(TESTNET_ENV_FLAG))
        return cls(symbol=symbol, **kwargs)

    # -- travas ----------------------------------------------------------

    @staticmethod
    def env_allows_live() -> bool:
        return env_flag(LIVE_ENV_FLAG)

    def ensure_credentials(self) -> None:
        """Exigencia minima de qualquer chamada autenticada, inclusive leitura."""
        if not self.credentials.complete:
            ambiente = "testnet" if self.testnet else "exchange"
            raise ExecutionError(f"credenciais da {ambiente} ausentes (API key/secret)")

    def ensure_can_trade(self) -> None:
        """Recusa o envio de ordem quando falta alguma autorizacao.

        A trava do modo real vale para **enviar ordem**, nao para ler saldo ou
        posicao: leitura nao move dinheiro, e exigir a autorizacao de ordem para
        conferir a conta so empurra quem esta conferindo a ligar a trava antes da
        hora — que e exatamente o que ela deveria evitar.
        """
        if not self.testnet:
            if not self.enabled:
                raise ExecutionError(
                    "modo real desligado: construa o cliente com enabled=True para operar valendo"
                )
            if not self.env_allows_live():
                raise ExecutionError(
                    f"modo real bloqueado: defina {LIVE_ENV_FLAG}=1 no ambiente para liberar ordens reais"
                )
        self.ensure_credentials()

    # -- conexao ---------------------------------------------------------

    @property
    def exchange(self):
        if self._exchange is None:
            try:
                import ccxt
            except ImportError as exc:  # pragma: no cover - depende do ambiente
                raise ExecutionError(
                    "ccxt nao instalado. Rode: pip install 'robo-trader[exchange]'"
                ) from exc
            self._exchange = getattr(ccxt, self.exchange_id)(
                {
                    "apiKey": self.credentials.api_key,
                    "secret": self.credentials.api_secret,
                    "enableRateLimit": True,
                }
            )

        if self.testnet and not self._sandbox_applied:
            self._enable_sandbox(self._exchange)
            self._sandbox_applied = True

        return self._exchange

    def _enable_sandbox(self, exchange) -> None:
        """Aponta o cliente ccxt para os endpoints de testnet da corretora."""
        setter = getattr(exchange, "set_sandbox_mode", None)
        if setter is None:
            raise ExecutionError(f"{self.exchange_id} nao expoe modo testnet no ccxt")
        setter(True)
        logger.info("cliente %s em modo testnet", self.exchange_id)

    # -- permissoes ------------------------------------------------------

    def permissions(self) -> dict | None:
        """O que a chave tem permissao de fazer, quando a corretora publica isso.

        `None` quando a corretora nao expoe a consulta: melhor a checagem sumir do
        relatorio do que virar um 'ok' sobre algo que nunca foi lido.
        """
        reader = getattr(self.exchange, "sapiGetAccountApiRestrictions", None)
        if reader is None:
            return None
        self.ensure_credentials()
        dados = reader() or {}
        return {
            "can_trade": _flag(dados.get("enableSpotAndMarginTrading")),
            "withdrawals": _flag(dados.get("enableWithdrawals")),
            "ip_restricted": _flag(dados.get("ipRestrict")),
        }

    # -- regras do par ---------------------------------------------------

    @property
    def market_rules(self) -> MarketRules | None:
        """Passo, minimos e tick do par, como a corretora publica.

        Carregado uma vez por cliente: a tabela de mercados e grande e nao muda
        no meio de uma sessao. `None` quando a corretora nao publica nada sobre
        o par — ai o cliente envia o que recebeu e deixa a corretora decidir.
        """
        if self._markets_loaded:
            return self._market_rules

        loader = getattr(self.exchange, "load_markets", None)
        if loader is None:
            self._markets_loaded = True
            return None

        market = (loader() or {}).get(self.symbol)
        # So marca como carregado depois que a corretora respondeu: falha de rede
        # virando cache de "par sem regras" mandaria a proxima ordem sem ajuste.
        self._markets_loaded = True
        if market:
            self._market_rules = MarketRules.from_market(market)
        return self._market_rules

    def _fit_to_market(self, order: Order, reference_price: float | None):
        """Ajusta quantidade e preco ao que o par aceita, ou recusa com a razao."""
        quantity = order.quantity
        price = order.price if order.type is OrderType.LIMIT else None

        rules = self.market_rules
        if rules is None:
            return quantity, price

        quantity = rules.adjust_amount(quantity)
        if price is not None:
            price = rules.adjust_price(price)

        referencia = price if price is not None else reference_price
        if referencia is None and rules.min_notional is not None:
            referencia = self._last_price()
        rules.validate(quantity, referencia)
        return quantity, price

    def _last_price(self) -> float | None:
        """Ultimo preco negociado, so para conferir o notional minimo.

        Ordem a mercado nao carrega preco, e sem ele nao da para saber se a ordem
        cabe no notional minimo. Uma cotacao indisponivel nao derruba o envio: a
        corretora ainda vai recusar se estiver abaixo, e perder a ordem por causa
        da cotacao seria pior do que deixar a corretora decidir.
        """
        ticker_reader = getattr(self.exchange, "fetch_ticker", None)
        if ticker_reader is None:
            return None
        try:
            ticker = ticker_reader(self.symbol) or {}
        except Exception as exc:  # pragma: no cover - depende da corretora
            logger.warning("nao foi possivel ler a cotacao de %s: %s", self.symbol, exc)
            return None
        preco = ticker.get("last") or ticker.get("close")
        return float(preco) if preco else None

    # -- operacoes -------------------------------------------------------

    def submit(self, order: Order, reference_price: float | None = None) -> Fill:
        self.ensure_can_trade()
        if order.symbol != self.symbol:
            raise ExecutionError(f"cliente configurado para {self.symbol}, recebeu {order.symbol}")

        quantity, price = self._fit_to_market(order, reference_price)

        logger.warning(
            "enviando ordem %s %s %s %.8f em %s",
            self.mode.upper(), order.side.value, order.type.value, quantity, self.symbol,
        )

        # A chave de idempotencia e do chamador: so ele sabe que dois envios sao o
        # mesmo giro. Gerar uma aqui, nova a cada chamada, nao protegeria de nada —
        # a retentativa depois de um timeout entraria como ordem nova e dobraria a
        # posicao. Sem chave, a corretora decide; com chave, ela recusa a segunda.
        params = {"clientOrderId": order.client_id} if order.client_id else {}

        if order.type is OrderType.MARKET:
            raw = self.exchange.create_order(
                self.symbol, "market", order.side.value, quantity, None, params
            )
        else:
            raw = self.exchange.create_order(
                self.symbol, "limit", order.side.value, quantity, price, params
            )
        return self._to_fill(raw, order, quantity, price)

    def _to_fill(
        self, raw: dict, order: Order, quantity: float, price_enviado: float | None
    ) -> Fill:
        price = raw.get("average") or raw.get("price") or price_enviado
        if price is None:
            raise ExecutionError(f"a exchange nao devolveu preco para a ordem {raw.get('id')}")
        filled = raw.get("filled") or quantity
        fee_info = raw.get("fee") or {}
        timestamp = raw.get("timestamp")
        return Fill(
            timestamp=(
                pd.Timestamp(timestamp, unit="ms", tz="UTC")
                if timestamp
                else pd.Timestamp.now(tz="UTC")
            ),
            symbol=self.symbol,
            side=order.side,
            quantity=float(filled),
            price=float(price),
            fee=float(fee_info.get("cost") or 0.0),
        )

    def position(self, symbol: str) -> Position:
        self.ensure_credentials()
        base = symbol.split("/")[0]
        balances = self.exchange.fetch_balance()
        quantity = float(balances.get(base, {}).get("total") or 0.0)
        # Spot nao reporta preco medio: o robo mantem seu proprio custo se precisar.
        return Position(symbol=symbol, quantity=quantity)

    def balance(self) -> Balance:
        self.ensure_credentials()
        balances = self.exchange.fetch_balance()
        entry = balances.get(self.quote_currency, {})
        return Balance(
            currency=self.quote_currency,
            free=float(entry.get("free") or 0.0),
            used=float(entry.get("used") or 0.0),
        )

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
from ..domain import Fill, Order, OrderType, Position
from .base import Balance, ExecutionError

logger = logging.getLogger(__name__)

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
        quote_currency: str = "USDT",
        exchange=None,
    ) -> None:
        self.symbol = symbol
        self.exchange_id = exchange_id
        self.quote_currency = quote_currency
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

    def ensure_allowed(self) -> None:
        """Recusa a operacao quando falta alguma autorizacao."""
        if not self.testnet:
            if not self.enabled:
                raise ExecutionError(
                    "modo real desligado: construa o cliente com enabled=True para operar valendo"
                )
            if not self.env_allows_live():
                raise ExecutionError(
                    f"modo real bloqueado: defina {LIVE_ENV_FLAG}=1 no ambiente para liberar ordens reais"
                )
        if not self.credentials.complete:
            ambiente = "testnet" if self.testnet else "exchange"
            raise ExecutionError(f"credenciais da {ambiente} ausentes (API key/secret)")

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

    # -- operacoes -------------------------------------------------------

    def submit(self, order: Order, reference_price: float | None = None) -> Fill:
        self.ensure_allowed()
        if order.symbol != self.symbol:
            raise ExecutionError(f"cliente configurado para {self.symbol}, recebeu {order.symbol}")

        logger.warning(
            "enviando ordem %s %s %s %.8f em %s",
            self.mode.upper(), order.side.value, order.type.value, order.quantity, self.symbol,
        )

        if order.type is OrderType.MARKET:
            raw = self.exchange.create_order(
                self.symbol, "market", order.side.value, order.quantity
            )
        else:
            raw = self.exchange.create_order(
                self.symbol, "limit", order.side.value, order.quantity, order.price
            )
        return self._to_fill(raw, order)

    def _to_fill(self, raw: dict, order: Order) -> Fill:
        price = raw.get("average") or raw.get("price") or order.price
        if price is None:
            raise ExecutionError(f"a exchange nao devolveu preco para a ordem {raw.get('id')}")
        filled = raw.get("filled") or order.quantity
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
        self.ensure_allowed()
        base = symbol.split("/")[0]
        balances = self.exchange.fetch_balance()
        quantity = float(balances.get(base, {}).get("total") or 0.0)
        # Spot nao reporta preco medio: o robo mantem seu proprio custo se precisar.
        return Position(symbol=symbol, quantity=quantity)

    def balance(self) -> Balance:
        self.ensure_allowed()
        balances = self.exchange.fetch_balance()
        entry = balances.get(self.quote_currency, {})
        return Balance(
            currency=self.quote_currency,
            free=float(entry.get("free") or 0.0),
            used=float(entry.get("used") or 0.0),
        )

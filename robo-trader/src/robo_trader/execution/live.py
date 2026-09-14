"""Execucao real via CCXT. Desligada por padrao."""

from __future__ import annotations

import logging
import os

import pandas as pd

from ..domain import Fill, Order, OrderType, Position, Side
from .base import Balance, ExecutionError

logger = logging.getLogger(__name__)

LIVE_ENV_FLAG = "ROBO_TRADER_ALLOW_LIVE"


class LiveExecutionClient:
    """Envia ordens de verdade para a exchange.

    Exige duas autorizacoes independentes: `enabled=True` no codigo e a variavel de
    ambiente `ROBO_TRADER_ALLOW_LIVE=1`. Sem as duas, `submit` recusa a ordem. A
    intencao e que ninguem mande dinheiro real por engano ao rodar um script de teste.
    """

    mode = "live"

    def __init__(
        self,
        symbol: str,
        exchange_id: str = "binance",
        api_key: str | None = None,
        api_secret: str | None = None,
        enabled: bool = False,
        quote_currency: str = "USDT",
        exchange=None,
    ) -> None:
        self.symbol = symbol
        self.exchange_id = exchange_id
        self.quote_currency = quote_currency
        self.enabled = enabled
        self._api_key = api_key or os.getenv("ROBO_TRADER_API_KEY")
        self._api_secret = api_secret or os.getenv("ROBO_TRADER_API_SECRET")
        self._exchange = exchange

    # -- travas ----------------------------------------------------------

    @staticmethod
    def env_allows_live() -> bool:
        return os.getenv(LIVE_ENV_FLAG, "0").strip() == "1"

    def ensure_live_allowed(self) -> None:
        if not self.enabled:
            raise ExecutionError(
                "modo real desligado: construa o cliente com enabled=True para operar valendo"
            )
        if not self.env_allows_live():
            raise ExecutionError(
                f"modo real bloqueado: defina {LIVE_ENV_FLAG}=1 no ambiente para liberar ordens reais"
            )
        if not (self._api_key and self._api_secret):
            raise ExecutionError("credenciais da exchange ausentes (API key/secret)")

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
                    "apiKey": self._api_key,
                    "secret": self._api_secret,
                    "enableRateLimit": True,
                }
            )
        return self._exchange

    # -- operacoes -------------------------------------------------------

    def submit(self, order: Order, reference_price: float | None = None) -> Fill:
        self.ensure_live_allowed()
        if order.symbol != self.symbol:
            raise ExecutionError(f"cliente configurado para {self.symbol}, recebeu {order.symbol}")

        logger.warning(
            "enviando ordem REAL %s %s %.8f em %s",
            order.side.value, order.type.value, order.quantity, self.symbol,
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
        self.ensure_live_allowed()
        base = symbol.split("/")[0]
        balances = self.exchange.fetch_balance()
        quantity = float(balances.get(base, {}).get("total") or 0.0)
        # Spot nao reporta preco medio: o robo mantem seu proprio custo se precisar.
        return Position(symbol=symbol, quantity=quantity)

    def balance(self) -> Balance:
        self.ensure_live_allowed()
        balances = self.exchange.fetch_balance()
        entry = balances.get(self.quote_currency, {})
        return Balance(
            currency=self.quote_currency,
            free=float(entry.get("free") or 0.0),
            used=float(entry.get("used") or 0.0),
        )

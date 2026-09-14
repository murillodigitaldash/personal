"""Execucao simulada (paper trading) sobre precos reais."""

from __future__ import annotations

import pandas as pd

from ..backtest.portfolio import Portfolio
from ..domain import Fill, Order, OrderType, Position, Side
from .base import Balance, ExecutionError


class PaperExecutionClient:
    """Executa ordens contra uma carteira em memoria, com taxa e slippage.

    Usa exatamente a mesma `Portfolio` do backtest, entao o resultado do paper
    trading e comparavel ao da simulacao historica.
    """

    mode = "paper"

    def __init__(
        self,
        symbol: str,
        initial_cash: float = 10_000.0,
        fee_rate: float = 0.001,
        slippage_rate: float = 0.0005,
        quote_currency: str = "USDT",
    ) -> None:
        self.symbol = symbol
        self.quote_currency = quote_currency
        self.portfolio = Portfolio(
            symbol=symbol,
            initial_cash=initial_cash,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
        )
        self.last_price: float | None = None

    def mark(self, price: float) -> None:
        """Informa o preco corrente de mercado."""
        if price <= 0:
            raise ValueError("preco deve ser positivo")
        self.last_price = price

    def submit(self, order: Order, reference_price: float | None = None) -> Fill:
        if order.symbol != self.symbol:
            raise ExecutionError(f"cliente configurado para {self.symbol}, recebeu {order.symbol}")

        price = reference_price if reference_price is not None else (
            order.price if order.type is OrderType.LIMIT else self.last_price
        )
        if price is None or price <= 0:
            raise ExecutionError("sem preco de referencia: chame mark(price) antes de operar")

        quantity = order.quantity
        if order.reduce_only:
            quantity = min(quantity, abs(self.portfolio.position.quantity))
            if quantity <= 0:
                raise ExecutionError("ordem reduce_only sem posicao para reduzir")

        execution_price = self.portfolio.execution_price(price, order.side)
        if order.side is Side.BUY:
            affordable = self.portfolio.cash / (execution_price * (1 + self.portfolio.fee_rate))
            if quantity > affordable:
                raise ExecutionError(
                    f"saldo insuficiente: pedido {quantity:.8f}, possivel {max(affordable, 0):.8f}"
                )

        timestamp = pd.Timestamp.now(tz="UTC")
        return self.portfolio._apply_fill(timestamp, order.side, quantity, execution_price)

    def position(self, symbol: str) -> Position:
        if symbol != self.symbol:
            return Position(symbol=symbol)
        return self.portfolio.position

    def balance(self) -> Balance:
        return Balance(currency=self.quote_currency, free=self.portfolio.cash)

    def equity(self, price: float | None = None) -> float:
        mark_price = price if price is not None else self.last_price
        if mark_price is None:
            return self.portfolio.cash
        return self.portfolio.equity(mark_price)

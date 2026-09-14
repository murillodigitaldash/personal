"""Carteira simulada: caixa, posicao, custos e apuracao de trades fechados."""

from __future__ import annotations

import pandas as pd

from ..domain import Fill, Position, Side, Trade

EPSILON = 1e-12


class Portfolio:
    """Carteira de um unico simbolo com custo de corretagem e slippage.

    Todo preco de execucao ja embute o slippage; a taxa e cobrada sobre o valor
    financeiro. O PnL registrado em cada `Trade` e liquido de taxas de entrada e saida.
    """

    def __init__(
        self,
        symbol: str,
        initial_cash: float = 10_000.0,
        fee_rate: float = 0.001,
        slippage_rate: float = 0.0005,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash deve ser positivo")
        if fee_rate < 0 or slippage_rate < 0:
            raise ValueError("fee_rate e slippage_rate nao podem ser negativos")

        self.symbol = symbol
        self.initial_cash = initial_cash
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate

        self.cash = initial_cash
        self.position = Position(symbol=symbol)
        self.trades: list[Trade] = []
        self.fills: list[Fill] = []
        self.total_fees = 0.0

    # -- leitura ---------------------------------------------------------

    def equity(self, price: float) -> float:
        return self.cash + self.position.market_value(price)

    def weight(self, price: float) -> float:
        equity = self.equity(price)
        if equity <= 0:
            return 0.0
        return self.position.market_value(price) / equity

    def execution_price(self, reference_price: float, side: Side) -> float:
        drift = 1 + self.slippage_rate if side is Side.BUY else 1 - self.slippage_rate
        return reference_price * drift

    # -- escrita ---------------------------------------------------------

    def rebalance(
        self,
        timestamp: pd.Timestamp,
        reference_price: float,
        target_weight: float,
        min_notional: float = 0.0,
        threshold: float = 0.0,
    ) -> Fill | None:
        """Leva a exposicao para `target_weight` do patrimonio, se valer o giro."""
        if reference_price <= 0:
            return None

        equity = self.equity(reference_price)
        if equity <= 0:
            return None

        current_weight = self.weight(reference_price)
        if abs(target_weight - current_weight) < threshold and abs(target_weight) > EPSILON:
            # Desvio pequeno demais: nao paga o custo de girar a carteira.
            return None

        desired_quantity = target_weight * equity / reference_price
        delta = desired_quantity - self.position.quantity
        if abs(delta) < EPSILON:
            return None

        side = Side.BUY if delta > 0 else Side.SELL
        price = self.execution_price(reference_price, side)
        quantity = abs(delta)

        if side is Side.BUY:
            # Nunca alavanca por arredondamento: limita ao caixa disponivel.
            affordable = self.cash / (price * (1 + self.fee_rate))
            quantity = min(quantity, max(affordable, 0.0))

        closing = self._closing_quantity(side)
        is_full_close = closing > EPSILON and abs(quantity - closing) <= EPSILON
        if quantity * price < min_notional and not is_full_close:
            # Ordens minusculas so passam quando servem para zerar a posicao.
            return None
        if quantity < EPSILON:
            return None

        return self._apply_fill(timestamp, side, quantity, price)

    def close(self, timestamp: pd.Timestamp, reference_price: float) -> Fill | None:
        """Zera a posicao a mercado (usado por stop, take profit e fim do backtest)."""
        if self.position.is_flat:
            return None
        side = Side.SELL if self.position.quantity > 0 else Side.BUY
        price = self.execution_price(reference_price, side)
        return self._apply_fill(timestamp, side, abs(self.position.quantity), price)

    def close_at_price(self, timestamp: pd.Timestamp, price: float) -> Fill | None:
        """Zera a posicao em um preco ja definido (stop disparado dentro do candle)."""
        if self.position.is_flat:
            return None
        side = Side.SELL if self.position.quantity > 0 else Side.BUY
        return self._apply_fill(timestamp, side, abs(self.position.quantity), price)

    # -- interno ---------------------------------------------------------

    def _closing_quantity(self, side: Side) -> float:
        position_quantity = self.position.quantity
        if side is Side.SELL and position_quantity > 0:
            return position_quantity
        if side is Side.BUY and position_quantity < 0:
            return -position_quantity
        return 0.0

    def _apply_fill(self, timestamp: pd.Timestamp, side: Side, quantity: float, price: float) -> Fill:
        fee = quantity * price * self.fee_rate
        signed = quantity if side is Side.BUY else -quantity

        self.cash -= signed * price + fee
        self.total_fees += fee

        position = self.position
        same_direction = position.is_flat or (position.quantity > 0) == (signed > 0)

        if same_direction:
            new_quantity = position.quantity + signed
            position.avg_price = (
                (position.avg_price * position.quantity + price * signed) / new_quantity
            )
            position.quantity = new_quantity
            position.fees += fee
            if position.opened_at is None:
                position.opened_at = timestamp
        else:
            self._register_close(timestamp, side, quantity, price, fee)

        fill = Fill(
            timestamp=timestamp,
            symbol=self.symbol,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
        )
        self.fills.append(fill)
        return fill

    def _register_close(
        self, timestamp: pd.Timestamp, side: Side, quantity: float, price: float, fee: float
    ) -> None:
        position = self.position
        open_quantity = abs(position.quantity)
        closed = min(quantity, open_quantity)
        direction = 1.0 if position.quantity > 0 else -1.0

        gross = (price - position.avg_price) * closed * direction
        entry_fee = position.fees * (closed / open_quantity)
        exit_fee = fee * (closed / quantity)

        self.trades.append(
            Trade(
                symbol=self.symbol,
                side=Side.BUY if direction > 0 else Side.SELL,
                quantity=closed,
                entry_time=position.opened_at or timestamp,
                entry_price=position.avg_price,
                exit_time=timestamp,
                exit_price=price,
                fees=entry_fee + exit_fee,
                pnl=gross - entry_fee - exit_fee,
            )
        )

        signed = quantity if side is Side.BUY else -quantity
        remaining = position.quantity + signed

        if abs(remaining) < EPSILON:
            position.quantity = 0.0
            position.avg_price = 0.0
            position.opened_at = None
            position.fees = 0.0
        elif (remaining > 0) == (position.quantity > 0):
            position.quantity = remaining
            position.fees -= entry_fee
        else:
            # A ordem inverteu a mao: o excedente abre posicao no sentido oposto.
            position.quantity = remaining
            position.avg_price = price
            position.opened_at = timestamp
            position.fees = fee - exit_fee

"""Regras do par publicadas pela corretora: passo, minimos e tick.

A corretora recusa ordem que nao respeite o passo de quantidade, o minimo do par
ou o notional minimo. Descobrir isso em producao custa uma ordem perdida no meio
de uma operacao; e por isso que a checagem mora aqui, antes do envio.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from .base import ExecutionError

__all__ = ["MarketRules"]


def _step(value) -> float | None:
    """Normaliza a precisao do ccxt para um passo em unidades.

    O ccxt publica `precision` de duas formas conforme a corretora: como passo
    (`0.001`, modo TICK_SIZE) ou como numero de casas (`3`, modo DECIMAL_PLACES).
    Inteiro >= 1 e lido como casas decimais, que e a convencao do modo
    DECIMAL_PLACES. O caso ambiguo (`1`) erra para o lado de recusar a ordem, e
    nao para o de enviar quantidade errada.
    """
    if value is None:
        return None
    try:
        numero = float(value)
    except (TypeError, ValueError):
        return None
    if numero <= 0:
        return None
    if numero >= 1 and numero.is_integer():
        return float(Decimal(1).scaleb(-int(numero)))
    return numero


def _positivo(value) -> float | None:
    if value is None:
        return None
    try:
        numero = float(value)
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


def _truncate(value: float, step: float) -> float:
    """Desce ate o multiplo do passo. Decimal para nao errar por ponto flutuante."""
    quantidade = Decimal(str(value))
    passo = Decimal(str(step))
    multiplos = (quantidade / passo).to_integral_value(rounding=ROUND_DOWN)
    return float(multiplos * passo)


@dataclass(frozen=True)
class MarketRules:
    """O que a corretora aceita neste par."""

    symbol: str
    amount_step: float | None = None
    min_amount: float | None = None
    min_notional: float | None = None
    price_step: float | None = None

    @classmethod
    def from_market(cls, market: dict) -> MarketRules:
        """Le o dicionario de mercado do ccxt."""
        precision = market.get("precision") or {}
        limits = market.get("limits") or {}
        return cls(
            symbol=market.get("symbol", ""),
            amount_step=_step(precision.get("amount")),
            price_step=_step(precision.get("price")),
            min_amount=_positivo((limits.get("amount") or {}).get("min")),
            min_notional=_positivo((limits.get("cost") or {}).get("min")),
        )

    # -- ajuste ----------------------------------------------------------

    def adjust_amount(self, quantity: float) -> float:
        """Trunca a quantidade para o passo do par.

        Sempre para baixo: enviar mais do que a estrategia pediu e' um erro pior
        do que enviar um pouco menos.
        """
        if self.amount_step is None:
            return quantity
        return _truncate(quantity, self.amount_step)

    def adjust_price(self, price: float) -> float:
        """Trunca o preco para o tick do par."""
        if self.price_step is None:
            return price
        return _truncate(price, self.price_step)

    # -- validacao -------------------------------------------------------

    def validate(self, quantity: float, price: float | None = None) -> None:
        """Recusa o que a corretora recusaria, com a razao explicita."""
        minimo = self.min_amount if self.min_amount is not None else self.amount_step
        if quantity <= 0 or (minimo is not None and quantity < minimo):
            raise ExecutionError(
                f"quantidade {quantity:.8f} abaixo do minimo do par {self.symbol}: {minimo}"
            )
        if self.min_notional is not None and price:
            notional = quantity * price
            if notional < self.min_notional:
                raise ExecutionError(
                    f"notional {notional:.2f} abaixo do minimo do par {self.symbol}: "
                    f"{self.min_notional}"
                )

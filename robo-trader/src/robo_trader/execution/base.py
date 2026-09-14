"""Contrato de execucao: a mesma interface para simulado e real."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..domain import Fill, Order, Position


class ExecutionError(RuntimeError):
    """A ordem nao pode ser enviada ou foi recusada pela corretora."""


@dataclass(frozen=True)
class Balance:
    """Saldo da conta na moeda de cotacao."""

    currency: str
    free: float
    used: float = 0.0

    @property
    def total(self) -> float:
        return self.free + self.used


@runtime_checkable
class ExecutionClient(Protocol):
    """Porta de saida do robo. Trocar simulado por real e trocar a implementacao.

    Nenhuma estrategia fala com a exchange direto: tudo passa por aqui, e por isso
    a trava do modo real fica em um unico lugar.
    """

    mode: str

    def submit(self, order: Order, reference_price: float | None = None) -> Fill:
        """Envia a ordem e devolve a execucao."""
        ...

    def position(self, symbol: str) -> Position:
        """Posicao atual no simbolo."""
        ...

    def balance(self) -> Balance:
        """Saldo disponivel na moeda de cotacao."""
        ...

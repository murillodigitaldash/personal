"""Registro de estrategias por nome, usado pela CLI."""

from __future__ import annotations

from .base import Strategy
from .donchian_breakout import DonchianBreakout
from .ema_crossover import EmaCrossover
from .rsi_reversion import RsiReversion

STRATEGIES: dict[str, type[Strategy]] = {
    EmaCrossover.name: EmaCrossover,
    RsiReversion.name: RsiReversion,
    DonchianBreakout.name: DonchianBreakout,
}


def build_strategy(name: str, params: dict | None = None) -> Strategy:
    try:
        cls = STRATEGIES[name]
    except KeyError as exc:
        raise KeyError(
            f"estrategia '{name}' nao registrada; disponiveis: {sorted(STRATEGIES)}"
        ) from exc
    return cls(**(params or {}))


def available() -> list[str]:
    return sorted(STRATEGIES)

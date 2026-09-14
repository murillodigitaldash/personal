"""Gestao de risco: limita exposicao e desliga o robo quando o prejuizo passa do teto."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class RiskConfig:
    """Limites de risco. Valores em fracao (0.05 = 5%); 0 desliga a regra."""

    max_position_weight: float = 1.0
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    max_daily_loss: float = 0.0
    max_drawdown: float = 0.0
    min_trade_notional: float = 10.0
    rebalance_threshold: float = 0.02
    trade_cooldown: float = 0.0
    max_trade_notional: float = 0.0
    max_daily_notional: float = 0.0

    def __post_init__(self) -> None:
        if not 0 < self.max_position_weight <= 1:
            raise ValueError("max_position_weight deve estar em (0, 1]")
        for field_name in ("stop_loss_pct", "take_profit_pct", "max_daily_loss", "max_drawdown"):
            value = getattr(self, field_name)
            if not 0 <= value < 1:
                raise ValueError(f"{field_name} deve estar em [0, 1)")
        for field_name in (
            "min_trade_notional",
            "trade_cooldown",
            "max_trade_notional",
            "max_daily_notional",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} nao pode ser negativo")
        if not 0 <= self.rebalance_threshold < 1:
            raise ValueError("rebalance_threshold deve estar em [0, 1)")


class RiskManager:
    """Mantem o estado de risco da conta e decide o peso permitido a cada candle.

    Duas travas independentes:

    * `max_daily_loss` bloqueia novas exposicoes ate o fim do dia corrente;
    * `max_drawdown` para o robo de vez (kill switch), zerando a posicao.
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.reset()

    def reset(self) -> None:
        self.peak_equity = 0.0
        self.day_start_equity = 0.0
        self.current_day: date | None = None
        self.halted = False
        self.halted_reason: str | None = None
        self.day_blocked = False
        self.day_blocked_reason: str | None = None
        self.last_trade_at: pd.Timestamp | None = None
        self.notional_blocked_reason: str | None = None
        self.traded_notional = 0.0
        self.traded_day: date | None = None

    def update(self, timestamp: pd.Timestamp, equity: float) -> None:
        """Atualiza pico, referencia do dia e avalia as travas."""
        day = timestamp.date()
        if self.current_day != day:
            self.current_day = day
            self.day_start_equity = equity
            self.day_blocked = False
            self.day_blocked_reason = None

        self.peak_equity = max(self.peak_equity, equity)

        cfg = self.config
        if cfg.max_daily_loss and self.day_start_equity > 0:
            daily_return = equity / self.day_start_equity - 1.0
            if daily_return <= -cfg.max_daily_loss:
                self.day_blocked = True
                self.day_blocked_reason = (
                    f"perda diaria de {daily_return:.2%} atingiu o limite de {cfg.max_daily_loss:.2%}"
                )

        if cfg.max_drawdown and self.peak_equity > 0:
            drawdown = equity / self.peak_equity - 1.0
            if drawdown <= -cfg.max_drawdown:
                self.halted = True
                self.halted_reason = (
                    f"drawdown de {drawdown:.2%} atingiu o limite de {cfg.max_drawdown:.2%}"
                )

    def allowed_weight(self, desired_weight: float) -> float:
        """Peso que o risco autoriza, dado o peso pedido pela estrategia."""
        if self.halted or self.day_blocked:
            return 0.0
        cap = self.config.max_position_weight
        return max(-cap, min(cap, float(desired_weight)))

    def register_trade(self, timestamp: pd.Timestamp, notional: float) -> None:
        """Anota um giro executado, para as travas de espera e de volume."""
        self.last_trade_at = timestamp
        self.traded_notional = self._traded_today(timestamp) + abs(notional)
        self.traded_day = timestamp.date()

    def _traded_today(self, timestamp: pd.Timestamp) -> float:
        """Volume ja girado no dia de `timestamp`. Vira zero quando o dia troca."""
        return self.traded_notional if self.traded_day == timestamp.date() else 0.0

    def allowed_notional(self, timestamp: pd.Timestamp, desired: float) -> float:
        """Quanto do notional pedido o risco autoriza neste instante."""
        self.notional_blocked_reason = None
        cfg = self.config
        if cfg.trade_cooldown and self.last_trade_at is not None:
            desde = (timestamp - self.last_trade_at).total_seconds()
            if desde < cfg.trade_cooldown:
                self.notional_blocked_reason = (
                    f"espera de {cfg.trade_cooldown:.0f}s entre giros: "
                    f"faltam {cfg.trade_cooldown - desde:.0f}s"
                )
                return 0.0

        permitido = desired
        if cfg.max_daily_notional:
            sobra = max(cfg.max_daily_notional - self._traded_today(timestamp), 0.0)
            if permitido > sobra:
                permitido = sobra
                self.notional_blocked_reason = (
                    f"volume diario de {cfg.max_daily_notional:,.2f} deixa "
                    f"so {sobra:,.2f} para girar hoje"
                )

        if cfg.max_trade_notional and permitido > cfg.max_trade_notional:
            permitido = cfg.max_trade_notional
            self.notional_blocked_reason = (
                f"teto por ordem de {cfg.max_trade_notional:,.2f} cortou o giro de {desired:,.2f}"
            )
        return permitido

    @property
    def blocked_reason(self) -> str | None:
        return self.halted_reason or self.day_blocked_reason

    def exit_levels(self, entry_price: float, is_long: bool) -> tuple[float | None, float | None]:
        """Precos de stop loss e take profit para uma posicao aberta em `entry_price`."""
        cfg = self.config
        if entry_price <= 0:
            return None, None
        direction = 1.0 if is_long else -1.0
        stop = entry_price * (1 - direction * cfg.stop_loss_pct) if cfg.stop_loss_pct else None
        target = entry_price * (1 + direction * cfg.take_profit_pct) if cfg.take_profit_pct else None
        return stop, target

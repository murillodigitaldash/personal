"""Tipos de dominio compartilhados por dados, estrategias, backtest e execucao."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True)
class Order:
    """Ordem antes de ir para a corretora (ou para o simulador)."""

    symbol: str
    side: Side
    quantity: float
    type: OrderType = OrderType.MARKET
    price: float | None = None
    client_id: str | None = None
    reduce_only: bool = False

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity deve ser positiva")
        if self.type is OrderType.LIMIT and self.price is None:
            raise ValueError("ordem limit exige price")


@dataclass(frozen=True)
class Fill:
    """Execucao efetiva de uma ordem."""

    timestamp: datetime
    symbol: str
    side: Side
    quantity: float
    price: float
    fee: float = 0.0

    @property
    def signed_quantity(self) -> float:
        return self.quantity if self.side is Side.BUY else -self.quantity

    @property
    def notional(self) -> float:
        return self.quantity * self.price


@dataclass
class Trade:
    """Round trip fechado: da abertura ate a zeragem da posicao."""

    symbol: str
    side: Side
    quantity: float
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    fees: float = 0.0
    pnl: float = 0.0

    @property
    def is_win(self) -> bool:
        return self.pnl > 0

    @property
    def return_pct(self) -> float:
        cost = self.entry_price * self.quantity
        return self.pnl / cost if cost else 0.0

    @property
    def duration(self):
        return self.exit_time - self.entry_time


@dataclass
class Position:
    """Posicao aberta em um simbolo, com preco medio de entrada."""

    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    opened_at: datetime | None = None
    fees: float = 0.0

    @property
    def is_flat(self) -> bool:
        return abs(self.quantity) < 1e-12

    @property
    def side(self) -> Side | None:
        if self.is_flat:
            return None
        return Side.BUY if self.quantity > 0 else Side.SELL

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.avg_price) * self.quantity


@dataclass
class AccountState:
    """Retrato da conta em um instante, usado pelo gestor de risco."""

    cash: float
    equity: float
    positions: dict[str, Position] = field(default_factory=dict)
    peak_equity: float = 0.0
    day_start_equity: float = 0.0

    @property
    def drawdown(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return self.equity / self.peak_equity - 1.0

    @property
    def daily_return(self) -> float:
        if self.day_start_equity <= 0:
            return 0.0
        return self.equity / self.day_start_equity - 1.0


def quote_of(symbol: str, default: str = "USDT") -> str:
    """Moeda de cotacao do par: 'BTC/BRL' -> 'BRL', 'BTC/USDT:USDT' -> 'USDT'."""
    if "/" not in symbol:
        return default
    return symbol.split("/", 1)[1].split(":", 1)[0] or default

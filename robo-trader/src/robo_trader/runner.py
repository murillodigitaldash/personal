"""Runner em tempo real: a mesma decisao do backtest, candle a candle.

O motor de backtest le o sinal no fechamento do candle `t` e executa na abertura
de `t+1`. Em tempo real o equivalente e agir **logo depois que o candle fecha**,
usando o fechamento dele como preco de referencia — o proximo preco negociado.

Dai vem a regra que este modulo existe para garantir: o candle corrente, que
ainda esta se formando, nao tem sinal. Usa-lo seria antecipacao de dados, o
mesmo erro que o backtest se esforca para nao cometer — so que aqui custaria
dinheiro de verdade.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .backtest.portfolio import EPSILON
from .data.schema import normalize_ohlcv, timeframe_to_timedelta
from .domain import Fill, Order, Side
from .risk import RiskConfig, RiskManager
from .strategies.base import Strategy

__all__ = ["Decision", "Runner"]


@dataclass(frozen=True)
class Decision:
    """O que o runner decidiu em um candle, e por que."""

    timestamp: pd.Timestamp | None
    price: float
    target_weight: float
    current_weight: float
    action: str
    reason: str
    fill: Fill | None = None

    def __str__(self) -> str:
        quando = self.timestamp.strftime("%Y-%m-%d %H:%M") if self.timestamp is not None else "--"
        return (
            f"{quando}  {self.price:>12,.2f}  alvo {self.target_weight:+.2f}  "
            f"atual {self.current_weight:+.2f}  {self.action}: {self.reason}"
        )


class Runner:
    """Liga fonte de candles -> estrategia -> risco -> execucao.

    Nao sabe se o cliente de execucao e simulado, testnet ou real: a decisao e a
    mesma nos tres, e so a implementacao de `ExecutionClient` muda.
    """

    def __init__(
        self,
        source,
        strategy: Strategy,
        client,
        risk: RiskConfig | RiskManager | None = None,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        history: int = 500,
        fee_rate: float = 0.001,
        slippage_rate: float = 0.0005,
        close_delay: float = 2.0,
        max_candle_age: float = 1.5,
        now: Callable[[], pd.Timestamp] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.source = source
        self.strategy = strategy
        self.client = client
        self.risk = risk if isinstance(risk, RiskManager) else RiskManager(risk or RiskConfig())
        self.symbol = symbol
        self.timeframe = timeframe
        self.history = history
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        # Folga apos o fechamento: pedir o candle no instante exato costuma
        # devolver a vela ainda aberta, que e justamente o que nao pode ser usado.
        self.close_delay = close_delay
        # Idade maxima do ultimo candle fechado, em multiplos do timeframe. Feed
        # parado devolve vela antiga sem avisar: o filtro de candle aberto tira o
        # que esta se formando, mas nada impede operar sobre um fechamento de
        # ontem. 0 desliga a trava.
        self.max_candle_age = max_candle_age
        self._now = now or (lambda: pd.Timestamp.now(tz="UTC"))
        self._sleep = sleep or time.sleep
        self._notional_block: str | None = None

    # -- leitura ---------------------------------------------------------

    def closed_candles(self) -> pd.DataFrame:
        """Candles ja fechados. O que ainda esta se formando fica de fora."""
        duracao = timeframe_to_timedelta(self.timeframe)
        agora = self._now()
        # A janela vai explicita: `limit` em algumas fontes e tamanho de pagina, e
        # pedir so por ele devolve o comeco do historico — preco de semanas atras.
        bruto = self.source.fetch_ohlcv(
            self.symbol,
            self.timeframe,
            since=agora - duracao * self.history,
            limit=self.history,
        )
        candles = normalize_ohlcv(bruto)
        return candles.loc[candles.index + duracao <= agora]

    def _staleness(self, timestamp: pd.Timestamp) -> str | None:
        """Motivo do bloqueio quando o ultimo candle fechado esta velho demais."""
        if not self.max_candle_age:
            return None
        duracao = timeframe_to_timedelta(self.timeframe)
        idade = self._now() - (timestamp + duracao)
        if idade <= self.max_candle_age * duracao:
            return None
        return (
            f"candle atrasado: fechou ha {idade.total_seconds() / 60:.0f} min, "
            f"limite de {self.max_candle_age:g}x {self.timeframe}"
        )

    def _state(self, price: float) -> tuple[float, float, float]:
        """Caixa livre, quantidade em posicao e patrimonio ao preco informado."""
        livre = float(self.client.balance().free)
        quantidade = float(self.client.position(self.symbol).quantity)
        return livre, quantidade, livre + quantidade * price

    # -- decisao ---------------------------------------------------------

    def step(self) -> Decision:
        """Avalia o ultimo candle fechado e opera se for o caso."""
        candles = self.closed_candles()
        if len(candles) <= self.strategy.warmup:
            return Decision(
                timestamp=None, price=0.0, target_weight=0.0, current_weight=0.0,
                action="manteve",
                reason=f"candles fechados insuficientes ({len(candles)})",
            )

        timestamp = candles.index[-1]
        price = float(candles["close"].iloc[-1])

        atraso = self._staleness(timestamp)
        if atraso is not None:
            return Decision(
                timestamp=timestamp, price=price, target_weight=0.0, current_weight=0.0,
                action="bloqueado", reason=atraso,
            )

        sinais = self.strategy.generate_signals(candles).astype(float).fillna(0.0)
        desejado = float(sinais.iloc[-1])

        livre, quantidade, equity = self._state(price)
        atual = (quantidade * price / equity) if equity > 0 else 0.0

        self.risk.update(timestamp, equity)
        alvo = self.risk.allowed_weight(desejado)
        bloqueado = self.risk.halted or self.risk.day_blocked

        base = dict(
            timestamp=timestamp, price=price, target_weight=alvo, current_weight=atual
        )
        if equity <= 0:
            return Decision(**base, action="manteve", reason="sem patrimonio para operar")

        ordem = self._order_for(alvo, atual, quantidade, livre, price, timestamp)
        if ordem is None:
            if bloqueado:
                return Decision(**base, action="bloqueado", reason=self.risk.blocked_reason)
            if self._notional_block:
                return Decision(**base, action="bloqueado", reason=self._notional_block)
            return Decision(**base, action="manteve", reason="sem desvio que pague o giro")

        fill = self.client.submit(ordem, price)
        self.risk.register_trade(timestamp, fill.quantity * fill.price)
        acao = "comprou" if ordem.side is Side.BUY else "vendeu"
        motivo = self.risk.blocked_reason if bloqueado else f"peso {atual:+.2f} -> {alvo:+.2f}"
        return Decision(**base, action=acao, reason=motivo, fill=fill)

    def _order_for(
        self,
        alvo: float,
        atual: float,
        quantidade: float,
        livre: float,
        price: float,
        timestamp: pd.Timestamp,
    ) -> Order | None:
        """Ordem que leva a exposicao ao peso alvo, ou None quando nao vale girar.

        Espelha `Portfolio.rebalance` para que paper, testnet e live tomem a mesma
        decisao que o backtest tomaria no mesmo candle.
        """
        self._notional_block = None
        cfg = self.risk.config
        if abs(alvo - atual) < cfg.rebalance_threshold and abs(alvo) > EPSILON:
            return None

        equity = livre + quantidade * price
        delta = (alvo * equity / price) - quantidade
        if abs(delta) < EPSILON:
            return None

        side = Side.BUY if delta > 0 else Side.SELL
        tamanho = abs(delta)
        if side is Side.BUY:
            # Limita ao caixa contando taxa E slippage: o preco que sai e pior que o
            # de referencia, e dimensionar sem isso faz a corretora recusar por saldo.
            custo_unitario = price * (1 + self.slippage_rate) * (1 + self.fee_rate)
            tamanho = min(tamanho, max(livre / custo_unitario, 0.0))

        # Teto e espera valem so para risco novo. Barrar a saida transformaria a
        # protecao em armadilha: o robo ficaria preso dentro da posicao justamente
        # quando precisa sair. Inversao direta (long -> short) escapa do teto, mas
        # as estrategias de hoje so vao de 0 a 1.
        if abs(alvo) > abs(atual):
            pedido = tamanho * price
            permitido = self.risk.allowed_notional(timestamp, pedido)
            if permitido <= 0:
                self._notional_block = self.risk.notional_blocked_reason
                return None
            tamanho = permitido / price

        zerando = abs(tamanho - abs(quantidade)) <= EPSILON and quantidade != 0
        if tamanho * price < cfg.min_trade_notional and not zerando:
            # Ordem minuscula so passa quando serve para zerar a posicao.
            return None
        if tamanho < EPSILON:
            return None

        return Order(
            symbol=self.symbol,
            side=side,
            quantity=tamanho,
            client_id=self._client_id(side, timestamp),
        )

    def _client_id(self, side: Side, timestamp: pd.Timestamp) -> str:
        """Identidade do giro: mesma vela e mesmo lado dao sempre a mesma chave.

        E o que permite reenviar depois de um timeout sem medo: a corretora
        reconhece a chave repetida e recusa a segunda ordem, em vez de dobrar a
        posicao porque a resposta da primeira se perdeu no caminho.
        """
        vela = int(timestamp.value // 10**6)
        return f"{self.symbol.replace('/', '')}-{side.value}-{vela}"

    # -- laco ------------------------------------------------------------

    def next_close(self, moment: pd.Timestamp | None = None) -> pd.Timestamp:
        """Proximo fechamento de candle depois de `moment`."""
        agora = moment if moment is not None else self._now()
        duracao = timeframe_to_timedelta(self.timeframe)
        epoch = pd.Timestamp(0, tz="UTC")
        decorridos = (agora - epoch) // duracao
        return epoch + (decorridos + 1) * duracao

    def wait_for_next_close(self) -> None:
        """Dorme ate o proximo candle fechar, com a folga de publicacao."""
        espera = (self.next_close() - self._now()).total_seconds() + self.close_delay
        if espera > 0:
            self._sleep(espera)

    def run(
        self,
        max_steps: int | None = None,
        on_decision: Callable[[Decision], None] | None = None,
    ) -> list[Decision]:
        """Opera em laco, um passo por candle fechado.

        Sem `max_steps` roda ate ser interrompido. Cada volta espera o candle
        fechar antes de decidir — nunca opera no meio da formacao de uma vela.
        """
        decisoes: list[Decision] = []
        while max_steps is None or len(decisoes) < max_steps:
            self.wait_for_next_close()
            decisao = self.step()
            decisoes.append(decisao)
            if on_decision is not None:
                on_decision(decisao)
        return decisoes

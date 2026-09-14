"""Runner em tempo real: mesma decisao do backtest, candle a candle."""

import pandas as pd
import pytest
from conftest import make_candles

from robo_trader.execution import PaperExecutionClient
from robo_trader.runner import Runner
from robo_trader.strategies.base import Strategy


class FonteFalsa:
    """Fonte de candles que devolve sempre a mesma janela, sem rede."""

    def __init__(self, candles):
        self.candles = candles
        self.chamadas = 0

    def fetch_ohlcv(self, symbol, timeframe, since=None, until=None, limit=None):
        self.chamadas += 1
        return self.candles


class CompraAcimaDe115(Strategy):
    """Compra quando o fechamento passa de 115. Serve para separar candle aberto de fechado."""

    name = "acima_de_115"

    def generate_signals(self, df):
        return (df["close"] > 115).astype(float)


def runner_de_teste(candles, agora, strategy=None, client=None, **kwargs):
    cliente = client or PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    return Runner(
        source=FonteFalsa(candles),
        strategy=strategy or CompraAcimaDe115(),
        client=cliente,
        symbol="BTC/USDT",
        timeframe="1h",
        fee_rate=0.0, slippage_rate=0.0,
        now=lambda: pd.Timestamp(agora, tz="UTC"),
        **kwargs,
    )


# Candles de 1h em 10:00, 11:00 e 12:00. O de 12:00 so fecha as 13:00.
CANDLES = make_candles([100.0, 110.0, 120.0], start="2024-01-01 10:00", freq="1h")


def test_sinal_de_candle_ainda_aberto_nao_vira_ordem():
    """As 12:30 o candle das 12:00 ainda esta se formando: seu sinal nao existe."""
    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    runner = runner_de_teste(CANDLES, "2024-01-01 12:30", client=cliente)

    decisao = runner.step()

    # O ultimo candle FECHADO e o das 11:00, que fechou em 110 — abaixo de 115.
    assert decisao.timestamp == pd.Timestamp("2024-01-01 11:00", tz="UTC")
    assert decisao.target_weight == pytest.approx(0.0)
    assert cliente.position("BTC/USDT").is_flat


def test_candle_recem_fechado_vira_ordem():
    """As 13:00 o candle das 12:00 fechou: agora o sinal dele vale."""
    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    runner = runner_de_teste(CANDLES, "2024-01-01 13:00", client=cliente)

    decisao = runner.step()

    assert decisao.timestamp == pd.Timestamp("2024-01-01 12:00", tz="UTC")
    assert decisao.price == pytest.approx(120.0)
    assert decisao.target_weight == pytest.approx(1.0)
    assert decisao.action == "comprou"
    assert cliente.position("BTC/USDT").quantity == pytest.approx(1_000.0 / 120.0)


# -- equivalencia com o backtest -------------------------------------------


def test_runner_reproduz_exatamente_o_backtest_no_mesmo_periodo():
    """Paper trading e backtest tem que chegar na mesma posicao, fill a fill.

    O `make_candles` abre cada candle no fechamento do anterior, entao o preco de
    execucao do backtest (abertura de t+1) e exatamente o que o runner usa
    (fechamento de t). Se os dois divergirem aqui, o backtest esta mentindo sobre
    o que aconteceria de verdade.

    A serie comeca com um trecho plano: enquanto as medias estao empatadas nao ha
    sinal, e os dois lados chegam ao primeiro candle operavel com o mesmo estado.
    Sem isso o teste esbarraria na fronteira do aquecimento, que e um assunto
    separado (o backtest opera um candle que o runner ainda nao pode avaliar).
    """
    import numpy as np

    from robo_trader.backtest import BacktestConfig, BacktestEngine
    from robo_trader.risk import RiskConfig
    from robo_trader.strategies import build_strategy

    plano = np.full(12, 100.0)
    onda = np.sin(np.linspace(0, 6 * np.pi, 60)) * 12 + 100
    candles = make_candles(np.concatenate([plano, onda]), start="2024-01-01 00:00", freq="1h")

    def estrategia():
        return build_strategy("ema_crossover", {"fast": 3, "slow": 7})

    def risco():
        return RiskConfig(min_trade_notional=10.0, rebalance_threshold=0.02)

    resultado = BacktestEngine(
        config=BacktestConfig(
            initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0, close_at_end=False
        ),
        risk=risco(),
    ).run(candles, estrategia(), symbol="BTC/USDT")

    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    relogio = {"agora": candles.index[0]}
    runner = Runner(
        source=FonteFalsa(candles),
        strategy=estrategia(),
        client=cliente,
        risk=risco(),
        symbol="BTC/USDT",
        timeframe="1h",
        fee_rate=0.0, slippage_rate=0.0,
        now=lambda: relogio["agora"],
    )

    # Um passo logo apos o fechamento de cada candle, menos o ultimo: e o mesmo
    # conjunto de execucoes que o backtest faz nas aberturas seguintes.
    for timestamp in candles.index[:-1]:
        relogio["agora"] = timestamp + pd.Timedelta("1h")
        runner.step()

    do_runner = cliente.portfolio.fills
    do_backtest = resultado.fills
    assert len(do_runner) == len(do_backtest) > 0
    for i, (r, b) in enumerate(zip(do_runner, do_backtest)):
        assert r.side == b.side, f"fill {i}"
        assert r.quantity == pytest.approx(b.quantity, rel=1e-9), f"fill {i}"
        assert r.price == pytest.approx(b.price, rel=1e-9), f"fill {i}"

    assert cliente.portfolio.cash == pytest.approx(_caixa_final(resultado), rel=1e-9)


def _caixa_final(resultado):
    caixa = 1_000.0
    for fill in resultado.fills:
        sinal = 1.0 if fill.side.value == "buy" else -1.0
        caixa -= sinal * fill.quantity * fill.price + fill.fee
    return caixa


def test_runner_espera_a_estrategia_aceitar_o_historico():
    """Com menos candles do que a estrategia exige, o runner nao inventa decisao."""
    from robo_trader.strategies import build_strategy

    curto = make_candles([100.0] * 4, start="2024-01-01 00:00", freq="1h")
    runner = runner_de_teste(
        curto, "2024-01-01 04:00", strategy=build_strategy("ema_crossover", {"fast": 3, "slow": 7})
    )

    decisao = runner.step()

    assert decisao.action == "manteve"
    assert "insuficientes" in decisao.reason
    assert decisao.timestamp is None


# -- risco dentro do runner ------------------------------------------------


class PesoControlado(Strategy):
    """Estrategia que devolve o peso que o teste mandar."""

    name = "peso_controlado"

    def __init__(self, peso=0.0):
        super().__init__()
        self.peso = peso

    def generate_signals(self, df):
        return pd.Series(float(self.peso), index=df.index)


def passos(runner, candles, ate=-1):
    saida = []
    for timestamp in candles.index[:ate] if ate else candles.index:
        runner._now = lambda ts=timestamp: ts + pd.Timedelta("1h")
        saida.append(runner.step())
    return saida


def test_kill_switch_zera_a_posicao_e_para_de_operar():
    from robo_trader.risk import RiskConfig

    # Sobe, desaba 20% e tenta se recuperar.
    candles = make_candles([100.0, 100.0, 80.0, 82.0, 85.0], start="2024-01-01", freq="1h")
    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    runner = Runner(
        source=FonteFalsa(candles), strategy=PesoControlado(1.0), client=cliente,
        risk=RiskConfig(max_drawdown=0.10), symbol="BTC/USDT", timeframe="1h", fee_rate=0.0, slippage_rate=0.0,
        now=lambda: candles.index[0],
    )

    decisoes = passos(runner, candles)

    assert runner.risk.halted
    assert cliente.position("BTC/USDT").is_flat
    assert any(d.action == "bloqueado" for d in decisoes)
    assert "drawdown" in (runner.risk.blocked_reason or "")


def test_kill_switch_nao_religa_quando_o_preco_volta():
    from robo_trader.risk import RiskConfig

    candles = make_candles([100.0, 100.0, 80.0, 130.0, 140.0], start="2024-01-01", freq="1h")
    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    runner = Runner(
        source=FonteFalsa(candles), strategy=PesoControlado(1.0), client=cliente,
        risk=RiskConfig(max_drawdown=0.10), symbol="BTC/USDT", timeframe="1h", fee_rate=0.0, slippage_rate=0.0,
        now=lambda: candles.index[0],
    )

    passos(runner, candles)

    # Recuperar o capital nao desfaz a parada: quem religa e uma pessoa.
    assert runner.risk.halted
    assert cliente.position("BTC/USDT").is_flat


def test_desvio_menor_que_o_limite_nao_gira_a_carteira():
    from robo_trader.risk import RiskConfig

    candles = make_candles([100.0] * 4, start="2024-01-01", freq="1h")
    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    estrategia = PesoControlado(1.0)
    runner = Runner(
        source=FonteFalsa(candles), strategy=estrategia, client=cliente,
        risk=RiskConfig(rebalance_threshold=0.02), symbol="BTC/USDT", timeframe="1h",
        fee_rate=0.0, slippage_rate=0.0, now=lambda: candles.index[1],
    )

    runner.step()
    assert len(cliente.portfolio.fills) == 1

    estrategia.peso = 0.99  # desvio de 1%, abaixo do limite de 2%
    decisao = runner.step()

    assert decisao.action == "manteve"
    assert len(cliente.portfolio.fills) == 1


def test_ordem_abaixo_do_notional_minimo_do_risco_nao_sai():
    from robo_trader.risk import RiskConfig

    candles = make_candles([100.0] * 4, start="2024-01-01", freq="1h")
    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=20.0, fee_rate=0.0, slippage_rate=0.0
    )
    estrategia = PesoControlado(1.0)
    runner = Runner(
        source=FonteFalsa(candles), strategy=estrategia, client=cliente,
        risk=RiskConfig(min_trade_notional=10.0, rebalance_threshold=0.0),
        symbol="BTC/USDT", timeframe="1h", fee_rate=0.0, slippage_rate=0.0, now=lambda: candles.index[1],
    )

    runner.step()
    estrategia.peso = 0.6  # ajuste de 8 USDT, abaixo do minimo de 10
    decisao = runner.step()

    assert decisao.action == "manteve"
    assert len(cliente.portfolio.fills) == 1


# -- laco ------------------------------------------------------------------


def runner_com_relogio(candles, inicio, **kwargs):
    relogio = {"agora": pd.Timestamp(inicio, tz="UTC")}
    dormidas = []

    def dormir(segundos):
        dormidas.append(segundos)
        relogio["agora"] += pd.Timedelta(seconds=segundos)

    runner = Runner(
        source=FonteFalsa(candles),
        strategy=PesoControlado(0.0),
        client=PaperExecutionClient(
            symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
        ),
        symbol="BTC/USDT",
        timeframe="1h",
        fee_rate=0.0, slippage_rate=0.0,
        now=lambda: relogio["agora"],
        sleep=dormir,
        **kwargs,
    )
    return runner, dormidas, relogio


def test_run_espera_ate_o_proximo_fechamento_de_candle():
    candles = make_candles([100.0] * 12, start="2024-01-01 00:00", freq="1h")
    runner, dormidas, _ = runner_com_relogio(candles, "2024-01-01 10:17", close_delay=2.0)

    runner.run(max_steps=1)

    # 10:17 -> 11:00 sao 43 minutos, mais a folga para a corretora publicar o candle.
    assert dormidas == [pytest.approx(43 * 60 + 2.0)]


def test_run_para_no_numero_de_passos_pedido():
    candles = make_candles([100.0] * 12, start="2024-01-01 00:00", freq="1h")
    runner, dormidas, _ = runner_com_relogio(candles, "2024-01-01 10:00")

    decisoes = runner.run(max_steps=3)

    assert len(decisoes) == 3
    assert len(dormidas) == 3


def test_run_entrega_cada_decisao_ao_observador():
    candles = make_candles([100.0] * 12, start="2024-01-01 00:00", freq="1h")
    runner, _, _ = runner_com_relogio(candles, "2024-01-01 10:00")
    vistas = []

    runner.run(max_steps=2, on_decision=vistas.append)

    assert len(vistas) == 2
    assert all(isinstance(d.action, str) for d in vistas)


def test_compra_cheia_cabe_no_caixa_mesmo_com_slippage():
    """Comprar com 100% do caixa pelo preco de referencia estoura na execucao.

    O preco que sai e pior que o de referencia; dimensionar sem contar isso faz a
    corretora recusar a ordem por saldo — e no paper, levantar ExecutionError.
    """
    candles = make_candles([100.0] * 12, start="2024-01-01", freq="1h")
    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.001, slippage_rate=0.0005
    )
    runner = Runner(
        source=FonteFalsa(candles),
        strategy=PesoControlado(1.0),
        client=cliente,
        symbol="BTC/USDT",
        timeframe="1h",
        fee_rate=0.001,
        slippage_rate=0.0005,
        now=lambda: candles.index[-1] + pd.Timedelta("1h"),
    )

    decisao = runner.step()

    assert decisao.action == "comprou"
    # Usou praticamente todo o caixa e nao estourou: a compra cheia cabe.
    assert cliente.portfolio.cash == pytest.approx(0.0, abs=1e-9)


def test_runner_pede_a_janela_mais_recente_de_candles():
    """Sem janela explicita, a fonte pode devolver o comeco do historico.

    O `limit` do CcxtMarketData e tamanho de pagina, nao "os N ultimos": pedir so
    por limit traz candles de semanas atras, e o robo decidiria sobre preco velho.
    """

    class FonteQueRegistra(FonteFalsa):
        pedido = None

        def fetch_ohlcv(self, symbol, timeframe, since=None, until=None, limit=None):
            self.pedido = {"since": since, "limit": limit}
            return self.candles

    candles = make_candles([100.0] * 600, start="2024-01-01 00:00", freq="1h")
    fonte = FonteQueRegistra(candles)
    agora = pd.Timestamp("2024-02-01 00:00", tz="UTC")
    runner = Runner(
        source=fonte, strategy=PesoControlado(0.0),
        client=PaperExecutionClient(
            symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
        ),
        symbol="BTC/USDT", timeframe="1h", history=500,
        fee_rate=0.0, slippage_rate=0.0, now=lambda: agora,
    )

    runner.step()

    assert fonte.pedido["since"] == agora - pd.Timedelta(hours=500)


# -- frescor dos dados -----------------------------------------------------


def test_recusa_operar_com_candle_velho():
    """Feed parado devolve candle antigo. Operar nele e decidir com preco de ontem."""
    # Ultimo candle fecha as 12:00; sao 15:00 e nada novo chegou.
    candles = make_candles([100.0, 110.0, 120.0], start="2024-01-01 09:00", freq="1h")
    runner = runner_de_teste(candles, "2024-01-01 15:00")

    decisao = runner.step()

    assert decisao.action == "bloqueado"
    assert "atrasado" in decisao.reason


def test_candle_recem_fechado_passa_na_trava_de_frescor():
    candles = make_candles([100.0, 110.0, 120.0], start="2024-01-01 09:00", freq="1h")
    runner = runner_de_teste(candles, "2024-01-01 12:00:02")

    decisao = runner.step()

    assert decisao.action == "comprou"


# -- identidade do giro ----------------------------------------------------


class ClienteQueRegistra(PaperExecutionClient):
    """Cliente de papel que guarda as ordens recebidas."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.recebidas = []

    def submit(self, order, price=None):
        self.recebidas.append(order)
        return super().submit(order, price)


def test_ordem_carrega_identidade_do_candle():
    """Chave estavel por vela: retentativa depois de timeout nao vira ordem nova."""
    candles = make_candles([100.0, 110.0, 120.0], start="2024-01-01 09:00", freq="1h")
    cliente = ClienteQueRegistra(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    runner = runner_de_teste(candles, "2024-01-01 12:00:02", client=cliente)

    runner.step()

    # 1704106800000 = 2024-01-01 11:00 UTC, o ultimo candle fechado as 12:00.
    assert cliente.recebidas[0].client_id == "BTCUSDT-buy-1704106800000"


# -- tetos de giro dentro do runner ----------------------------------------


def test_teto_por_ordem_limita_a_compra():
    from robo_trader.risk import RiskConfig

    candles = make_candles([100.0, 110.0, 120.0], start="2024-01-01 09:00", freq="1h")
    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    runner = runner_de_teste(
        candles, "2024-01-01 12:00:02", strategy=PesoControlado(1.0), client=cliente,
        risk=RiskConfig(max_trade_notional=200.0),
    )

    decisao = runner.step()

    assert decisao.action == "comprou"
    assert decisao.fill.quantity * decisao.fill.price == pytest.approx(200.0)


def test_cooldown_bloqueia_o_giro_seguinte():
    from robo_trader.risk import RiskConfig, RiskManager

    candles = make_candles([100.0, 110.0, 120.0], start="2024-01-01 09:00", freq="1h")
    gestor = RiskManager(RiskConfig(trade_cooldown=3_600.0))
    gestor.register_trade(pd.Timestamp("2024-01-01 10:30", tz="UTC"), 100.0)
    runner = runner_de_teste(
        candles, "2024-01-01 12:00:02", strategy=PesoControlado(1.0), risk=gestor,
    )

    decisao = runner.step()

    assert decisao.action == "bloqueado"
    assert "espera" in decisao.reason


def test_teto_nao_prende_o_robo_dentro_da_posicao():
    """Teto limita risco novo. Barrar a saida transformaria protecao em armadilha."""
    from robo_trader.risk import RiskConfig

    candles = make_candles([100.0, 100.0, 300.0], start="2024-01-01 09:00", freq="1h")
    cliente = PaperExecutionClient(
        symbol="BTC/USDT", initial_cash=1_000.0, fee_rate=0.0, slippage_rate=0.0
    )
    estrategia = PesoControlado(1.0)
    runner = runner_de_teste(
        candles, "2024-01-01 11:00:02", strategy=estrategia, client=cliente,
        risk=RiskConfig(max_trade_notional=200.0),
    )
    runner.step()  # compra 2 BTC a 100, no teto

    estrategia.peso = 0.0
    runner._now = lambda: pd.Timestamp("2024-01-01 12:00:02", tz="UTC")
    decisao = runner.step()

    assert decisao.action == "vendeu"
    assert decisao.fill.quantity == pytest.approx(2.0)  # saida inteira, valendo 600

# Robô Trader

Robô de negociação de criptomoedas em Python: ingestão de candles, backtest sem
antecipação de dados, gestão de risco e uma camada de execução que separa
simulação de dinheiro real.

O estado atual cobre **dados + backtest**. A execução real existe como interface
com as travas de segurança já no lugar, mas desligada.

## Instalação

```bash
cd robo-trader
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[exchange,dev]"
```

Sem o extra `exchange` o pacote funciona normalmente para backtest sobre CSV — o
`ccxt` só é necessário para baixar candles da corretora.

## Uso

```bash
# estratégias registradas
robo-trader strategies

# baixar candles reais da Binance
robo-trader fetch --symbol BTC/USDT --timeframe 1h \
    --since 2023-01-01 --out data/BTCUSDT_1h.csv

# backtest com travas de risco
robo-trader backtest --csv data/BTCUSDT_1h.csv --symbol BTC/USDT \
    --strategy donchian_breakout --param entry=20 --param exit=10 \
    --stop-loss 0.05 --max-drawdown 0.25 --report reports/donchian

# sem dados em mãos: candles sintéticos para exercitar o motor
robo-trader backtest --synthetic --strategy ema_crossover --param fast=12 --param slow=26
```

Saída típica:

```
Backtest donchian_breakout(entry=20, exit=10) em BTC/USDT
Periodo: 2024-01-01 a 2024-05-04  (3000 candles)
----------------------------------------------------
Capital inicial                  10,000.00
Capital final                    14,640.57
Retorno total                       46.41%
Buy & hold                         230.94%
Retorno anualizado (CAGR)          204.50%
Sharpe                                2.16
Drawdown maximo                    -20.50%
Tempo exposto                       39.67%
Trades fechados                         51
Acerto                              50.98%
Fator de lucro                        1.68
Custos totais                     1,034.21
```

Esse exemplo roda sobre candles **sintéticos** e não diz nada sobre o desempenho
da estratégia no mercado: serve só para mostrar o formato do relatório.

Em Python:

```python
from robo_trader import BacktestConfig, BacktestEngine, RiskConfig, build_strategy
from robo_trader.data import CsvMarketData

candles = CsvMarketData("data").fetch_ohlcv("BTC/USDT", "1h", since="2023-01-01")
engine = BacktestEngine(
    config=BacktestConfig(initial_cash=10_000, fee_rate=0.001, slippage_rate=0.0005),
    risk=RiskConfig(max_position_weight=0.5, stop_loss_pct=0.05, max_drawdown=0.25),
)
resultado = engine.run(candles, build_strategy("ema_crossover", {"fast": 12, "slow": 26}), "BTC/USDT")
print(resultado.summary())
resultado.save("reports/ema")
```

## Arquitetura

```
src/robo_trader/
  domain.py        Order, Fill, Trade, Position — tipos comuns a todas as camadas
  indicators.py    EMA, SMA, RSI, ATR, Donchian
  data/            ingestão: schema/validação, CCXT, CSV, candles sintéticos
  strategies/      candles -> peso alvo da carteira, em [-1, 1]
  backtest/        carteira simulada, motor candle a candle, métricas, relatório
  risk/            teto de exposição, stop/alvo, limite diário e kill switch
  execution/       interface de execução: paper (simulada) e live (real, travada)
  cli.py           comandos fetch / backtest / strategies
```

O fluxo é sempre o mesmo: **fonte de dados → estratégia → risco → execução**. O
backtest e o paper trading usam a mesma classe `Portfolio`, então os dois
resultados são comparáveis.

### Contrato das estratégias

Uma estratégia recebe os candles e devolve uma série de pesos da carteira: `1`
comprado com todo o capital elegível, `-1` vendido, `0` fora. Cada peso pode usar
apenas informação até o fechamento daquele candle.

```python
class MinhaEstrategia(Strategy):
    name = "minha_estrategia"

    @property
    def warmup(self) -> int:
        return 20

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        ...
```

Registre em `strategies/registry.py` e ela aparece na CLI.

## Como o backtest evita enganar

Backtest otimista demais vira prejuízo real. As decisões do motor:

- **Sem antecipação de dados.** O sinal lido no fechamento do candle `t` só vira
  ordem na abertura de `t+1`. Um teste alimenta o motor com um sinal que "adivinha"
  a alta do próprio candle e verifica que ele não lucra com isso.
- **Custos sempre cobrados.** Corretagem (0,1% padrão, taker da Binance spot) e
  slippage (0,05%) entram em toda execução, inclusive nas zeragens.
- **Stop antes do alvo.** Quando o candle toca stop e take profit, a simulação
  assume que o stop veio primeiro.
- **Sem alavancagem acidental.** A compra é limitada ao caixa disponível já
  descontadas as taxas; o caixa nunca fica negativo.
- **Buy & hold no relatório.** Toda comparação mostra quanto renderia só comprar e
  segurar no mesmo período.

O que ainda **não** é modelado: profundidade de livro (ordens grandes movem o
preço), funding de perpétuos, indisponibilidade da corretora e variação de taxa
por nível de volume.

## Gestão de risco

| Parâmetro | Efeito |
|---|---|
| `max_position_weight` | Teto de exposição por posição |
| `stop_loss_pct` / `take_profit_pct` | Saídas avaliadas dentro do candle |
| `max_daily_loss` | Bloqueia novas exposições até o fim do dia |
| `max_drawdown` | Kill switch: zera a posição e para de operar |
| `min_trade_notional` | Descarta ordens-poeira |
| `rebalance_threshold` | Evita girar a carteira por desvio irrelevante |

O bloqueio diário expira na virada do dia. O kill switch não religa sozinho — nem
depois que o capital se recupera.

## Execução real

`LiveExecutionClient` fala com a corretora via CCXT e exige **duas autorizações
independentes** para enviar qualquer ordem:

1. `enabled=True` no código;
2. `ROBO_TRADER_ALLOW_LIVE=1` no ambiente.

Faltando uma delas, `submit` recusa a ordem. Credenciais vêm de
`ROBO_TRADER_API_KEY` / `ROBO_TRADER_API_SECRET` — copie `.env.example` para
`.env` e não comite o arquivo.

Nenhuma estratégia conversa com a corretora diretamente: tudo passa pela
interface `ExecutionClient`, e é por isso que a trava mora em um lugar só.

## Testes

```bash
pytest
```

126 testes cobrem validação de dados, indicadores, estratégias, contabilidade da
carteira, ausência de antecipação de dados, disparo de stop e alvo, kill switch,
métricas, paginação da corretora (com dublê, sem rede) e as travas do modo real.

## Próximos passos

1. Walk-forward e otimização de parâmetros com validação fora da amostra.
2. Runner de paper trading em tempo real sobre o `PaperExecutionClient`.
3. Carteira com vários símbolos e alocação entre eles.
4. Persistência de estado e observabilidade (logs estruturados, alertas).
5. Homologação em testnet antes de qualquer ordem com dinheiro real.

## Aviso

Software para estudo e pesquisa. Resultado de backtest não é promessa de
resultado futuro, e negociação de criptomoedas pode zerar o capital. Quem liga o
modo real assume o risco.

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
  config.py        leitura do .env e credenciais, sem dependência externa
  indicators.py    EMA, SMA, RSI, ATR, Donchian
  data/            ingestão: schema/validação, CCXT, CSV, candles sintéticos
  strategies/      candles -> peso alvo da carteira, em [-1, 1]
  backtest/        carteira simulada, motor candle a candle, métricas, relatório
  risk/            teto de exposição, stop/alvo, limite diário e kill switch
  execution/       interface de execução: paper, testnet e live (real, travada)
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

## Modos de execução

Três modos atrás da mesma interface `ExecutionClient`, o que permite trocar
simulação por dinheiro real sem mexer em estratégia nenhuma:

| Modo | O que faz | O que exige |
|---|---|---|
| `paper` | Carteira em memória, sem tocar na corretora | nada |
| `testnet` | Ordens no ambiente de homologação, saldo fictício | credenciais de testnet |
| `live` | Ordens reais, com dinheiro de verdade | `enabled=True` **e** `ROBO_TRADER_ALLOW_LIVE=1` |

```python
from robo_trader import build_execution_client, load_env_file

load_env_file()                                    # lê o .env do diretório atual
cliente = build_execution_client("testnet", "BTC/USDT")
print(cliente.balance())
```

Pedir `"live"` na fábrica **não** dispensa as duas travas: o nome do modo
costuma vir de arquivo de configuração, e isso é fraco demais para ser a única
coisa entre um script e o dinheiro de verdade.

### Homologação na testnet

As chaves da testnet são separadas das reais — gere as suas em
[testnet.binance.vision](https://testnet.binance.vision) e coloque no `.env`:

```bash
cp .env.example .env
# ROBO_TRADER_API_KEY / ROBO_TRADER_API_SECRET = chaves da testnet
# ROBO_TRADER_TESTNET=1
# ROBO_TRADER_ALLOW_LIVE=0
```

Internamente o modo testnet chama `set_sandbox_mode(True)` no cliente CCXT, que
redireciona os endpoints. Se a corretora configurada não tiver ambiente de
homologação no CCXT, o cliente recusa em vez de cair silenciosamente na conta real.

**Os candles continuam vindo da rede principal.** A testnet tem liquidez e
histórico artificiais; homologar o *envio de ordem* lá é útil, medir estratégia
com dados de lá não é.

### Antes de ligar o dinheiro real

1. Backtest com custos realistas e walk-forward fora da amostra.
2. Paper trading em tempo real, para pegar divergência entre simulação e mercado.
3. Testnet, para validar o caminho da ordem de ponta a ponta.
4. Só então `live`, com capital pequeno e `max_drawdown` apertado.

### Credenciais

Vêm de `ROBO_TRADER_API_KEY` / `ROBO_TRADER_API_SECRET`, pelo ambiente ou pelo
`.env` (que está no `.gitignore`). Variável exportada no shell vence o arquivo.
O `repr` das credenciais nunca imprime os valores, para que chave não vaze em log
ou traceback.

Na corretora, para a chave que o robô vai usar: **saques desabilitados**,
allowlist de IP, e só as permissões que o robô precisa de fato.

## Testes

```bash
pytest
```

145 testes cobrem validação de dados, indicadores, estratégias, contabilidade da
carteira, ausência de antecipação de dados, disparo de stop e alvo, kill switch,
métricas, paginação da corretora (com dublê, sem rede), as travas do modo real e o
roteamento da testnet.

## Próximos passos

1. Walk-forward e otimização de parâmetros com validação fora da amostra.
2. Runner em tempo real, reaproveitando os três modos de execução.
3. Carteira com vários símbolos e alocação entre eles.
4. Persistência de estado e observabilidade (logs estruturados, alertas).

## Aviso

Software para estudo e pesquisa. Resultado de backtest não é promessa de
resultado futuro, e negociação de criptomoedas pode zerar o capital. Quem liga o
modo real assume o risco.

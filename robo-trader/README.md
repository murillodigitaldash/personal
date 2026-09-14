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

# antes da primeira ordem: confere credenciais, conexão, regras do par e saldo
robo-trader preflight --mode testnet --symbol BTC/USDT --notional 20

# opera em tempo real, um passo por candle fechado (paper não toca na corretora)
robo-trader run --mode paper --symbol BTC/USDT --timeframe 1h \
    --strategy ema_crossover --param fast=12 --param slow=26 --cash 1000
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
  execution/       interface de execução: paper, testnet e live (real, travada),
                   regras do par e preflight
  runner.py        laco em tempo real: candle fechado -> decisao -> ordem
  cli.py           comandos fetch / backtest / strategies / preflight / run
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

## Operar em tempo real

```bash
robo-trader run --mode paper --timeframe 1h --strategy ema_crossover
```

```
robo-trader paper em BTC/USDT 1m — ema_crossover(allow_short=False, fast=5, slow=15)
um passo por candle fechado. Ctrl+C para parar.

2026-09-14 20:09     79,036.16  alvo +1.00  atual +0.00  comprou: peso +0.00 -> +1.00
2026-09-14 20:10     79,036.15  alvo +1.00  atual +1.00  manteve: sem desvio que pague o giro
```

O runner liga **fonte de candles → estratégia → risco → execução**, e não sabe se o
cliente de execução é simulado, testnet ou real: a decisão é a mesma nos três.

`--once` decide uma vez e sai, o que serve para rodar por cron. `--steps N` para
depois de N candles. `--csv` lê de arquivo em vez da corretora e posiciona o
relógio no fim do arquivo, para ensaiar sem rede.

### O candle aberto não tem sinal

Esta é a regra que o módulo existe para garantir. O backtest lê o sinal no
fechamento de `t` e executa na abertura de `t+1`; em tempo real o equivalente é
agir **logo depois que o candle fecha**. O candle corrente, que ainda está se
formando, é descartado — usá-lo seria antecipação de dados, o mesmo erro que o
backtest evita, só que aqui custando dinheiro de verdade.

Por isso o runner espera o fechamento com uma folga de 2 segundos: pedir o candle
no instante exato costuma devolver a vela ainda aberta.

### Mesma decisão que o backtest

Um teste roda o motor de backtest e o runner sobre a mesma série e compara
**fill a fill** — lado, quantidade, preço — e o caixa final. Se divergirem, o
backtest está mentindo sobre o que aconteceria de verdade, e o teste quebra.

O dimensionamento da compra desconta taxa **e** slippage do caixa disponível. Sem
isso, uma compra de 100% do capital é recusada por saldo: o preço que sai é pior
que o de referência.

### O que o runner ainda não faz

- **Stop loss e take profit em tempo real.** O backtest zera a posição
  exatamente no preço do stop, olhando a máxima e a mínima do candle. Ao vivo
  isso é impossível: você só percebe o rompimento no fechamento e sai onde o
  mercado estiver. Por isso `--stop-loss` e `--take-profit` **não existem** no
  `run` — expor a flag sem a implementação seria mentir sobre a proteção. O jeito
  certo é ordem de stop na corretora, e isso é trabalho à parte.
- **Persistência.** Posição, kill switch e perda do dia vivem em memória. Se o
  processo cair no meio de uma posição, o robô volta sem saber que está comprado.
- **Vários símbolos.** Um runner opera um par.

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

### Ler não é operar

As travas do modo real valem para **enviar ordem**. `balance()` e `position()`
pedem só credenciais: leitura não move dinheiro, e exigir a autorização de ordem
para conferir a conta empurraria quem está conferindo a ligar a trava antes da
hora — exatamente o que ela deveria evitar. `submit()` continua exigindo as duas.

A moeda de cotação sai do próprio par: quem opera `BTC/BRL` tem o saldo conferido
em BRL, não em USDT.

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

### Preflight: o que conferir antes da primeira ordem

Homologação costuma falhar sempre pelas mesmas coisas — credencial do ambiente
errado, sandbox que não ligou, par fora da lista, ordem abaixo do notional
mínimo. Descobrir uma de cada vez, a cada ordem recusada, é caro. O `preflight`
junta tudo num relatório e **não envia ordem nenhuma**:

```bash
robo-trader preflight --mode testnet --notional 20
```

```
Preflight testnet em BTC/USDT
-----------------------------
[ok] modo: homologacao: saldo ficticio, ordem nao vale dinheiro real
[FALHA] credenciais: faltando ROBO_TRADER_API_KEY/ROBO_TRADER_API_SECRET no .env ou no ambiente
[ok] conexao: binance respondeu em testnet
[ok] regras do par: passo 0.00001, minimo 0.00001, notional minimo 5
[FALHA] saldo: nao foi possivel ler o saldo: credenciais da testnet ausentes (API key/secret)
[ok] notional: ordem de 20.00 cabe no par (saldo nao verificado)

NAO PRONTO para enviar ordem em testnet
```

Ele confere, nesta ordem: as travas do modo, as credenciais, a conexão com o
ambiente certo, as regras do par, **as permissões da chave**, o saldo e o notional
pretendido.

Sai com código 1 quando reprova, então serve em script e em CI. Um detalhe de
propósito: o relatório nunca afirma o que não conseguiu verificar — sem saldo
lido, o notional sai como "saldo não verificado", e não como "cabe"; sem resposta
da corretora sobre a chave, as permissões saem como "não verificadas".

A checagem de permissão é a que mais economiza tempo: chave só de leitura é
recusada pela corretora na hora da ordem, muito depois de tudo parecer certo.
O preflight lê `enableSpotAndMarginTrading` e reprova antes — e também reprova
chave com **saque habilitado**, que não tem por que existir num robô.

O `--mode live` vai sempre reprovar a trava `enabled=True`, porque essa
autorização mora no código de quem opera, não na linha de comando. A CLI não
tem como liberar dinheiro real, e isso é intencional.

### Regras do par

Corretora recusa ordem que não respeite o passo de quantidade, o mínimo do par
ou o notional mínimo — na Binance o BTC/USDT anda com passo de 0.00001 BTC e
notional mínimo de 5 USDT. Descobrir isso com a ordem recusada, no meio de uma
operação, custa a operação.

Por isso o cliente lê as regras publicadas pela corretora (uma vez por sessão) e,
antes de enviar:

- **trunca a quantidade** para o passo do par — sempre para baixo, porque comprar
  mais do que a estratégia pediu é pior do que comprar um pouco menos;
- **ajusta o preço** da ordem limit ao tick;
- **recusa antes de enviar** o que ficou abaixo do mínimo do par ou do notional
  mínimo, dizendo qual dos dois foi.

Falha de rede ao ler as regras não vira "esse par não tem regras": a ordem é
recusada e a leitura é tentada de novo na próxima, para que uma queda de conexão
nunca resulte em ordem enviada sem ajuste.

### Antes de ligar o dinheiro real

1. Backtest com custos realistas e walk-forward fora da amostra.
2. Paper trading em tempo real, para pegar divergência entre simulação e mercado.
3. `preflight` verde na testnet, com o notional que se pretende operar.
4. Testnet, para validar o caminho da ordem de ponta a ponta.
5. Só então `live`, com capital pequeno e `max_drawdown` apertado.

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

199 testes cobrem validação de dados, indicadores, estratégias, contabilidade da
carteira, ausência de antecipação de dados, disparo de stop e alvo, kill switch,
métricas, paginação da corretora (com dublê, sem rede), as travas do modo real, o
roteamento da testnet, o ajuste de quantidade e preço às regras do par, a
separação entre leitura e ordem, o relatório de preflight (incluindo permissões
da chave) e o runner — inclusive a equivalência fill a fill com o backtest e a
recusa em operar sobre candle ainda aberto. Nenhum teste toca a rede.

## Próximos passos

1. Paper trading em tempo real por alguns dias, comparado com o backtest do mesmo
   período — divergência grande ali significa que o backtest está mentindo.
2. Walk-forward e otimização de parâmetros com validação fora da amostra.
3. Persistência de estado e observabilidade (logs estruturados, alertas), para o
   robô sobreviver a um restart no meio de uma posição.
4. Stop loss como ordem na corretora, em vez de avaliação no fechamento.
5. Carteira com vários símbolos e alocação entre eles.

## Aviso

Software para estudo e pesquisa. Resultado de backtest não é promessa de
resultado futuro, e negociação de criptomoedas pode zerar o capital. Quem liga o
modo real assume o risco.

"""Interface de linha de comando do robo."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

import pandas as pd

from .backtest import BacktestConfig, BacktestEngine
from .config import EXCHANGE_ENV, load_env_file
from .data import CsvMarketData, generate_ohlcv, write_ohlcv
from .data.schema import timeframe_to_timedelta
from .execution import MODES, build_execution_client, preflight
from .risk import RiskConfig
from .runner import Runner
from .strategies import available, build_strategy


def _parse_params(items: list[str] | None) -> dict:
    """Converte `chave=valor` da linha de comando em parametros tipados."""
    params: dict = {}
    for item in items or []:
        if "=" not in item:
            raise argparse.ArgumentTypeError(f"parametro '{item}' deve ter a forma chave=valor")
        key, _, raw = item.partition("=")
        value: object = raw
        if raw.lower() in {"true", "false"}:
            value = raw.lower() == "true"
        else:
            try:
                value = int(raw)
            except ValueError:
                try:
                    value = float(raw)
                except ValueError:
                    value = raw
        params[key.strip()] = value
    return params


def _load_candles(args: argparse.Namespace) -> pd.DataFrame:
    if args.synthetic:
        return generate_ohlcv(
            periods=args.synthetic_periods, timeframe=args.timeframe, seed=args.seed
        )
    if not args.csv:
        raise SystemExit("informe --csv com os candles ou use --synthetic para dados de teste")
    source = CsvMarketData(args.csv)
    return source.fetch_ohlcv(args.symbol, args.timeframe, since=args.since, until=args.until)


def cmd_strategies(args: argparse.Namespace) -> int:
    for name in available():
        strategy = build_strategy(name)
        print(f"{name:<20} {strategy.describe()}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    from .data.ccxt_source import CcxtMarketData

    source = CcxtMarketData(exchange_id=args.exchange, cache_dir=args.cache_dir)
    df = source.fetch_ohlcv(args.symbol, args.timeframe, since=args.since, until=args.until)
    if args.out:
        path = write_ohlcv(df, args.out)
        print(f"{len(df)} candles gravados em {path}")
    else:
        print(f"{len(df)} candles de {df.index[0]} ate {df.index[-1]}")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    candles = _load_candles(args)
    strategy = build_strategy(args.strategy, _parse_params(args.param))

    engine = BacktestEngine(
        config=BacktestConfig(
            initial_cash=args.cash,
            fee_rate=args.fee,
            slippage_rate=args.slippage,
            risk_free_rate=args.risk_free,
        ),
        risk=RiskConfig(
            max_position_weight=args.max_weight,
            stop_loss_pct=args.stop_loss,
            take_profit_pct=args.take_profit,
            max_daily_loss=args.max_daily_loss,
            max_drawdown=args.max_drawdown,
            min_trade_notional=args.min_notional,
            rebalance_threshold=args.rebalance_threshold,
        ),
    )
    result = engine.run(candles, strategy, symbol=args.symbol)

    if args.json:
        print(json.dumps(result.metrics, indent=2, default=float))
    else:
        print(result.summary())

    if args.report:
        files = result.save(args.report)
        print("\nRelatorios gravados:")
        for label, path in files.items():
            print(f"  {label:<8} {path}")
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    """Confere o caminho da ordem antes da primeira ordem de verdade."""
    extras = {} if args.mode == "paper" else {"exchange_id": args.exchange}
    client = build_execution_client(args.mode, args.symbol, **extras)

    report = preflight(client, notional=args.notional)
    print(report.summary())
    print("\nNenhuma ordem foi enviada.")
    return 0 if report.ok else 1


def cmd_run(args: argparse.Namespace) -> int:
    """Opera em tempo real: estrategia -> risco -> execucao, um passo por candle."""
    if args.mode == "live":
        raise SystemExit(
            "modo live nao e operavel pela linha de comando: a segunda autorizacao mora "
            "no codigo de quem opera. Use --mode paper ou --mode testnet."
        )

    agora = None
    if args.csv:
        source = CsvMarketData(args.csv)
        # Ensaio offline: o relogio vai para o fim do arquivo, senao a janela de
        # candles recentes descartaria um historico que e todo passado.
        historico = source.fetch_ohlcv(args.symbol, args.timeframe)
        if len(historico):
            fim = historico.index[-1] + timeframe_to_timedelta(args.timeframe)
            agora = lambda: fim  # noqa: E731
    else:
        from .data.ccxt_source import CcxtMarketData

        # Candles vem sempre da rede principal: a testnet tem preco artificial.
        source = CcxtMarketData(exchange_id=args.exchange, cache_dir=args.cache_dir)

    if args.mode == "paper":
        extras = dict(initial_cash=args.cash, fee_rate=args.fee, slippage_rate=args.slippage)
    else:
        extras = dict(exchange_id=args.exchange)
    client = build_execution_client(args.mode, args.symbol, **extras)

    strategy = build_strategy(args.strategy, _parse_params(args.param))
    runner = Runner(
        source=source,
        strategy=strategy,
        client=client,
        risk=RiskConfig(
            max_position_weight=args.max_weight,
            max_daily_loss=args.max_daily_loss,
            max_drawdown=args.max_drawdown,
            min_trade_notional=args.min_notional,
            rebalance_threshold=args.rebalance_threshold,
        ),
        symbol=args.symbol,
        timeframe=args.timeframe,
        history=args.history,
        fee_rate=args.fee,
        slippage_rate=args.slippage,
        **({"now": agora} if agora is not None else {}),
    )

    print(f"robo-trader {args.mode} em {args.symbol} {args.timeframe} — {strategy.describe()}")

    if args.once:
        print(runner.step())
        return 0

    print("um passo por candle fechado. Ctrl+C para parar.\n")
    try:
        runner.run(max_steps=args.steps, on_decision=lambda d: print(d, flush=True))
    except KeyboardInterrupt:
        print("\ninterrompido")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="robo-trader", description="Robo trader de criptomoedas: dados, backtest e execucao"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="loga detalhes da execucao")
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("strategies", help="lista as estrategias registradas")
    listing.set_defaults(func=cmd_strategies)

    fetch = subparsers.add_parser("fetch", help="baixa candles da exchange via ccxt")
    fetch.add_argument("--exchange", default="binance")
    fetch.add_argument("--symbol", default="BTC/USDT")
    fetch.add_argument("--timeframe", default="1h")
    fetch.add_argument("--since", default=None, help="data inicial, ex.: 2024-01-01")
    fetch.add_argument("--until", default=None, help="data final, ex.: 2024-12-31")
    fetch.add_argument("--out", default=None, help="arquivo CSV/Parquet de saida")
    fetch.add_argument("--cache-dir", default=None, help="diretorio de cache dos candles")
    fetch.set_defaults(func=cmd_fetch)

    backtest = subparsers.add_parser("backtest", help="roda um backtest")
    backtest.add_argument("--csv", default=None, help="arquivo ou diretorio com os candles")
    backtest.add_argument("--synthetic", action="store_true", help="usa candles sinteticos")
    backtest.add_argument("--synthetic-periods", type=int, default=2000)
    backtest.add_argument("--seed", type=int, default=42)
    backtest.add_argument("--symbol", default="BTC/USDT")
    backtest.add_argument("--timeframe", default="1h")
    backtest.add_argument("--since", default=None)
    backtest.add_argument("--until", default=None)
    backtest.add_argument("--strategy", default="ema_crossover", choices=available())
    backtest.add_argument(
        "--param", action="append", metavar="CHAVE=VALOR", help="parametro da estrategia"
    )
    backtest.add_argument("--cash", type=float, default=10_000.0)
    backtest.add_argument("--fee", type=float, default=0.001, help="taxa por ordem (0.001 = 0,1%%)")
    backtest.add_argument("--slippage", type=float, default=0.0005)
    backtest.add_argument("--risk-free", type=float, default=0.0, help="taxa livre de risco anual")
    backtest.add_argument("--max-weight", type=float, default=1.0)
    backtest.add_argument("--stop-loss", type=float, default=0.0)
    backtest.add_argument("--take-profit", type=float, default=0.0)
    backtest.add_argument("--max-daily-loss", type=float, default=0.0)
    backtest.add_argument("--max-drawdown", type=float, default=0.0)
    backtest.add_argument("--min-notional", type=float, default=10.0)
    backtest.add_argument("--rebalance-threshold", type=float, default=0.02)
    backtest.add_argument("--report", default=None, help="diretorio para gravar os relatorios")
    backtest.add_argument("--json", action="store_true", help="imprime as metricas em JSON")
    backtest.set_defaults(func=cmd_backtest)

    run = subparsers.add_parser(
        "run", help="opera em tempo real (paper ou testnet), um passo por candle fechado"
    )
    run.add_argument("--mode", default="paper", choices=MODES)
    run.add_argument("--symbol", default="BTC/USDT")
    run.add_argument("--timeframe", default="1h")
    run.add_argument("--strategy", default="ema_crossover", choices=available())
    run.add_argument("--param", action="append", metavar="CHAVE=VALOR")
    run.add_argument("--csv", default=None, help="le candles de arquivo em vez da corretora")
    run.add_argument("--exchange", default=os.getenv(EXCHANGE_ENV, "binance"))
    run.add_argument("--cache-dir", default=None)
    run.add_argument("--history", type=int, default=500, help="candles de historico por passo")
    run.add_argument("--cash", type=float, default=1_000.0, help="capital inicial no modo paper")
    run.add_argument("--fee", type=float, default=0.001)
    run.add_argument("--slippage", type=float, default=0.0005)
    run.add_argument("--max-weight", type=float, default=1.0)
    run.add_argument("--max-daily-loss", type=float, default=0.0)
    run.add_argument("--max-drawdown", type=float, default=0.0)
    run.add_argument("--min-notional", type=float, default=10.0)
    run.add_argument("--rebalance-threshold", type=float, default=0.02)
    run.add_argument("--steps", type=int, default=None, help="para depois de N candles")
    run.add_argument(
        "--once",
        action="store_true",
        help="decide uma vez e sai. Serve em cron apenas em testnet/live, onde a posicao "
        "mora na corretora: em paper o estado e de memoria e cada chamada comeca zerada",
    )
    run.set_defaults(func=cmd_run)

    preflight_cmd = subparsers.add_parser(
        "preflight", help="confere credenciais, conexao, regras do par e saldo sem enviar ordem"
    )
    preflight_cmd.add_argument("--mode", default="testnet", choices=MODES)
    preflight_cmd.add_argument("--symbol", default="BTC/USDT")
    preflight_cmd.add_argument("--exchange", default=os.getenv(EXCHANGE_ENV, "binance"))
    preflight_cmd.add_argument(
        "--notional",
        type=float,
        default=None,
        help="tamanho pretendido da ordem na moeda de cotacao, para conferir minimo e saldo",
    )
    preflight_cmd.set_defaults(func=cmd_preflight)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Credenciais e travas saem do .env do diretorio de trabalho, quando existir.
    load_env_file()
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

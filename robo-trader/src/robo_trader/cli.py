"""Interface de linha de comando do robo."""

from __future__ import annotations

import argparse
import json
import logging
import sys

import pandas as pd

from .backtest import BacktestConfig, BacktestEngine
from .config import load_env_file
from .data import CsvMarketData, generate_ohlcv, write_ohlcv
from .risk import RiskConfig
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

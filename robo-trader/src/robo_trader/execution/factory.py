"""Escolha do cliente de execucao por modo."""

from __future__ import annotations

from .base import ExecutionError
from .live import LiveExecutionClient
from .paper import PaperExecutionClient

MODES = ("paper", "testnet", "live")


def build_execution_client(mode: str, symbol: str, **kwargs):
    """Cria o cliente do modo pedido.

    * `paper`   — carteira em memoria, sem tocar na corretora;
    * `testnet` — ordens no ambiente de homologacao, com saldo ficticio;
    * `live`    — ordens reais, ainda sujeitas a `enabled=True` e
      `ROBO_TRADER_ALLOW_LIVE=1`. Pedir o modo aqui nao dispensa nenhuma das duas:
      o nome do modo costuma vir de arquivo de configuracao, e isso e fraco demais
      para ser a unica coisa entre um script e o dinheiro de verdade.
    """
    if mode not in MODES:
        raise ExecutionError(f"modo '{mode}' desconhecido; use um de {list(MODES)}")

    if mode == "paper":
        return PaperExecutionClient(symbol=symbol, **kwargs)

    kwargs.pop("testnet", None)
    return LiveExecutionClient(symbol=symbol, testnet=(mode == "testnet"), **kwargs)

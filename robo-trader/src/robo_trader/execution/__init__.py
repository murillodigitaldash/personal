"""Camada de execucao: simulada, testnet e real atras da mesma interface."""

from ..config import LIVE_ENV_FLAG, TESTNET_ENV_FLAG
from .base import Balance, ExecutionClient, ExecutionError
from .factory import MODES, build_execution_client
from .live import LiveExecutionClient
from .paper import PaperExecutionClient

__all__ = [
    "LIVE_ENV_FLAG",
    "MODES",
    "TESTNET_ENV_FLAG",
    "Balance",
    "ExecutionClient",
    "ExecutionError",
    "LiveExecutionClient",
    "PaperExecutionClient",
    "build_execution_client",
]

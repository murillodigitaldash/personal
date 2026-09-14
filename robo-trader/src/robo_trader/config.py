"""Configuracao vinda do ambiente e do arquivo .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LIVE_ENV_FLAG = "ROBO_TRADER_ALLOW_LIVE"
TESTNET_ENV_FLAG = "ROBO_TRADER_TESTNET"
API_KEY_ENV = "ROBO_TRADER_API_KEY"
API_SECRET_ENV = "ROBO_TRADER_API_SECRET"
EXCHANGE_ENV = "ROBO_TRADER_EXCHANGE"


def env_flag(name: str, default: bool = False) -> bool:
    """Le uma variavel de ambiente booleana. So '1' liga a trava."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip() == "1"


def load_env_file(path: str | Path = ".env", override: bool = False) -> dict[str, str]:
    """Carrega um arquivo .env para o ambiente e devolve o que foi lido.

    Sem dependencia externa e sem sobrescrever o que ja veio do ambiente: uma
    variavel exportada no shell vence o arquivo, que e o comportamento esperado
    de quem roda com credenciais diferentes por sessao.
    """
    file = Path(path)
    if not file.exists():
        return {}

    loaded: dict[str, str] = {}
    for line in file.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        key = key.strip()
        value = raw.strip().strip('"').strip("'")
        if not key:
            continue
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded


@dataclass(frozen=True)
class ExchangeCredentials:
    """Par de credenciais da corretora."""

    api_key: str | None = None
    api_secret: str | None = None

    @property
    def complete(self) -> bool:
        return bool(self.api_key and self.api_secret)

    @classmethod
    def from_env(cls) -> ExchangeCredentials:
        return cls(api_key=os.getenv(API_KEY_ENV), api_secret=os.getenv(API_SECRET_ENV))

    def __repr__(self) -> str:
        # Nunca imprime o segredo: log e traceback sao lugares faceis de vazar chave.
        estado = "preenchidas" if self.complete else "ausentes"
        return f"ExchangeCredentials({estado})"

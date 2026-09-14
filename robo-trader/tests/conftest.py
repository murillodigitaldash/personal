import numpy as np
import pandas as pd
import pytest


def make_candles(closes, start="2024-01-01", freq="1h", spread=0.0):
    """Candles determinísticos: abertura igual ao fechamento anterior."""
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate(([closes[0]], closes[:-1]))
    high = np.maximum(opens, closes) * (1 + spread)
    low = np.minimum(opens, closes) * (1 - spread)
    index = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=len(closes), freq=freq)
    return pd.DataFrame(
        {
            "open": opens,
            "high": high,
            "low": low,
            "close": closes,
            "volume": np.full(len(closes), 100.0),
        },
        index=pd.DatetimeIndex(index, name="timestamp"),
    )


@pytest.fixture
def make_candles_fixture():
    return make_candles


@pytest.fixture
def rising_market():
    return make_candles(100 * 1.01 ** np.arange(60))


@pytest.fixture
def flat_market():
    return make_candles(np.full(50, 100.0))


# -- dubles de corretora ---------------------------------------------------


class ExchangeFalsa:
    """Dublê de exchange: registra as chamadas em vez de acessar a rede."""

    def __init__(self):
        self.ordens = []
        self.sandbox = False

    def set_sandbox_mode(self, ligado):
        self.sandbox = ligado

    def create_order(self, symbol, tipo, lado, quantidade, preco=None):
        self.ordens.append((symbol, tipo, lado, quantidade, preco))
        return {
            "id": "1",
            "average": preco or 100.0,
            "filled": quantidade,
            "fee": {"cost": 0.1},
            "timestamp": 1704067200000,
        }

    def fetch_balance(self):
        return {"USDT": {"free": 500.0, "used": 10.0}, "BTC": {"total": 0.25}}


class ExchangeSemSandbox(ExchangeFalsa):
    """Corretora que o ccxt expõe sem ambiente de homologação."""

    set_sandbox_mode = None


MERCADO_BTC = {
    "symbol": "BTC/USDT",
    "precision": {"amount": 0.001, "price": 0.01},
    "limits": {"amount": {"min": 0.001}, "cost": {"min": 10.0}},
}


class ExchangeComMercado(ExchangeFalsa):
    """Dublê que publica as regras do par, como a corretora de verdade faz."""

    def __init__(self, mercado=None):
        super().__init__()
        self.mercado = MERCADO_BTC if mercado is None else mercado
        self.carregamentos = 0

    def load_markets(self, reload=False):
        self.carregamentos += 1
        return {"BTC/USDT": self.mercado}


class ExchangeComPermissoes(ExchangeComMercado):
    """Dublê que publica as permissões da chave, como a Binance faz."""

    def __init__(self, mercado=None, **flags):
        super().__init__(mercado)
        self.flags = {
            "enableReading": True,
            "enableSpotAndMarginTrading": True,
            "enableWithdrawals": False,
            "ipRestrict": False,
        }
        self.flags.update(flags)

    def sapiGetAccountApiRestrictions(self):
        return dict(self.flags)

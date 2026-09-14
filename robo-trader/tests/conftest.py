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

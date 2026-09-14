import pandas as pd
import pytest

from robo_trader.data import (
    CsvMarketData,
    DataValidationError,
    find_gaps,
    generate_ohlcv,
    infer_periods_per_year,
    normalize_ohlcv,
    write_ohlcv,
)


def test_normaliza_epoch_em_milissegundos():
    raw = pd.DataFrame(
        {
            "timestamp": [1704067200000, 1704070800000],
            "open": [1.0, 2.0],
            "high": [2.0, 3.0],
            "low": [0.5, 1.5],
            "close": [1.5, 2.5],
            "volume": [10.0, 20.0],
        }
    )
    df = normalize_ohlcv(raw)
    assert str(df.index.tz) == "UTC"
    assert df.index[0] == pd.Timestamp("2024-01-01 00:00:00", tz="UTC")
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_remove_duplicatas_e_ordena():
    raw = pd.DataFrame(
        {
            "timestamp": ["2024-01-02", "2024-01-01", "2024-01-02"],
            "open": [2.0, 1.0, 9.0],
            "high": [2.0, 1.0, 9.0],
            "low": [2.0, 1.0, 9.0],
            "close": [2.0, 1.0, 9.0],
            "volume": [1.0, 1.0, 1.0],
        }
    )
    df = normalize_ohlcv(raw)
    assert len(df) == 2
    assert df.index.is_monotonic_increasing
    assert df["close"].iloc[-1] == 9.0  # mantem a ultima ocorrencia


def test_rejeita_colunas_ausentes():
    raw = pd.DataFrame({"timestamp": ["2024-01-01"], "open": [1.0], "close": [1.0]})
    with pytest.raises(DataValidationError, match="colunas ausentes"):
        normalize_ohlcv(raw)


def test_rejeita_candle_inconsistente():
    raw = pd.DataFrame(
        {
            "timestamp": ["2024-01-01"],
            "open": [10.0],
            "high": [5.0],  # maxima abaixo da abertura
            "low": [4.0],
            "close": [9.0],
            "volume": [1.0],
        }
    )
    with pytest.raises(DataValidationError, match="inconsistente"):
        normalize_ohlcv(raw)


def test_rejeita_serie_vazia():
    with pytest.raises(DataValidationError):
        normalize_ohlcv(pd.DataFrame())


def test_encontra_buracos_na_serie():
    df = generate_ohlcv(periods=10, timeframe="1h")
    com_buraco = df.drop(df.index[3])
    gaps = find_gaps(com_buraco, "1h")
    assert list(gaps) == [df.index[3]]


def test_periodos_por_ano_de_serie_horaria():
    df = generate_ohlcv(periods=100, timeframe="1h")
    assert infer_periods_per_year(df.index) == pytest.approx(8760, rel=1e-6)


def test_csv_round_trip(tmp_path):
    df = generate_ohlcv(periods=50, timeframe="1h")
    write_ohlcv(df, tmp_path / "BTCUSDT_1h.csv")

    source = CsvMarketData(tmp_path)
    lido = source.fetch_ohlcv("BTC/USDT", "1h")
    pd.testing.assert_frame_equal(lido, df, check_freq=False)


def test_csv_respeita_janela_e_limite(tmp_path):
    df = generate_ohlcv(periods=100, timeframe="1h")
    write_ohlcv(df, tmp_path / "BTCUSDT_1h.csv")
    source = CsvMarketData(tmp_path)

    recorte = source.fetch_ohlcv("BTC/USDT", "1h", since=df.index[10], until=df.index[20])
    assert len(recorte) == 11

    ultimos = source.fetch_ohlcv("BTC/USDT", "1h", limit=5)
    assert len(ultimos) == 5
    assert ultimos.index[-1] == df.index[-1]


def test_csv_sem_arquivo_correspondente(tmp_path):
    with pytest.raises(FileNotFoundError):
        CsvMarketData(tmp_path).fetch_ohlcv("ETH/USDT", "1h")


def test_candles_sinteticos_sao_validos_e_reprodutiveis():
    a = generate_ohlcv(periods=200, seed=7)
    b = generate_ohlcv(periods=200, seed=7)
    pd.testing.assert_frame_equal(a, b)
    normalize_ohlcv(a)  # nao levanta

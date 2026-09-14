import json

import pytest

from robo_trader.cli import _parse_params, main
from robo_trader.data import generate_ohlcv, write_ohlcv


def test_parse_params_converte_tipos():
    params = _parse_params(["fast=5", "ratio=0.5", "allow_short=true", "mode=agressivo"])
    assert params == {"fast": 5, "ratio": 0.5, "allow_short": True, "mode": "agressivo"}
    assert isinstance(params["fast"], int)


def test_parse_params_rejeita_formato_invalido():
    with pytest.raises(Exception, match="chave=valor"):
        _parse_params(["fast"])


def test_comando_strategies_lista_as_disponiveis(capsys):
    assert main(["strategies"]) == 0
    saida = capsys.readouterr().out
    assert "ema_crossover" in saida
    assert "donchian_breakout" in saida


def test_backtest_sintetico_imprime_resumo(capsys):
    codigo = main(["backtest", "--synthetic", "--synthetic-periods", "300", "--strategy", "ema_crossover"])
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "Retorno total" in saida
    assert "Drawdown maximo" in saida


def test_backtest_em_json(capsys):
    main(["backtest", "--synthetic", "--synthetic-periods", "300", "--json"])
    metrics = json.loads(capsys.readouterr().out)

    assert "sharpe" in metrics
    assert "max_drawdown" in metrics
    assert metrics["initial_equity"] == 10_000.0


def test_backtest_aceita_parametros_da_estrategia(capsys):
    main([
        "backtest", "--synthetic", "--synthetic-periods", "400",
        "--strategy", "ema_crossover", "--param", "fast=5", "--param", "slow=15", "--json",
    ])
    assert json.loads(capsys.readouterr().out)["bars"] == 400


def test_backtest_a_partir_de_csv(tmp_path, capsys):
    arquivo = tmp_path / "BTCUSDT_1h.csv"
    write_ohlcv(generate_ohlcv(periods=400, timeframe="1h"), arquivo)

    codigo = main(["backtest", "--csv", str(arquivo), "--symbol", "BTC/USDT", "--json"])
    assert codigo == 0
    assert json.loads(capsys.readouterr().out)["bars"] == 400


def test_backtest_sem_fonte_de_dados():
    with pytest.raises(SystemExit, match="--csv"):
        main(["backtest", "--strategy", "ema_crossover"])


def test_backtest_grava_relatorios(tmp_path, capsys):
    destino = tmp_path / "relatorio"
    main([
        "backtest", "--synthetic", "--synthetic-periods", "300",
        "--report", str(destino),
    ])

    assert (destino / "equity.csv").exists()
    assert (destino / "trades.csv").exists()
    assert (destino / "metrics.csv").exists()
    assert "Relatorios gravados" in capsys.readouterr().out


def test_backtest_com_travas_de_risco(capsys):
    codigo = main([
        "backtest", "--synthetic", "--synthetic-periods", "500",
        "--max-weight", "0.5", "--stop-loss", "0.03", "--max-drawdown", "0.15", "--json",
    ])
    assert codigo == 0
    assert json.loads(capsys.readouterr().out)["max_drawdown"] >= -0.5


def test_preflight_no_modo_paper_imprime_o_relatorio(capsys):
    codigo = main(["preflight", "--mode", "paper", "--symbol", "BTC/USDT"])
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "PRONTO" in saida
    assert "paper" in saida


def test_preflight_reprova_e_devolve_codigo_de_erro(capsys):
    # Notional maior que a carteira simulada: reprova sem tocar em corretora.
    codigo = main(["preflight", "--mode", "paper", "--notional", "999999"])
    saida = capsys.readouterr().out

    assert codigo == 1
    assert "NAO PRONTO" in saida


def test_preflight_avisa_que_nao_enviou_ordem(capsys):
    main(["preflight", "--mode", "paper"])
    assert "Nenhuma ordem foi enviada" in capsys.readouterr().out


def test_preflight_recusa_modo_desconhecido():
    with pytest.raises(SystemExit):
        main(["preflight", "--mode", "producao"])

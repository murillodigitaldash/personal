"""Conferencia pre-ordem: tudo que precisa estar certo antes da primeira ordem."""

import pytest
from conftest import ExchangeComMercado, ExchangeComPermissoes, ExchangeFalsa

from robo_trader.execution import (
    LIVE_ENV_FLAG,
    LiveExecutionClient,
    PaperExecutionClient,
    preflight,
)


def cliente_testnet(exchange=None, **kwargs):
    base = dict(symbol="BTC/USDT", api_key="k", api_secret="s", testnet=True)
    base.update(kwargs)
    return LiveExecutionClient(exchange=exchange or ExchangeComMercado(), **base)


def checagem(report, nome):
    return next(c for c in report.checks if c.name == nome)


def test_preflight_do_paper_passa_sem_tocar_na_corretora():
    report = preflight(PaperExecutionClient(symbol="BTC/USDT"))

    assert report.ok
    assert report.mode == "paper"
    assert checagem(report, "saldo").ok


def test_preflight_da_testnet_reporta_as_regras_do_par():
    report = preflight(cliente_testnet())

    assert report.ok
    assert report.mode == "testnet"
    assert "0.001" in checagem(report, "regras do par").detail


def test_preflight_nao_envia_nenhuma_ordem():
    exchange = ExchangeComMercado()
    preflight(cliente_testnet(exchange))

    assert exchange.ordens == []


def test_preflight_reprova_sem_credenciais(monkeypatch):
    monkeypatch.delenv("ROBO_TRADER_API_KEY", raising=False)
    monkeypatch.delenv("ROBO_TRADER_API_SECRET", raising=False)
    cliente = cliente_testnet(api_key=None, api_secret=None)

    report = preflight(cliente)

    # Relatorio, nao excecao: o valor do preflight e listar tudo que falta de uma vez.
    assert not report.ok
    assert not checagem(report, "credenciais").ok


def test_preflight_do_modo_real_reprova_sem_a_variavel(monkeypatch):
    monkeypatch.delenv(LIVE_ENV_FLAG, raising=False)
    cliente = LiveExecutionClient(
        symbol="BTC/USDT", exchange=ExchangeComMercado(), enabled=True,
        api_key="k", api_secret="s",
    )

    report = preflight(cliente)

    assert not report.ok
    assert LIVE_ENV_FLAG in checagem(report, "modo").detail


def test_preflight_confere_o_notional_pretendido():
    reprovado = preflight(cliente_testnet(), notional=5.0)
    aprovado = preflight(cliente_testnet(), notional=50.0)

    assert not reprovado.ok
    assert not checagem(reprovado, "notional").ok
    assert aprovado.ok


def test_preflight_reporta_falha_de_conexao():
    class ExchangeForaDoAr(ExchangeFalsa):
        def load_markets(self, reload=False):
            raise ConnectionError("nome nao resolvido")

        def fetch_balance(self):
            raise ConnectionError("nome nao resolvido")

    report = preflight(cliente_testnet(ExchangeForaDoAr()))

    assert not report.ok
    assert "nome nao resolvido" in checagem(report, "conexao").detail


def test_summary_marca_o_que_falhou():
    texto = preflight(cliente_testnet(), notional=5.0).summary()

    assert "notional" in texto
    assert "testnet" in texto


def test_notional_nao_afirma_saldo_que_nao_conseguiu_ler():
    class SemSaldo(ExchangeComMercado):
        def fetch_balance(self):
            raise ConnectionError("sem resposta")

    report = preflight(cliente_testnet(SemSaldo()), notional=20.0)

    # Dizer "cabe no saldo" sem ter lido o saldo e' a mentira mais cara do relatorio.
    assert "saldo nao verificado" in checagem(report, "notional").detail


def test_regras_do_par_saem_sem_notacao_cientifica():
    mercado = {
        "symbol": "BTC/USDT",
        "precision": {"amount": 0.00001, "price": 0.01},
        "limits": {"amount": {"min": 0.00001}, "cost": {"min": 5.0}},
    }
    report = preflight(cliente_testnet(ExchangeComMercado(mercado)))
    detalhe = checagem(report, "regras do par").detail

    assert "0.00001" in detalhe
    assert "e-05" not in detalhe


# -- permissoes da chave ---------------------------------------------------


def test_preflight_reprova_chave_sem_permissao_de_negociar():
    exchange = ExchangeComPermissoes(enableSpotAndMarginTrading=False)

    report = preflight(cliente_testnet(exchange))

    # Chave so de leitura nao manda ordem nenhuma: a corretora recusa antes das
    # nossas travas, e descobrir isso na primeira ordem e' caro.
    assert not report.ok
    assert not checagem(report, "permissoes").ok
    assert "negociar" in checagem(report, "permissoes").detail


def test_preflight_reprova_chave_com_saque_habilitado():
    exchange = ExchangeComPermissoes(enableWithdrawals=True)

    report = preflight(cliente_testnet(exchange))

    assert not checagem(report, "permissoes").ok
    assert "saque" in checagem(report, "permissoes").detail


def test_preflight_aprova_chave_que_negocia_e_nao_saca():
    report = preflight(cliente_testnet(ExchangeComPermissoes()))

    assert report.ok
    assert checagem(report, "permissoes").ok


def test_preflight_omite_permissoes_quando_a_corretora_nao_expoe():
    report = preflight(cliente_testnet(ExchangeComMercado()))

    # Sem a consulta, nao inventa um 'ok' sobre permissao que nao foi lida.
    assert all(check.name != "permissoes" for check in report.checks)


def test_falha_ao_ler_permissoes_nao_vira_reprovacao():
    class SemResposta(ExchangeComPermissoes):
        def sapiGetAccountApiRestrictions(self):
            raise ConnectionError("endpoint indisponivel")

    report = preflight(cliente_testnet(SemResposta()))

    assert report.ok
    assert "nao verificad" in checagem(report, "permissoes").detail

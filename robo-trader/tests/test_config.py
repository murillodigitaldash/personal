import os

import pytest

from robo_trader.config import (
    API_KEY_ENV,
    API_SECRET_ENV,
    ExchangeCredentials,
    env_flag,
    load_env_file,
)


def test_env_flag_so_liga_com_um(monkeypatch):
    monkeypatch.setenv("FLAG_TESTE", "1")
    assert env_flag("FLAG_TESTE") is True

    for valor in ("0", "true", "sim", "yes", ""):
        monkeypatch.setenv("FLAG_TESTE", valor)
        assert env_flag("FLAG_TESTE") is False


def test_env_flag_usa_o_padrao_quando_ausente(monkeypatch):
    monkeypatch.delenv("FLAG_TESTE", raising=False)
    assert env_flag("FLAG_TESTE") is False
    assert env_flag("FLAG_TESTE", default=True) is True


def test_load_env_file_ignora_comentarios_e_aspas(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "\n".join(
            [
                "# comentario",
                "",
                'ROBO_TRADER_API_KEY="chave"',
                "ROBO_TRADER_API_SECRET='segredo'",
                "ROBO_TRADER_ALLOW_LIVE=0",
                "linha sem igual",
            ]
        )
    )
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.delenv(API_SECRET_ENV, raising=False)

    lidas = load_env_file(arquivo)

    assert lidas[API_KEY_ENV] == "chave"
    assert lidas[API_SECRET_ENV] == "segredo"
    assert "linha sem igual" not in lidas
    assert os.environ[API_KEY_ENV] == "chave"


def test_load_env_file_nao_sobrescreve_o_ambiente(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text(f"{API_KEY_ENV}=do-arquivo")
    monkeypatch.setenv(API_KEY_ENV, "do-shell")

    load_env_file(arquivo)
    assert os.environ[API_KEY_ENV] == "do-shell"

    load_env_file(arquivo, override=True)
    assert os.environ[API_KEY_ENV] == "do-arquivo"


def test_load_env_file_ausente_nao_falha(tmp_path):
    assert load_env_file(tmp_path / "nao-existe") == {}


def test_credenciais_incompletas():
    assert not ExchangeCredentials().complete
    assert not ExchangeCredentials(api_key="k").complete
    assert ExchangeCredentials(api_key="k", api_secret="s").complete


def test_credenciais_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "k")
    monkeypatch.setenv(API_SECRET_ENV, "s")
    assert ExchangeCredentials.from_env().complete


def test_repr_das_credenciais_nao_vaza_o_segredo():
    texto = repr(ExchangeCredentials(api_key="chave-publica", api_secret="segredo-sensivel"))
    assert "segredo-sensivel" not in texto
    assert "chave-publica" not in texto
    assert "preenchidas" in texto

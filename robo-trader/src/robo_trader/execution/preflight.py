"""Conferencia pre-ordem: o que precisa estar certo antes da primeira ordem.

A homologacao em testnet falha quase sempre pelas mesmas coisas — credencial do
ambiente errado, sandbox que nao ligou, par fora da lista, ordem abaixo do
notional minimo. Descobrir uma de cada vez, a cada ordem recusada, e caro. O
preflight junta tudo em um relatorio e **nao envia nenhuma ordem**.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import API_KEY_ENV, API_SECRET_ENV, LIVE_ENV_FLAG

__all__ = ["Check", "PreflightReport", "preflight"]


@dataclass(frozen=True)
class Check:
    """Uma conferencia e o que ela achou."""

    name: str
    ok: bool
    detail: str

    def __str__(self) -> str:
        return f"[{'ok' if self.ok else 'FALHA'}] {self.name}: {self.detail}"


@dataclass(frozen=True)
class PreflightReport:
    """Resultado da conferencia. Reprovar aqui e' de graca; na corretora, nao."""

    mode: str
    symbol: str
    checks: tuple[Check, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def summary(self) -> str:
        titulo = f"Preflight {self.mode} em {self.symbol}"
        linhas = [titulo, "-" * len(titulo)]
        linhas.extend(str(check) for check in self.checks)
        linhas.append("")
        linhas.append(
            f"{'PRONTO' if self.ok else 'NAO PRONTO'} para enviar ordem em {self.mode}"
        )
        return "\n".join(linhas)


def _check_modo(client, mode: str) -> Check:
    if mode == "testnet":
        return Check(
            "modo", True, "homologacao: saldo ficticio, ordem nao vale dinheiro real"
        )

    faltando = []
    if not getattr(client, "enabled", False):
        faltando.append("enabled=True no cliente")
    if not client.env_allows_live():
        faltando.append(f"{LIVE_ENV_FLAG}=1 no ambiente")
    if faltando:
        return Check("modo", False, "modo real bloqueado, falta " + " e ".join(faltando))
    return Check("modo", True, "modo real liberado: as ordens valem dinheiro de verdade")


def preflight(client, notional: float | None = None) -> PreflightReport:
    """Confere o caminho da ordem sem enviar nenhuma.

    `notional` e' o tamanho em moeda de cotacao que se pretende negociar: quando
    informado, o relatorio diz se ele passa do minimo do par e se cabe no saldo.
    """
    mode = getattr(client, "mode", "?")
    symbol = getattr(client, "symbol", "?")
    checks: list[Check] = []
    rules = None
    saldo = None

    if mode == "paper":
        checks.append(Check("modo", True, "carteira simulada: nada sai da maquina"))
    else:
        checks.append(_check_modo(client, mode))

        credenciais = client.credentials
        checks.append(
            Check(
                "credenciais",
                credenciais.complete,
                "API key e secret presentes"
                if credenciais.complete
                else f"faltando {API_KEY_ENV}/{API_SECRET_ENV} no .env ou no ambiente",
            )
        )

        try:
            rules = client.market_rules
        except Exception as exc:
            checks.append(Check("conexao", False, f"corretora nao respondeu: {exc}"))
        else:
            ambiente = "testnet" if mode == "testnet" else "producao"
            checks.append(
                Check("conexao", True, f"{client.exchange_id} respondeu em {ambiente}")
            )
            checks.append(
                Check("regras do par", True, _descreve(rules))
                if rules is not None
                else Check(
                    "regras do par",
                    False,
                    f"{symbol} nao esta na lista de mercados da corretora",
                )
            )

        try:
            permissoes = client.permissions()
        except Exception as exc:
            checks.append(
                Check("permissoes", True, f"nao verificadas: corretora nao respondeu ({exc})")
            )
        else:
            if permissoes is not None:
                checks.append(_check_permissoes(permissoes))

    try:
        saldo = client.balance()
    except Exception as exc:
        checks.append(Check("saldo", False, f"nao foi possivel ler o saldo: {exc}"))
    else:
        tem_saldo = saldo.free > 0
        checks.append(
            Check(
                "saldo",
                tem_saldo,
                f"{saldo.free:.2f} {saldo.currency} livres"
                if tem_saldo
                else f"sem {saldo.currency} livre para operar",
            )
        )

    if notional is not None:
        checks.append(_check_notional(notional, rules, saldo))

    return PreflightReport(mode=mode, symbol=symbol, checks=tuple(checks))


def _numero(value) -> str:
    """Numero legivel: passo de 0.00001 nao pode sair como 1e-05 num relatorio."""
    if value is None:
        return "sem limite"
    return f"{value:.10f}".rstrip("0").rstrip(".") or "0"


def _descreve(rules) -> str:
    return (
        f"passo {_numero(rules.amount_step)}, minimo {_numero(rules.min_amount)}, "
        f"notional minimo {_numero(rules.min_notional)}"
    )


def _check_notional(notional: float, rules, saldo) -> Check:
    minimo = getattr(rules, "min_notional", None)
    if minimo is not None and notional < minimo:
        return Check(
            "notional",
            False,
            f"ordem de {notional:.2f} abaixo do minimo {_numero(minimo)} do par",
        )
    if saldo is None:
        # Sem saldo lido nao da para prometer que a ordem cabe: dizer que cabe seria
        # exatamente o tipo de conforto falso que o preflight existe para evitar.
        return Check("notional", True, f"ordem de {notional:.2f} cabe no par (saldo nao verificado)")
    if notional > saldo.free:
        return Check(
            "notional",
            False,
            f"ordem de {notional:.2f} acima do saldo livre de {saldo.free:.2f}",
        )
    return Check("notional", True, f"ordem de {notional:.2f} cabe no par e no saldo")


def _check_permissoes(permissoes: dict) -> Check:
    """Le as permissoes da chave antes que a corretora recuse a ordem por elas."""
    if permissoes.get("can_trade") is False:
        return Check(
            "permissoes",
            False,
            "a chave nao pode negociar: habilite spot trading na corretora ou gere outra",
        )
    if permissoes.get("withdrawals") is True:
        return Check(
            "permissoes",
            False,
            "a chave permite saque: desligue na corretora antes de usar em robo",
        )
    detalhe = "negociacao liberada, saque desligado"
    if permissoes.get("ip_restricted") is False:
        detalhe += "; sem allowlist de IP"
    return Check("permissoes", True, detalhe)

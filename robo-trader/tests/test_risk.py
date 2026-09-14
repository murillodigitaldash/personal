import pandas as pd
import pytest

from robo_trader.risk import RiskConfig, RiskManager

D1 = pd.Timestamp("2024-01-01 10:00", tz="UTC")
D1_TARDE = pd.Timestamp("2024-01-01 20:00", tz="UTC")
D2 = pd.Timestamp("2024-01-02 10:00", tz="UTC")


def test_limita_o_peso_ao_teto_configurado():
    gestor = RiskManager(RiskConfig(max_position_weight=0.3))
    assert gestor.allowed_weight(1.0) == pytest.approx(0.3)
    assert gestor.allowed_weight(-1.0) == pytest.approx(-0.3)
    assert gestor.allowed_weight(0.1) == pytest.approx(0.1)


def test_perda_diaria_bloqueia_ate_o_fim_do_dia():
    gestor = RiskManager(RiskConfig(max_daily_loss=0.05))
    gestor.update(D1, 10_000.0)
    assert gestor.allowed_weight(1.0) == 1.0

    gestor.update(D1_TARDE, 9_400.0)  # -6% no dia
    assert gestor.allowed_weight(1.0) == 0.0
    assert "perda diaria" in gestor.blocked_reason
    assert not gestor.halted  # bloqueio temporario, nao desligamento


def test_bloqueio_diario_expira_no_dia_seguinte():
    gestor = RiskManager(RiskConfig(max_daily_loss=0.05))
    gestor.update(D1, 10_000.0)
    gestor.update(D1_TARDE, 9_000.0)
    assert gestor.allowed_weight(1.0) == 0.0

    gestor.update(D2, 9_000.0)
    assert gestor.allowed_weight(1.0) == 1.0


def test_drawdown_desliga_o_robo_de_vez():
    gestor = RiskManager(RiskConfig(max_drawdown=0.20))
    gestor.update(D1, 10_000.0)
    gestor.update(D1_TARDE, 7_500.0)  # -25% do pico

    assert gestor.halted
    assert gestor.allowed_weight(1.0) == 0.0

    gestor.update(D2, 12_000.0)  # nem a recuperacao religa
    assert gestor.halted
    assert gestor.allowed_weight(1.0) == 0.0


def test_pico_acompanha_o_maior_patrimonio():
    gestor = RiskManager(RiskConfig(max_drawdown=0.20))
    gestor.update(D1, 10_000.0)
    gestor.update(D1_TARDE, 20_000.0)
    gestor.update(D2, 17_000.0)  # -15% do novo pico
    assert not gestor.halted


def test_niveis_de_saida_para_compra_e_venda():
    gestor = RiskManager(RiskConfig(stop_loss_pct=0.05, take_profit_pct=0.10))

    stop, alvo = gestor.exit_levels(100.0, is_long=True)
    assert (stop, alvo) == (pytest.approx(95.0), pytest.approx(110.0))

    stop, alvo = gestor.exit_levels(100.0, is_long=False)
    assert (stop, alvo) == (pytest.approx(105.0), pytest.approx(90.0))


def test_sem_configuracao_nao_ha_niveis_de_saida():
    stop, alvo = RiskManager().exit_levels(100.0, is_long=True)
    assert stop is None and alvo is None


def test_reset_limpa_o_estado():
    gestor = RiskManager(RiskConfig(max_drawdown=0.10))
    gestor.update(D1, 10_000.0)
    gestor.update(D1_TARDE, 5_000.0)
    assert gestor.halted

    gestor.reset()
    assert not gestor.halted
    assert gestor.blocked_reason is None
    assert gestor.allowed_weight(1.0) == 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_position_weight": 0.0},
        {"max_position_weight": 1.5},
        {"stop_loss_pct": 1.0},
        {"max_drawdown": -0.1},
        {"min_trade_notional": -1.0},
        {"rebalance_threshold": 1.0},
    ],
)
def test_configuracao_invalida_e_recusada(kwargs):
    with pytest.raises(ValueError):
        RiskConfig(**kwargs)

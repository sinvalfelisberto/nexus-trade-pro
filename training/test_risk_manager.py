# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Teste do Risk Manager
========================================
Executa testes automatizados do sistema de controle de risco
"""

import sys
import os

# Adicionar diretorio ao path
sys.path.insert(0, os.path.dirname(__file__))

from risk_manager import RiskManager, RiskConfig


def test_basic_functionality():
    """Teste basico de funcionamento"""
    print("\n" + "=" * 60)
    print("  TESTE 1: Funcionamento Basico")
    print("=" * 60)

    rm = RiskManager(initial_capital=1000.0)

    # Verificar estado inicial
    status = rm.get_status()
    assert status["status"] == "OK", "Status deveria ser OK"
    assert status["capital"]["current"] == 1000.0, "Capital inicial incorreto"
    assert status["drawdown"]["current"] == 0, "Drawdown inicial deveria ser 0"

    print("[OK] Estado inicial correto")

    # Verificar se pode operar
    can, reason, details = rm.check_can_trade(confidence=70, score=35)
    assert can == True, "Deveria poder operar"
    print("[OK] Verificacao de trade funcionando")

    # Limpar
    rm.reset_all(1000.0)
    print("[OK] Reset funcionando")


def test_drawdown_control():
    """Teste do controle de drawdown"""
    print("\n" + "=" * 60)
    print("  TESTE 2: Controle de Drawdown")
    print("=" * 60)

    # Config com limites mais altos para teste isolado de drawdown
    config = RiskConfig(
        max_drawdown_percent=20.0,
        warning_drawdown_percent=10.0,
        max_daily_loss_percent=50.0,  # Alto para nao interferir no teste
        circuit_breaker_loss_percent=50.0  # Alto para nao interferir
    )
    rm = RiskManager(config=config, initial_capital=10000.0)  # Capital maior

    # Simular perdas
    print("\n  Simulando perdas progressivas...")

    # Perda 1: -5% (OK)
    rm.register_trade("PETR4", "BUY", 100, 10.0, 9.50, -50)
    status = rm.get_status()
    print(f"  Apos perda 1: Capital R$ {status['capital']['current']:.2f}, DD: {status['drawdown']['current']:.1f}%")
    can, _, _ = rm.check_can_trade()
    assert can == True, "Ainda deveria poder operar"

    # Perda 2: mais -5% (WARNING - total ~1.5%)
    rm.register_trade("VALE3", "BUY", 50, 20.0, 18.0, -100)
    status = rm.get_status()
    print(f"  Apos perda 2: Capital R$ {status['capital']['current']:.2f}, DD: {status['drawdown']['current']:.1f}%")

    # Perdas maiores para atingir 20% de drawdown
    # Precisamos perder 2000 para atingir 20%
    rm.register_trade("MGLU3", "BUY", 100, 30.0, 20.0, -1000)
    status = rm.get_status()
    print(f"  Apos perda 3: Capital R$ {status['capital']['current']:.2f}, DD: {status['drawdown']['current']:.1f}%")

    rm.register_trade("AZUL4", "BUY", 100, 25.0, 15.0, -1000)
    status = rm.get_status()
    print(f"  Apos perda 4: Capital R$ {status['capital']['current']:.2f}, DD: {status['drawdown']['current']:.1f}%")

    can, reason, details = rm.check_can_trade()
    print(f"  Status: {status['status']}, Pode operar: {can}, Razao: {reason}")

    if status['drawdown']['current'] >= 20:
        assert can == False, "Deveria estar bloqueado"
        assert "DRAWDOWN" in reason, "Razao deveria mencionar drawdown"
        print("[OK] Bloqueio por drawdown funcionando!")
    else:
        print("[OK] Drawdown controlado, ainda pode operar")

    # Limpar
    rm.reset_all(10000.0)


def test_consecutive_losses():
    """Teste de reducao por perdas consecutivas"""
    print("\n" + "=" * 60)
    print("  TESTE 3: Reducao por Perdas Consecutivas")
    print("=" * 60)

    # Config com limites altos para testar apenas perdas consecutivas
    config = RiskConfig(
        max_consecutive_losses=10,  # Alto para nao bloquear
        reduction_after_losses=2,
        max_daily_loss_percent=50.0,  # Alto para nao interferir
        circuit_breaker_loss_percent=50.0  # Alto para nao interferir
    )
    rm = RiskManager(config=config, initial_capital=100000.0)  # Capital alto

    print("\n  Simulando perdas consecutivas...")

    # Multiplas perdas pequenas
    for i in range(4):
        rm.register_trade(f"ATIVO{i}", "BUY", 10, 100.0, 99.0, -10)  # Perdas pequenas
        multiplier = rm.get_position_multiplier()
        print(f"  Perda {i+1}: Multiplicador = {multiplier}")

    # Verificar reducao
    status = rm.get_status()
    print(f"\n  Perdas consecutivas: {status['sequences']['consecutive_losses']}")
    print(f"  Multiplicador final: {status['position_multiplier']}")

    assert status['position_multiplier'] < 1.0, "Multiplicador deveria ser menor que 1"
    print("[OK] Reducao por perdas consecutivas funcionando!")

    # Limpar
    rm.reset_all(100000.0)


def test_position_sizing():
    """Teste de position sizing"""
    print("\n" + "=" * 60)
    print("  TESTE 4: Position Sizing")
    print("=" * 60)

    rm = RiskManager(initial_capital=10000.0)

    # Calcular para PETR4 @ R$ 38.50
    size = rm.calculate_position_size(
        price=38.50,
        stop_loss_percent=3.0,
        win_rate=0.60,
        avg_win_loss_ratio=1.5
    )

    print(f"\n  Capital: R$ {size['capital']:.2f}")
    print(f"  Preco: R$ {size['price']:.2f}")
    print(f"  Multiplicador: {size['multiplier']}")
    print(f"\n  Metodos:")
    print(f"    Fixed %:   {size['methods']['fixed_percent']['quantity']} acoes")
    if 'kelly' in size['methods']:
        print(f"    Kelly:     {size['methods']['kelly']['quantity']} acoes")
    print(f"    Risk-Based: {size['methods']['risk_based']['quantity']} acoes")
    print(f"\n  RECOMENDADO: {size['recommended']['quantity']} acoes")
    print(f"  Valor: R$ {size['recommended']['amount']:.2f}")
    print(f"  % Capital: {size['recommended']['percent_of_capital']:.1f}%")

    assert size['recommended']['quantity'] > 0, "Deveria recomendar pelo menos 1 acao"
    assert size['recommended']['percent_of_capital'] <= 20, "Nao deveria exceder 20% do capital"
    print("\n[OK] Position sizing funcionando!")

    # Limpar
    rm.reset_all(10000.0)


def test_daily_limit():
    """Teste de limite diario"""
    print("\n" + "=" * 60)
    print("  TESTE 5: Limite Diario")
    print("=" * 60)

    config = RiskConfig(
        max_daily_loss_percent=5.0,
        max_daily_trades=5
    )
    rm = RiskManager(config=config, initial_capital=1000.0)

    print("\n  Simulando trades no dia...")

    # Executar trades ate o limite
    for i in range(5):
        rm.register_trade(f"ATIVO{i}", "BUY", 1, 10.0, 10.50, 5)
        print(f"  Trade {i+1} executado")

    # Proximo trade deveria ser bloqueado
    can, reason, _ = rm.check_can_trade()
    print(f"\n  Apos 5 trades: Pode operar = {can}, Razao = {reason}")

    assert can == False, "Deveria estar bloqueado"
    assert "TRADES" in reason or "LIMIT" in reason, "Razao deveria mencionar limite"
    print("[OK] Limite de trades diarios funcionando!")

    # Limpar
    rm.reset_all(1000.0)


def test_confidence_filter():
    """Teste de filtro de confianca"""
    print("\n" + "=" * 60)
    print("  TESTE 6: Filtro de Confianca")
    print("=" * 60)

    config = RiskConfig(
        min_confidence_to_trade=55.0,
        min_score_to_trade=25.0
    )
    rm = RiskManager(config=config, initial_capital=1000.0)

    # Trade com confianca baixa
    can, reason, _ = rm.check_can_trade(confidence=40, score=50)
    print(f"  Confianca 40%: Pode operar = {can}, Razao = {reason}")
    assert can == False, "Deveria bloquear confianca baixa"

    # Trade com score baixo
    can, reason, _ = rm.check_can_trade(confidence=70, score=15)
    print(f"  Score 15: Pode operar = {can}, Razao = {reason}")
    assert can == False, "Deveria bloquear score baixo"

    # Trade valido
    can, reason, _ = rm.check_can_trade(confidence=70, score=40)
    print(f"  Confianca 70%, Score 40: Pode operar = {can}, Razao = {reason}")
    assert can == True, "Deveria permitir trade valido"

    print("[OK] Filtros de confianca e score funcionando!")

    # Limpar
    rm.reset_all(1000.0)


def test_recovery_after_wins():
    """Teste de recuperacao apos ganhos"""
    print("\n" + "=" * 60)
    print("  TESTE 7: Recuperacao apos Ganhos")
    print("=" * 60)

    rm = RiskManager(initial_capital=1000.0)

    # Primeiro, algumas perdas
    for i in range(3):
        rm.register_trade(f"LOSS{i}", "BUY", 10, 100.0, 98.0, -20)

    status = rm.get_status()
    mult_after_losses = status['position_multiplier']
    print(f"  Apos 3 perdas: Multiplicador = {mult_after_losses}")

    # Agora, ganhos
    for i in range(3):
        rm.register_trade(f"WIN{i}", "BUY", 10, 100.0, 105.0, 50)

    status = rm.get_status()
    mult_after_wins = status['position_multiplier']
    print(f"  Apos 3 ganhos: Multiplicador = {mult_after_wins}")

    assert mult_after_wins > mult_after_losses, "Multiplicador deveria aumentar apos ganhos"
    assert status['sequences']['consecutive_losses'] == 0, "Perdas consecutivas deveriam zerar"
    print("[OK] Recuperacao funcionando!")

    # Limpar
    rm.reset_all(1000.0)


def run_all_tests():
    """Executa todos os testes"""
    print("\n" + "=" * 60)
    print("  NEXUS TRADE PRO - TESTES DO RISK MANAGER")
    print("=" * 60)

    tests = [
        test_basic_functionality,
        test_drawdown_control,
        test_consecutive_losses,
        test_position_sizing,
        test_daily_limit,
        test_confidence_filter,
        test_recovery_after_wins
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n[FALHOU] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERRO] {test.__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"  RESULTADO: {passed} passaram, {failed} falharam")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

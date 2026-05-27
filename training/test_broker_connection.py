# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Teste de Conexao com Corretora
Execute este script para verificar se a integracao esta funcionando.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("  NEXUS TRADE PRO - Teste de Conexao")
print("=" * 60)

# Verificar configuracoes
TRADING_MODE = os.getenv("TRADING_MODE", "PAPER")
BROKER_NAME = os.getenv("BROKER_NAME", "MT5")

print(f"\n[CONFIG] Modo: {TRADING_MODE}")
print(f"[CONFIG] Corretora: {BROKER_NAME}")

if TRADING_MODE == "PAPER":
    print("\n[INFO] Modo PAPER (simulacao) ativo.")
    print("[INFO] Para operar com dinheiro real, altere TRADING_MODE=REAL no .env")

# Testar importacao
print("\n[TESTE] Importando modulo de integracao...")
try:
    from broker_integration import connect, disconnect, get_balance, get_positions, buy, sell
    print("[OK] Modulo importado com sucesso!")
except ImportError as e:
    print(f"[ERRO] Falha ao importar: {e}")
    sys.exit(1)

# Testar conexao
print("\n[TESTE] Conectando a corretora...")
if connect():
    print("[OK] Conexao estabelecida!")

    # Testar saldo
    print("\n[TESTE] Obtendo saldo...")
    balance = get_balance()
    if "error" not in balance:
        print(f"[OK] Saldo: R$ {balance.get('balance', 0):.2f}")
        print(f"[OK] Equity: R$ {balance.get('equity', 0):.2f}")
        print(f"[OK] Modo: {balance.get('mode', 'N/A')}")
    else:
        print(f"[ERRO] {balance.get('error')}")

    # Testar posicoes
    print("\n[TESTE] Obtendo posicoes abertas...")
    positions = get_positions()
    print(f"[OK] Posicoes: {len(positions)}")
    for p in positions:
        print(f"     - {p.get('symbol')}: {p.get('quantity')} @ {p.get('entry_price')}")

    # Teste de ordem (apenas em PAPER)
    if TRADING_MODE == "PAPER":
        print("\n[TESTE] Executando ordem de teste (PAPER)...")
        # Usar quantidade pequena para respeitar limite de R$ 1000
        result = buy("PETR4", 20, 47.50)  # 20 x 47.50 = R$ 950
        if result.get("success"):
            order = result.get('order', {})
            print(f"[OK] Ordem executada!")
            print(f"     ID: {order.get('id')}")
            print(f"     Ticker: {order.get('symbol')}")
            print(f"     Qtd: {order.get('quantity')} acoes")
            print(f"     Preco: R$ {order.get('price'):.2f}")
            print(f"     Valor: R$ {order.get('value'):.2f}")
            print(f"     Stop Loss: R$ {order.get('stop_loss'):.2f}")
            print(f"     Take Profit: R$ {order.get('take_profit'):.2f}")
        else:
            print(f"[ERRO] {result.get('error')}")

    # Desconectar
    print("\n[TESTE] Desconectando...")
    disconnect()
    print("[OK] Desconectado com sucesso!")

else:
    print("[ERRO] Falha na conexao!")

    if BROKER_NAME == "MT5":
        print("\n[DICA] Para usar MetaTrader 5:")
        print("  1. Instale: pip install MetaTrader5")
        print("  2. Baixe o MetaTrader 5 da sua corretora")
        print("  3. Configure MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER no .env")
        print("  4. Execute o MetaTrader 5 e faca login")
        print("  5. Execute este teste novamente")

print("\n" + "=" * 60)
print("  Teste finalizado!")
print("=" * 60)

# Verificar se MT5 esta instalado
if BROKER_NAME == "MT5":
    print("\n[INFO] Verificando MetaTrader 5...")
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            info = mt5.terminal_info()
            if info:
                print(f"[OK] MT5 instalado e funcionando")
                print(f"     Versao: {mt5.version()}")
                print(f"     Corretora: {info.company}")
            mt5.shutdown()
        else:
            print("[AVISO] MT5 instalado mas nao inicializado")
            print("        Abra o MetaTrader 5 e faca login primeiro")
    except ImportError:
        print("[AVISO] MetaTrader5 nao instalado")
        print("        Execute: pip install MetaTrader5")
    except Exception as e:
        print(f"[AVISO] Erro ao verificar MT5: {e}")

# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Modulo de Integracao com Corretoras
Suporta: MetaTrader 5, BTG Pactual (futuro)

Para usar MetaTrader 5:
1. Instale: pip install MetaTrader5
2. Baixe o MetaTrader 5 da sua corretora
3. Configure as credenciais no .env
"""

import os
from datetime import datetime
import sys
from abc import ABC, abstractmethod

# Configuracao vem sempre do .env da raiz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_config as cfg

# Configuracoes do .env
TRADING_MODE = cfg.get_str("TRADING_MODE", "PAPER")  # PAPER ou REAL
BROKER_NAME = cfg.get_str("BROKER_NAME", "MT5")
MAX_ORDER_VALUE = cfg.get_float("MAX_ORDER_VALUE", 300.0)
DAILY_LOSS_LIMIT = cfg.get_float("DAILY_LOSS_LIMIT", 150.0)
RISK_PER_TRADE = cfg.get_float("RISK_PER_TRADE", 1.0)
STOP_LOSS_PERCENT = cfg.get_float("STOP_LOSS_PERCENT", 4.0)
TAKE_PROFIT_PERCENT = cfg.get_float("TAKE_PROFIT_PERCENT", 8.0)


class BrokerInterface(ABC):
    """Interface base para corretoras"""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        pass

    @abstractmethod
    def get_balance(self) -> dict:
        pass

    @abstractmethod
    def get_positions(self) -> list:
        pass

    @abstractmethod
    def buy(self, symbol: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0) -> dict:
        pass

    @abstractmethod
    def sell(self, symbol: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0) -> dict:
        pass

    @abstractmethod
    def close_position(self, position_id: int) -> dict:
        pass


class PaperBroker(BrokerInterface):
    """Corretora simulada para testes"""

    def __init__(self):
        self.connected = False
        self.balance = 10000.0
        self.positions = []
        self.orders = []
        self.daily_pnl = 0.0

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def get_balance(self) -> dict:
        return {
            "balance": self.balance,
            "equity": self.balance + sum(p.get("pnl", 0) for p in self.positions),
            "margin_free": self.balance * 0.8,
            "daily_pnl": self.daily_pnl,
            "mode": "PAPER"
        }

    def get_positions(self) -> list:
        return self.positions

    def buy(self, symbol: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0) -> dict:
        if not self.connected:
            return {"error": "Nao conectado"}

        order_value = price * quantity
        if order_value > MAX_ORDER_VALUE:
            return {"error": f"Valor excede limite de R$ {MAX_ORDER_VALUE}"}

        if order_value > self.balance:
            return {"error": "Saldo insuficiente"}

        order = {
            "id": len(self.orders) + 1,
            "symbol": symbol,
            "type": "BUY",
            "quantity": quantity,
            "price": price,
            "stop_loss": stop_loss or price * (1 - STOP_LOSS_PERCENT/100),
            "take_profit": take_profit or price * (1 + TAKE_PROFIT_PERCENT/100),
            "value": order_value,
            "status": "FILLED",
            "timestamp": datetime.now().isoformat(),
            "mode": "PAPER"
        }

        self.orders.append(order)
        self.balance -= order_value

        position = {
            "id": order["id"],
            "symbol": symbol,
            "type": "BUY",
            "quantity": quantity,
            "entry_price": price,
            "current_price": price,
            "stop_loss": order["stop_loss"],
            "take_profit": order["take_profit"],
            "pnl": 0,
            "pnl_percent": 0
        }
        self.positions.append(position)

        return {"success": True, "order": order}

    def sell(self, symbol: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0) -> dict:
        if not self.connected:
            return {"error": "Nao conectado"}

        # Verificar se tem posicao para vender
        position = next((p for p in self.positions if p["symbol"] == symbol and p["type"] == "BUY"), None)

        if position:
            # Fechar posicao existente
            pnl = (price - position["entry_price"]) * position["quantity"]
            self.balance += (price * position["quantity"]) + pnl
            self.daily_pnl += pnl
            self.positions.remove(position)

            return {
                "success": True,
                "order": {
                    "id": len(self.orders) + 1,
                    "symbol": symbol,
                    "type": "SELL",
                    "quantity": quantity,
                    "price": price,
                    "pnl": pnl,
                    "status": "FILLED",
                    "mode": "PAPER"
                }
            }
        else:
            # Abrir posicao vendida (short)
            order = {
                "id": len(self.orders) + 1,
                "symbol": symbol,
                "type": "SELL",
                "quantity": quantity,
                "price": price,
                "stop_loss": stop_loss or price * (1 + STOP_LOSS_PERCENT/100),
                "take_profit": take_profit or price * (1 - TAKE_PROFIT_PERCENT/100),
                "status": "FILLED",
                "mode": "PAPER"
            }
            self.orders.append(order)
            return {"success": True, "order": order}

    def close_position(self, position_id: int) -> dict:
        position = next((p for p in self.positions if p["id"] == position_id), None)
        if position:
            self.positions.remove(position)
            return {"success": True, "closed": position}
        return {"error": "Posicao nao encontrada"}


class MetaTrader5Broker(BrokerInterface):
    """Integracao com MetaTrader 5"""

    def __init__(self):
        self.mt5 = None
        self.connected = False
        self.account = cfg.get_str("MT5_ACCOUNT", "")
        self.password = cfg.get_str("MT5_PASSWORD", "")
        self.server = cfg.get_str("MT5_SERVER", "")

    def connect(self) -> bool:
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5

            if not mt5.initialize():
                return False

            if self.account and self.password and self.server:
                authorized = mt5.login(
                    login=int(self.account),
                    password=self.password,
                    server=self.server
                )
                if not authorized:
                    return False

            self.connected = True
            return True
        except ImportError:
            print("MetaTrader5 nao instalado. Execute: pip install MetaTrader5")
            return False
        except Exception as e:
            print(f"Erro ao conectar MT5: {e}")
            return False

    def disconnect(self) -> bool:
        if self.mt5:
            self.mt5.shutdown()
        self.connected = False
        return True

    def get_balance(self) -> dict:
        if not self.connected:
            return {"error": "Nao conectado"}

        account_info = self.mt5.account_info()
        if account_info:
            return {
                "balance": account_info.balance,
                "equity": account_info.equity,
                "margin_free": account_info.margin_free,
                "profit": account_info.profit,
                "mode": "REAL" if TRADING_MODE == "REAL" else "DEMO"
            }
        return {"error": "Falha ao obter saldo"}

    def get_positions(self) -> list:
        if not self.connected:
            return []

        positions = self.mt5.positions_get()
        if positions:
            return [{
                "id": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "quantity": p.volume,
                "entry_price": p.price_open,
                "current_price": p.price_current,
                "stop_loss": p.sl,
                "take_profit": p.tp,
                "pnl": p.profit
            } for p in positions]
        return []

    def buy(self, symbol: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0) -> dict:
        if not self.connected:
            return {"error": "Nao conectado"}

        if TRADING_MODE != "REAL":
            return {"error": "Modo REAL nao ativado. Configure TRADING_MODE=REAL no .env"}

        # Obter preco atual se nao informado
        if price == 0:
            tick = self.mt5.symbol_info_tick(symbol)
            if tick:
                price = tick.ask
            else:
                return {"error": f"Simbolo {symbol} nao encontrado"}

        # Verificar limite de valor
        order_value = price * quantity
        if order_value > MAX_ORDER_VALUE:
            return {"error": f"Valor R$ {order_value:.2f} excede limite de R$ {MAX_ORDER_VALUE}"}

        # Calcular SL/TP
        sl = stop_loss or round(price * (1 - STOP_LOSS_PERCENT/100), 2)
        tp = take_profit or round(price * (1 + TAKE_PROFIT_PERCENT/100), 2)

        # Criar ordem
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(quantity),
            "type": self.mt5.ORDER_TYPE_BUY,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 123456,
            "comment": "NexusTradePro",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }

        result = self.mt5.order_send(request)

        if result.retcode == self.mt5.TRADE_RETCODE_DONE:
            return {
                "success": True,
                "order": {
                    "id": result.order,
                    "symbol": symbol,
                    "type": "BUY",
                    "quantity": quantity,
                    "price": result.price,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "status": "FILLED",
                    "mode": "REAL"
                }
            }
        else:
            return {"error": f"Ordem rejeitada: {result.comment}"}

    def sell(self, symbol: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0) -> dict:
        if not self.connected:
            return {"error": "Nao conectado"}

        if TRADING_MODE != "REAL":
            return {"error": "Modo REAL nao ativado"}

        if price == 0:
            tick = self.mt5.symbol_info_tick(symbol)
            if tick:
                price = tick.bid
            else:
                return {"error": f"Simbolo {symbol} nao encontrado"}

        sl = stop_loss or round(price * (1 + STOP_LOSS_PERCENT/100), 2)
        tp = take_profit or round(price * (1 - TAKE_PROFIT_PERCENT/100), 2)

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(quantity),
            "type": self.mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 123456,
            "comment": "NexusTradePro",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }

        result = self.mt5.order_send(request)

        if result.retcode == self.mt5.TRADE_RETCODE_DONE:
            return {
                "success": True,
                "order": {
                    "id": result.order,
                    "symbol": symbol,
                    "type": "SELL",
                    "quantity": quantity,
                    "price": result.price,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "status": "FILLED",
                    "mode": "REAL"
                }
            }
        else:
            return {"error": f"Ordem rejeitada: {result.comment}"}

    def close_position(self, position_id: int) -> dict:
        if not self.connected:
            return {"error": "Nao conectado"}

        positions = self.mt5.positions_get(ticket=position_id)
        if not positions:
            return {"error": "Posicao nao encontrada"}

        position = positions[0]

        # Ordem contraria para fechar
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": self.mt5.ORDER_TYPE_SELL if position.type == 0 else self.mt5.ORDER_TYPE_BUY,
            "position": position_id,
            "deviation": 20,
            "magic": 123456,
            "comment": "NexusTradePro Close",
        }

        result = self.mt5.order_send(request)

        if result.retcode == self.mt5.TRADE_RETCODE_DONE:
            return {"success": True, "closed": position_id, "pnl": position.profit}
        else:
            return {"error": f"Falha ao fechar: {result.comment}"}


def get_broker() -> BrokerInterface:
    """Factory para obter a corretora correta"""
    if TRADING_MODE == "PAPER":
        return PaperBroker()
    elif BROKER_NAME == "MT5":
        return MetaTrader5Broker()
    else:
        # Fallback para paper
        return PaperBroker()


# Instancia global
broker = get_broker()


# === Funcoes de conveniencia ===

def connect():
    """Conectar a corretora"""
    return broker.connect()

def disconnect():
    """Desconectar da corretora"""
    return broker.disconnect()

def get_balance():
    """Obter saldo"""
    return broker.get_balance()

def get_positions():
    """Obter posicoes abertas"""
    return broker.get_positions()

def buy(symbol: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0):
    """Executar ordem de compra"""
    return broker.buy(symbol, quantity, price, stop_loss, take_profit)

def sell(symbol: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0):
    """Executar ordem de venda"""
    return broker.sell(symbol, quantity, price, stop_loss, take_profit)

def close_position(position_id: int):
    """Fechar posicao"""
    return broker.close_position(position_id)


if __name__ == "__main__":
    print("=" * 50)
    print("NEXUS TRADE PRO - Teste de Integracao")
    print("=" * 50)
    print(f"Modo: {TRADING_MODE}")
    print(f"Corretora: {BROKER_NAME}")
    print(f"Limite por ordem: R$ {MAX_ORDER_VALUE}")
    print(f"Stop Loss: {STOP_LOSS_PERCENT}%")
    print(f"Take Profit: {TAKE_PROFIT_PERCENT}%")
    print("=" * 50)

    if connect():
        print("[OK] Conectado!")
        balance = get_balance()
        print(f"Saldo: {balance}")

        # Teste de compra simulada
        if TRADING_MODE == "PAPER":
            result = buy("PETR4", 100, 47.50)
            print(f"Ordem teste: {result}")
            print(f"Posicoes: {get_positions()}")

        disconnect()
        print("[OK] Desconectado")
    else:
        print("[ERRO] Falha na conexao")

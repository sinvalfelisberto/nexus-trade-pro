# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Auto Trader v1.0
===================================
Sistema de trading automatico com forward testing

Executa ciclos de:
1. Scan do mercado
2. Analise de sinais
3. Decisao de trade
4. Registro no risk manager
5. Monitoramento de posicoes

Uso:
    python auto_trader.py              # Modo simulacao (forward test)
    python auto_trader.py --live       # Modo real (quando estiver pronto)
"""

import os
import sys
import json
import time
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# Adicionar diretorio ao path
sys.path.insert(0, os.path.dirname(__file__))

# Configuracao vem sempre do .env da raiz
import env_config as cfg

# Importar modulos do NexusTrade
try:
    from risk_manager import (
        risk_manager, can_trade, register_trade,
        get_status, update_capital, reset, force_unblock
    )
    RISK_AVAILABLE = True
except ImportError:
    RISK_AVAILABLE = False
    print("[WARN] Risk Manager nao disponivel")

try:
    from broker_integration import (
        connect, disconnect, get_balance,
        get_positions, buy, sell, close_position,
        TRADING_MODE, MAX_ORDER_VALUE
    )
    BROKER_AVAILABLE = True
except ImportError:
    BROKER_AVAILABLE = False
    print("[WARN] Broker Integration nao disponivel")

try:
    from ensemble_model import ensemble_predict, get_combined_weights
    ENSEMBLE_AVAILABLE = True
except ImportError:
    ENSEMBLE_AVAILABLE = False
    print("[WARN] Ensemble Model nao disponivel")


# ══════════════════════════════════════════════════════════════
# CONFIGURACOES (lidas do .env)
# ══════════════════════════════════════════════════════════════

CONFIG = {
    # Ativos para monitorar (validados - 04/05/2026)
    "watchlist": [
        "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3",
        "PRIO3", "MGLU3", "WEGE3", "B3SA3", "RENT3",
        "GGBR4", "CSNA3", "SUZB3", "HAPV3", "RADL3"
    ],

    # Thresholds (do .env)
    "min_score_buy": cfg.get_int("MIN_SCORE_BUY", 35),
    "min_score_sell": cfg.get_int("MIN_SCORE_SELL", -35),
    "min_confidence": cfg.get_int("MIN_CONFIDENCE", 55),

    # Filtros de horario (do .env)
    "trading_hours": {
        "start": cfg.get_str("TRADING_START", "10:00"),
        "end": cfg.get_str("TRADING_END", "16:30"),
        "lunch_start": cfg.get_str("LUNCH_START", "12:00"),
        "lunch_end": cfg.get_str("LUNCH_END", "13:30")
    },

    # Ignorar horario no modo simulacao
    "ignore_trading_hours": cfg.get_bool("IGNORE_TRADING_HOURS", True),

    # Ciclo de execucao
    "scan_interval_seconds": 60,
    "max_positions": cfg.get_int("MAX_POSITIONS", 3),

    # Capital e risco (do .env - sincronizado com dashboard R$500)
    "initial_capital": cfg.get_float("INITIAL_CAPITAL", 500.0),
    "risk_per_trade": cfg.get_float("RISK_PER_TRADE", 1.0) / 100,
    "stop_loss_percent": cfg.get_float("STOP_LOSS_PERCENT", 4.0),
    "take_profit_percent": cfg.get_float("TAKE_PROFIT_PERCENT", 8.0),

    # Forward testing (salva na pasta data/)
    "log_file": os.path.join(os.path.dirname(__file__), "..", "data", "forward_test_log.json"),
    "save_interval": 5
}


# ══════════════════════════════════════════════════════════════
# DATA FETCHER (usando yfinance como primario)
# ══════════════════════════════════════════════════════════════

async def get_quote(ticker: str) -> dict:
    """Busca cotacao do ativo"""
    try:
        import yfinance as yf

        # Adicionar .SA para B3
        symbol = f"{ticker}.SA" if not ticker.endswith(".SA") else ticker
        stock = yf.Ticker(symbol)

        # Dados do dia
        hist = stock.history(period="1d")
        if hist.empty:
            return {"error": "Sem dados", "ticker": ticker}

        last = hist.iloc[-1]
        prev_close = stock.info.get("previousClose", last["Close"])

        price = float(last["Close"])
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close > 0 else 0

        return {
            "ticker": ticker,
            "price": round(price, 2),
            "change": round(change, 2),
            "changePercent": round(change_pct, 2),
            "volume": int(last["Volume"]),
            "high": round(float(last["High"]), 2),
            "low": round(float(last["Low"]), 2),
            "source": "YAHOO",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


async def get_indicators(ticker: str) -> dict:
    """Calcula indicadores tecnicos"""
    try:
        import yfinance as yf

        symbol = f"{ticker}.SA" if not ticker.endswith(".SA") else ticker
        stock = yf.Ticker(symbol)
        hist = stock.history(period="3mo")

        if len(hist) < 30:
            return {"error": "Dados insuficientes", "ticker": ticker}

        closes = hist["Close"].tolist()
        highs = hist["High"].tolist()
        lows = hist["Low"].tolist()
        volumes = hist["Volume"].tolist()

        # RSI (14)
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))

        if len(gains) >= 14:
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 50

        # EMA (9, 21)
        def ema(data, period):
            if len(data) < period:
                return sum(data) / len(data)
            k = 2 / (period + 1)
            e = sum(data[:period]) / period
            for p in data[period:]:
                e = p * k + e * (1 - k)
            return e

        ema9 = ema(closes, 9)
        ema21 = ema(closes, 21)

        # MACD
        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        macd_line = ema12 - ema26

        # Stochastic (14)
        if len(closes) >= 14:
            lowest_low = min(lows[-14:])
            highest_high = max(highs[-14:])
            if highest_high - lowest_low > 0:
                stoch_k = 100 * (closes[-1] - lowest_low) / (highest_high - lowest_low)
            else:
                stoch_k = 50
        else:
            stoch_k = 50

        # ADX simplificado
        if len(closes) >= 14:
            tr_list = []
            plus_dm_list = []
            minus_dm_list = []

            for i in range(1, len(closes)):
                tr = max(highs[i] - lows[i],
                        abs(highs[i] - closes[i-1]),
                        abs(lows[i] - closes[i-1]))
                tr_list.append(tr)

                up = highs[i] - highs[i-1]
                down = lows[i-1] - lows[i]
                plus_dm_list.append(up if up > down and up > 0 else 0)
                minus_dm_list.append(down if down > up and down > 0 else 0)

            atr = sum(tr_list[-14:]) / 14
            if atr > 0:
                plus_di = 100 * sum(plus_dm_list[-14:]) / (14 * atr)
                minus_di = 100 * sum(minus_dm_list[-14:]) / (14 * atr)
                dx = 100 * abs(plus_di - minus_di) / max(plus_di + minus_di, 0.001)
                adx = dx
            else:
                plus_di = minus_di = adx = 0
        else:
            adx = plus_di = minus_di = 0

        # Bollinger Bands
        sma20 = sum(closes[-20:]) / 20
        std20 = (sum((p - sma20)**2 for p in closes[-20:]) / 20) ** 0.5
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20

        # Volume trend
        avg_vol = sum(volumes[-20:]) / 20
        vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1

        return {
            "ticker": ticker,
            "price": round(closes[-1], 2),
            "rsi": round(rsi, 2),
            "macd_histogram": round(macd_line, 4),
            "ema9": round(ema9, 2),
            "ema21": round(ema21, 2),
            "stoch_k": round(stoch_k, 2),
            "adx": round(adx, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "bb_upper": round(bb_upper, 2),
            "bb_lower": round(bb_lower, 2),
            "bb_middle": round(sma20, 2),
            "volume_ratio": round(vol_ratio, 2),
            "obv_trend": "ALTA" if vol_ratio > 1.2 else "BAIXA" if vol_ratio < 0.8 else "NEUTRO",
            "vwap_position": "ACIMA" if closes[-1] > sma20 else "ABAIXO",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


# ══════════════════════════════════════════════════════════════
# SCORING SYSTEM (simplificado e mais robusto)
# ══════════════════════════════════════════════════════════════

def calculate_score(indicators: dict) -> dict:
    """Calcula score usando pesos otimizados (Stoch + ADX + MACD)"""

    if "error" in indicators:
        return {"error": indicators["error"], "ticker": indicators.get("ticker", "?")}

    # Pesos simplificados (removendo RSI e BB que tinham peso ~0)
    weights = {
        "stoch": 2.66,    # Dominante (66% win rate no backtest)
        "adx": 2.45,      # Forte (60.6% win rate)
        "macd": 1.19,     # Moderado
        "volume": 1.0     # Confirmacao
    }

    score = 0
    max_score = 0
    reasons = []

    # Stochastic (peso maior)
    stoch = indicators.get("stoch_k", 50)
    if stoch < 20:
        s = 25
        reasons.append(f"Stoch sobrevendido ({stoch:.0f})")
    elif stoch > 80:
        s = -25
        reasons.append(f"Stoch sobrecomprado ({stoch:.0f})")
    else:
        s = 0
    score += s * weights["stoch"]
    max_score += 25 * weights["stoch"]

    # ADX + DI
    adx = indicators.get("adx", 0)
    plus_di = indicators.get("plus_di", 0)
    minus_di = indicators.get("minus_di", 0)

    if adx >= 25:
        if plus_di > minus_di:
            s = 20
            reasons.append(f"ADX forte tendencia alta ({adx:.0f})")
        else:
            s = -20
            reasons.append(f"ADX forte tendencia baixa ({adx:.0f})")
    else:
        s = 0
    score += s * weights["adx"]
    max_score += 20 * weights["adx"]

    # MACD
    macd_h = indicators.get("macd_histogram", 0)
    if macd_h > 0:
        s = 15
        reasons.append("MACD positivo")
    else:
        s = -15
        reasons.append("MACD negativo")
    score += s * weights["macd"]
    max_score += 15 * weights["macd"]

    # Volume
    vol_ratio = indicators.get("volume_ratio", 1)
    obv = indicators.get("obv_trend", "NEUTRO")
    vwap = indicators.get("vwap_position", "NEUTRO")

    if obv == "ALTA" and vwap == "ACIMA":
        s = 10
        reasons.append("Volume confirmando alta")
    elif obv == "BAIXA" and vwap == "ABAIXO":
        s = -10
        reasons.append("Volume confirmando baixa")
    else:
        s = 0
    score += s * weights["volume"]
    max_score += 10 * weights["volume"]

    # EMA crossover (bonus)
    ema9 = indicators.get("ema9", 0)
    ema21 = indicators.get("ema21", 0)
    if ema9 > ema21:
        score += 10
        reasons.append("EMA9 > EMA21")
    else:
        score -= 10
        reasons.append("EMA9 < EMA21")
    max_score += 10

    # Normalizar
    if max_score > 0:
        normalized = (score / max_score) * 100
    else:
        normalized = 0

    normalized = max(-100, min(100, normalized))
    confidence = min(95, 50 + abs(normalized) * 0.4)

    # Sinal
    if normalized >= 40:
        signal = "COMPRA_FORTE"
    elif normalized >= 25:
        signal = "COMPRA"
    elif normalized <= -40:
        signal = "VENDA_FORTE"
    elif normalized <= -25:
        signal = "VENDA"
    else:
        signal = "NEUTRO"

    return {
        "ticker": indicators.get("ticker", "?"),
        "score": round(normalized, 1),
        "confidence": round(confidence, 1),
        "signal": signal,
        "reasons": reasons,
        "price": indicators.get("price", 0),
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# FORWARD TEST LOGGER
# ══════════════════════════════════════════════════════════════

class ForwardTestLogger:
    """Registra sinais e resultados para validacao"""

    def __init__(self, log_file: str):
        self.log_file = log_file
        self.signals = []
        self.trades = []
        self.load()

    def load(self):
        """Carrega log existente"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.signals = data.get("signals", [])
                    self.trades = data.get("trades", [])
        except:
            pass

    def save(self):
        """Salva log"""
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump({
                    "signals": self.signals[-500:],  # Ultimos 500
                    "trades": self.trades[-200:],     # Ultimos 200
                    "last_update": datetime.now().isoformat(),
                    "stats": self.get_stats()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[LOG] Erro ao salvar: {e}")

    def log_signal(self, ticker: str, score: float, signal: str, price: float, confidence: float):
        """Registra sinal gerado"""
        self.signals.append({
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "score": score,
            "signal": signal,
            "price": price,
            "confidence": confidence,
            "validated": False,
            "outcome": None
        })

    def log_trade(self, ticker: str, action: str, quantity: int,
                  entry_price: float, exit_price: float = 0, pnl: float = 0):
        """Registra trade executado"""
        self.trades.append({
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "status": "OPEN" if exit_price == 0 else "CLOSED"
        })

        if len(self.trades) % CONFIG["save_interval"] == 0:
            self.save()

    def get_stats(self) -> dict:
        """Retorna estatisticas do forward test"""
        closed = [t for t in self.trades if t["status"] == "CLOSED"]

        if not closed:
            return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0, "pnl": 0}

        wins = sum(1 for t in closed if t["pnl"] > 0)
        losses = sum(1 for t in closed if t["pnl"] <= 0)
        total_pnl = sum(t["pnl"] for t in closed)

        return {
            "total": len(closed),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(closed) * 100, 1) if closed else 0,
            "pnl": round(total_pnl, 2),
            "signals_count": len(self.signals)
        }


# ══════════════════════════════════════════════════════════════
# AUTO TRADER
# ══════════════════════════════════════════════════════════════

class AutoTrader:
    """Sistema de trading automatico"""

    def __init__(self, config: dict, mode: str = "forward_test"):
        self.config = config
        self.mode = mode  # forward_test ou live
        self.logger = ForwardTestLogger(config["log_file"])
        self.running = False
        self.capital = config["initial_capital"]

        # Carregar posicoes abertas do log anterior
        self.positions = []
        for trade in self.logger.trades:
            if trade.get("status") == "OPEN":
                self.positions.append({
                    "id": len(self.positions) + 1,
                    "ticker": trade["ticker"],
                    "action": trade["action"],
                    "quantity": trade["quantity"],
                    "entry_price": trade["entry_price"],
                    "stop_loss": trade["entry_price"] * 0.96,  # 4% default
                    "take_profit": trade["entry_price"] * 1.08,  # 8% default
                    "timestamp": trade["timestamp"]
                })
                # Descontar capital
                self.capital -= trade["quantity"] * trade["entry_price"]

        if self.positions:
            print(f"[INIT] Carregadas {len(self.positions)} posicoes abertas")

    def is_trading_hours(self) -> bool:
        """Verifica se esta em horario de negociacao"""

        # No modo simulacao, ignora horario se configurado
        if self.mode == "forward_test" and self.config.get("ignore_trading_hours", False):
            return True

        now = datetime.now()

        # Fim de semana (apenas em modo real)
        if now.weekday() >= 5:
            return False

        current_time = now.strftime("%H:%M")
        hours = self.config["trading_hours"]

        # Fora do horario
        if current_time < hours["start"] or current_time > hours["end"]:
            return False

        # Hora do almoco
        if hours["lunch_start"] <= current_time <= hours["lunch_end"]:
            return False

        return True

    async def scan_market(self) -> List[dict]:
        """Escaneia mercado e retorna sinais"""
        signals = []

        for ticker in self.config["watchlist"]:
            try:
                # Buscar indicadores
                indicators = await get_indicators(ticker)

                if "error" in indicators:
                    continue

                # Calcular score
                score_data = calculate_score(indicators)

                if "error" in score_data:
                    continue

                score = score_data["score"]
                confidence = score_data["confidence"]
                signal = score_data["signal"]
                price = score_data["price"]

                # Filtrar por confianca minima
                if confidence < self.config["min_confidence"]:
                    continue

                # Registrar sinal
                self.logger.log_signal(ticker, score, signal, price, confidence)

                # Verificar se atinge threshold
                if score >= self.config["min_score_buy"]:
                    signals.append({
                        "ticker": ticker,
                        "action": "BUY",
                        "score": score,
                        "confidence": confidence,
                        "price": price,
                        "reasons": score_data["reasons"]
                    })
                elif score <= self.config["min_score_sell"]:
                    signals.append({
                        "ticker": ticker,
                        "action": "SELL",
                        "score": score,
                        "confidence": confidence,
                        "price": price,
                        "reasons": score_data["reasons"]
                    })

            except Exception as e:
                print(f"[SCAN] Erro em {ticker}: {e}")
                continue

        # Ordenar por score absoluto (mais fortes primeiro)
        signals.sort(key=lambda x: abs(x["score"]), reverse=True)

        return signals

    def calculate_position_size(self, price: float) -> int:
        """Calcula quantidade de acoes para comprar"""
        risk_amount = self.capital * self.config["risk_per_trade"]
        stop_distance = price * (self.config["stop_loss_percent"] / 100)

        if stop_distance > 0:
            quantity = int(risk_amount / stop_distance)
        else:
            quantity = int(risk_amount / price)

        # Garantir minimo de 1
        return max(1, quantity)

    async def execute_signal(self, signal: dict) -> Optional[dict]:
        """Executa sinal de trading"""
        ticker = signal["ticker"]
        action = signal["action"]
        price = signal["price"]

        # Verificar se ja tem posicao neste ativo
        if any(p["ticker"] == ticker for p in self.positions):
            print(f"[TRADE] Ja tem posicao em {ticker}, ignorando")
            return None

        # Verificar limite de posicoes
        if len(self.positions) >= self.config["max_positions"]:
            print(f"[TRADE] Limite de {self.config['max_positions']} posicoes atingido")
            return None

        # Calcular quantidade
        quantity = self.calculate_position_size(price)
        order_value = quantity * price

        # Verificar capital
        if order_value > self.capital:
            print(f"[TRADE] Capital insuficiente: R$ {order_value:.2f} > R$ {self.capital:.2f}")
            return None

        # Verificar risk manager
        if RISK_AVAILABLE:
            can, reason, details = can_trade(
                order_value=order_value,
                confidence=signal["confidence"],
                score=abs(signal["score"])
            )
            if not can:
                print(f"[RISK] Bloqueado: {reason}")
                return None

        # Calcular stops
        if action == "BUY":
            stop_loss = round(price * (1 - self.config["stop_loss_percent"]/100), 2)
            take_profit = round(price * (1 + self.config["take_profit_percent"]/100), 2)
        else:
            stop_loss = round(price * (1 + self.config["stop_loss_percent"]/100), 2)
            take_profit = round(price * (1 - self.config["take_profit_percent"]/100), 2)

        # Executar ordem (simulada ou real)
        if self.mode == "forward_test":
            # Modo forward test - apenas registra
            order = {
                "success": True,
                "order": {
                    "id": len(self.positions) + 1,
                    "symbol": ticker,
                    "type": action,
                    "quantity": quantity,
                    "price": price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "status": "SIMULATED"
                }
            }
        elif BROKER_AVAILABLE:
            # Modo live - executa de verdade
            connect()
            if action == "BUY":
                order = buy(ticker, quantity, price, stop_loss, take_profit)
            else:
                order = sell(ticker, quantity, price, stop_loss, take_profit)
        else:
            print("[TRADE] Broker nao disponivel")
            return None

        if order.get("success"):
            # Registrar posicao
            position = {
                "id": order["order"]["id"],
                "ticker": ticker,
                "action": action,
                "quantity": quantity,
                "entry_price": price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "score": signal["score"],
                "timestamp": datetime.now().isoformat()
            }
            self.positions.append(position)

            # Atualizar capital
            self.capital -= order_value

            # Registrar no logger
            self.logger.log_trade(ticker, action, quantity, price)

            # Registrar no risk manager
            if RISK_AVAILABLE:
                register_trade(ticker, action, quantity, price)

            print(f"[TRADE] {action} {quantity}x {ticker} @ R$ {price:.2f}")
            print(f"        SL: R$ {stop_loss:.2f} | TP: R$ {take_profit:.2f}")
            print(f"        Score: {signal['score']:.1f} | Conf: {signal['confidence']:.1f}%")

            return position
        else:
            print(f"[TRADE] Erro: {order.get('error', 'Desconhecido')}")
            return None

    async def check_positions(self):
        """Verifica posicoes e fecha se atingiu stop/take"""
        for position in self.positions[:]:  # Copia para iterar
            ticker = position["ticker"]

            try:
                quote = await get_quote(ticker)
                if "error" in quote:
                    continue

                current_price = quote["price"]
                entry_price = position["entry_price"]
                stop_loss = position["stop_loss"]
                take_profit = position["take_profit"]
                quantity = position["quantity"]
                action = position["action"]

                should_close = False
                close_reason = ""

                if action == "BUY":
                    # Verificar stop loss
                    if current_price <= stop_loss:
                        should_close = True
                        close_reason = "STOP_LOSS"
                    # Verificar take profit
                    elif current_price >= take_profit:
                        should_close = True
                        close_reason = "TAKE_PROFIT"
                else:  # SELL
                    if current_price >= stop_loss:
                        should_close = True
                        close_reason = "STOP_LOSS"
                    elif current_price <= take_profit:
                        should_close = True
                        close_reason = "TAKE_PROFIT"

                if should_close:
                    # Calcular P&L
                    if action == "BUY":
                        pnl = (current_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - current_price) * quantity

                    # Atualizar capital
                    self.capital += (quantity * current_price)

                    # Remover posicao
                    self.positions.remove(position)

                    # Registrar fechamento
                    self.logger.log_trade(ticker, f"CLOSE_{action}", quantity,
                                         entry_price, current_price, pnl)

                    # Registrar no risk manager
                    if RISK_AVAILABLE:
                        register_trade(ticker, action, quantity, entry_price,
                                      current_price, pnl)

                    pnl_pct = (pnl / (entry_price * quantity)) * 100
                    status = "WIN" if pnl > 0 else "LOSS"

                    print(f"[CLOSE] {ticker} - {close_reason} - {status}")
                    print(f"        Entry: R$ {entry_price:.2f} -> Exit: R$ {current_price:.2f}")
                    print(f"        P&L: R$ {pnl:.2f} ({pnl_pct:+.1f}%)")

            except Exception as e:
                print(f"[CHECK] Erro ao verificar {ticker}: {e}")

    def print_status(self):
        """Imprime status atual"""
        stats = self.logger.get_stats()

        print("\n" + "=" * 60)
        print(f"  NEXUS AUTO TRADER - {self.mode.upper()}")
        print("=" * 60)
        print(f"  Capital: R$ {self.capital:.2f}")
        print(f"  Posicoes: {len(self.positions)}/{self.config['max_positions']}")
        print(f"  Trades: {stats['total']} (W: {stats['wins']} / L: {stats['losses']})")
        print(f"  Win Rate: {stats['win_rate']:.1f}%")
        print(f"  P&L Total: R$ {stats['pnl']:.2f}")
        print(f"  Sinais gerados: {stats['signals_count']}")

        if self.positions:
            print("\n  Posicoes abertas:")
            for p in self.positions:
                print(f"    - {p['ticker']}: {p['action']} {p['quantity']}x @ R$ {p['entry_price']:.2f}")

        print("=" * 60 + "\n")

    async def run(self):
        """Executa loop principal"""
        self.running = True
        cycle = 0

        print("\n" + "=" * 60)
        print("  NEXUS AUTO TRADER INICIADO")
        print(f"  Modo: {self.mode}")
        print(f"  Capital: R$ {self.capital:.2f}")
        print(f"  Watchlist: {len(self.config['watchlist'])} ativos")
        print("=" * 60 + "\n")

        while self.running:
            try:
                cycle += 1
                now = datetime.now()

                # Verificar horario
                if not self.is_trading_hours():
                    print(f"[{now.strftime('%H:%M')}] Fora do horario de negociacao. Aguardando...")
                    await asyncio.sleep(60)
                    continue

                print(f"\n[CICLO {cycle}] {now.strftime('%H:%M:%S')}")

                # 1. Verificar posicoes abertas
                if self.positions:
                    print("[1] Verificando posicoes...")
                    await self.check_positions()

                # 2. Escanear mercado
                print("[2] Escaneando mercado...")
                signals = await self.scan_market()

                if signals:
                    print(f"    Encontrados {len(signals)} sinais")

                    # 3. Executar sinais (ate o limite de posicoes)
                    for signal in signals:
                        if len(self.positions) >= self.config["max_positions"]:
                            break

                        print(f"[3] Avaliando {signal['ticker']} ({signal['action']})...")
                        await self.execute_signal(signal)
                else:
                    print("    Nenhum sinal forte encontrado")

                # 4. Mostrar status a cada 5 ciclos
                if cycle % 5 == 0:
                    self.print_status()
                    self.logger.save()

                # Aguardar proximo ciclo
                print(f"    Aguardando {self.config['scan_interval_seconds']}s...")
                await asyncio.sleep(self.config["scan_interval_seconds"])

            except KeyboardInterrupt:
                print("\n[STOP] Interrompido pelo usuario")
                self.running = False
            except Exception as e:
                print(f"[ERROR] {e}")
                await asyncio.sleep(10)

        # Salvar log final
        self.logger.save()
        self.print_status()
        print("\n[FIM] Auto Trader encerrado.")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

async def main():
    """Funcao principal"""

    # Verificar dependencias
    try:
        import yfinance
        print("[OK] yfinance disponivel")
    except ImportError:
        print("[ERRO] yfinance nao instalado. Execute: pip install yfinance")
        return

    # Verificar modo
    mode = "forward_test"
    if "--live" in sys.argv:
        mode = "live"
        print("[AVISO] Modo LIVE ativado - operacoes reais!")
        confirm = input("Confirmar? (s/N): ")
        if confirm.lower() != "s":
            print("Cancelado.")
            return

    # Iniciar trader
    trader = AutoTrader(CONFIG, mode=mode)

    # Resetar risk manager se solicitado
    if "--reset" in sys.argv and RISK_AVAILABLE:
        reset(CONFIG["initial_capital"])
        print(f"[RESET] Risk Manager resetado para R$ {CONFIG['initial_capital']:.2f}")

    # Executar
    await trader.run()


if __name__ == "__main__":
    asyncio.run(main())

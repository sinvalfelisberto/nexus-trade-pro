"""
NEXUS TRADE PRO — Servidor FastMCP v3.5
Servidor completo com todos os modulos avancados

Recursos:
- 20+ tools de analise tecnica
- Data Providers (Yahoo Finance, brapi.dev, Simulado)
- Multi-Timeframe Analysis
- Advanced Filters (Liquidez, Regime, Horario)
- Ensemble Model (GA, SA, PSO, Trend, Reversion)
- Risk Manager (Drawdown, Position Sizing)
"""
import os
import json
import math
import random
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carregar .env da raiz do projeto
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import httpx
from fastmcp import FastMCP

mcp = FastMCP("NexusTradePro")

BRAPI_TOKEN = os.getenv("BRAPI_TOKEN", "")
TAVILY_KEY = os.getenv("TAVILY_KEY", "")
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "+5511999999999")

# ══════════════════════════════════════════════════════════════
# MODULOS AVANCADOS
# ══════════════════════════════════════════════════════════════

# Data Providers (Yahoo Finance, etc)
try:
    from data_providers import (
        data_manager,
        get_quote as dp_get_quote,
        get_history as dp_get_history,
        get_provider_stats
    )
    DATA_PROVIDERS_AVAILABLE = True
    print("[OK] Data Providers carregados")
except ImportError as e:
    DATA_PROVIDERS_AVAILABLE = False
    print(f"[X] Data Providers nao disponiveis: {e}")

# Multi-Timeframe Analysis
try:
    from multi_timeframe import (
        mtf_analyzer,
        analyze_mtf,
        quick_mtf_analysis
    )
    MTF_AVAILABLE = True
    print("[OK] Multi-Timeframe Analysis carregado")
except ImportError as e:
    MTF_AVAILABLE = False
    print(f"[X] Multi-Timeframe nao disponivel: {e}")

# Advanced Filters
try:
    from advanced_filters import (
        filter_manager,
        check_filters,
        quick_filter_check,
        detect_regime,
        is_good_time_to_trade
    )
    FILTERS_AVAILABLE = True
    print("[OK] Advanced Filters carregados")
except ImportError as e:
    FILTERS_AVAILABLE = False
    print(f"[X] Advanced Filters nao disponiveis: {e}")

# Ensemble Model
try:
    from ensemble_model import (
        ensemble,
        ensemble_predict,
        get_ensemble_performance,
        get_combined_weights
    )
    ENSEMBLE_AVAILABLE = True
    print("[OK] Ensemble Model carregado")
except ImportError as e:
    ENSEMBLE_AVAILABLE = False
    print(f"[X] Ensemble Model nao disponivel: {e}")

# ── Cache simples ──
_cache = {}
def get_cache(key, ttl=60):
    if key in _cache:
        ts, val = _cache[key]
        if (datetime.now() - ts).seconds < ttl:
            return val
    return None

def set_cache(key, val):
    _cache[key] = (datetime.now(), val)


# ══════════════════════════════════════════════════════════════
# HELPER: EMA calculation
# ══════════════════════════════════════════════════════════════
def calc_ema(data, period):
    """Calcula Exponential Moving Average"""
    if len(data) < period:
        return sum(data) / len(data) if data else 0
    k = 2 / (period + 1)
    e = sum(data[:period]) / period
    for p in data[period:]:
        e = p * k + e * (1 - k)
    return e


def calc_sma(data, period):
    """Calcula Simple Moving Average"""
    if len(data) < period:
        return sum(data) / len(data) if data else 0
    return sum(data[-period:]) / period


# ══════════════════════════════════════════════════════════════
# TOOL 1 — Cotação real via brapi.dev
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def get_quote(ticker: str) -> dict:
    """Busca cotacao real de um ativo na B3 via brapi.dev (cache 90s)"""
    cache_key = f"quote_{ticker.upper()}"
    cached = get_cache(cache_key, ttl=90)  # Cache de 90 segundos
    if cached:
        cached["from_cache"] = True
        return cached
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://brapi.dev/api/quote/{ticker}",
                params={"token": BRAPI_TOKEN}
            )
            data = r.json()
            if "results" in data and data["results"]:
                result = data["results"][0]
                quote = {
                    "ticker": ticker.upper(),
                    "price": result.get("regularMarketPrice", 0),
                    "change": result.get("regularMarketChange", 0),
                    "changePercent": result.get("regularMarketChangePercent", 0),
                    "volume": result.get("regularMarketVolume", 0),
                    "previousClose": result.get("regularMarketPreviousClose", 0),
                    "high": result.get("regularMarketDayHigh", 0),
                    "low": result.get("regularMarketDayLow", 0),
                    "source": "REAL",
                    "timestamp": datetime.now().isoformat()
                }
                set_cache(cache_key, quote)
                return quote
            return {"error": "Ticker nao encontrado", "ticker": ticker}
    except Exception as e:
        return {"error": str(e), "ticker": ticker, "source": "ERROR"}


# ══════════════════════════════════════════════════════════════
# TOOL 2 — Cotação múltipla
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def get_quotes_batch(tickers: str) -> dict:
    """Busca cotações de múltiplos ativos (separados por vírgula)"""
    ticker_list = [t.strip().upper() for t in tickers.split(",")]
    results = {}
    for t in ticker_list:
        results[t] = await get_quote(t)
    return {"quotes": results, "count": len(results)}


# ══════════════════════════════════════════════════════════════
# TOOL 3 — Histórico de preços
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def get_history(ticker: str, days: int = 30) -> dict:
    """Busca historico de precos de um ativo"""
    # Mapear dias para range valido da API brapi
    if days <= 5:
        range_param = "5d"
    elif days <= 30:
        range_param = "1mo"
    elif days <= 90:
        range_param = "3mo"
    elif days <= 180:
        range_param = "6mo"
    elif days <= 365:
        range_param = "1y"
    else:
        range_param = "2y"

    # Cache de historico (5 minutos)
    cache_key = f"hist_{ticker}_{range_param}"
    cached = get_cache(cache_key, ttl=300)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"https://brapi.dev/api/quote/{ticker}",
                params={"token": BRAPI_TOKEN, "range": range_param, "interval": "1d"}
            )
            data = r.json()
            if "results" in data and data["results"]:
                hist = data["results"][0].get("historicalDataPrice", [])
                if hist:
                    result = {"ticker": ticker, "days": days, "range": range_param, "data": hist[-days:], "source": "REAL"}
                    set_cache(cache_key, result)
                    return result
            return {"error": "Sem dados historicos", "ticker": ticker}
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


# ══════════════════════════════════════════════════════════════
# TOOL 4 — Cálculo de indicadores técnicos básicos (RSI, MACD, BB)
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def calc_indicators(ticker: str) -> dict:
    """Calcula RSI(14), MACD, Bollinger Bands e EMAs para um ativo"""
    hist_data = await get_history(ticker, 50)
    if "error" in hist_data:
        return hist_data

    prices = [d.get("close", 0) for d in hist_data.get("data", []) if d.get("close")]
    if len(prices) < 26:
        return {"error": "Dados insuficientes para calculo (minimo 26 periodos)", "ticker": ticker}

    # RSI(14) - Calculo correto com suavizacao
    period = 14
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    if len(gains) >= period:
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    else:
        avg_gain = sum(gains) / max(len(gains), 1)
        avg_loss = sum(losses) / max(len(losses), 1)

    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9) - CORRIGIDO: Signal e a EMA(9) da linha MACD
    macd_values = []
    for i in range(26, len(prices) + 1):
        subset = prices[:i]
        ema12 = calc_ema(subset, 12)
        ema26 = calc_ema(subset, 26)
        macd_values.append(ema12 - ema26)

    macd_line = macd_values[-1] if macd_values else 0
    signal_line = calc_ema(macd_values, 9) if len(macd_values) >= 9 else macd_line
    macd_hist = macd_line - signal_line

    # Bollinger Bands (20, 2)
    period_bb = min(20, len(prices))
    sma20 = sum(prices[-period_bb:]) / period_bb
    std20 = (sum((p - sma20)**2 for p in prices[-period_bb:]) / period_bb) ** 0.5
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20

    return {
        "ticker": ticker,
        "price": prices[-1],
        "rsi": round(rsi, 2),
        "macd": {"line": round(macd_line, 4), "signal": round(signal_line, 4), "histogram": round(macd_hist, 4)},
        "bollinger": {"upper": round(bb_upper, 2), "middle": round(sma20, 2), "lower": round(bb_lower, 2)},
        "ema9": round(calc_ema(prices, 9), 2),
        "ema21": round(calc_ema(prices, 21), 2),
        "source": "CALCULATED",
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# TOOL 5 — Indicadores Avançados (ADX, Stochastic, ATR, VWAP, OBV)
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def calc_advanced_indicators(ticker: str) -> dict:
    """Calcula indicadores avançados: ADX, Stochastic, ATR, VWAP, OBV"""
    hist_data = await get_history(ticker, 50)
    if "error" in hist_data:
        return hist_data

    data = hist_data.get("data", [])
    if len(data) < 20:
        return {"error": "Dados insuficientes para cálculo avançado", "ticker": ticker}

    # Extrair OHLCV
    highs = [d.get("high", d.get("close", 0)) for d in data]
    lows = [d.get("low", d.get("close", 0)) for d in data]
    closes = [d.get("close", 0) for d in data]
    volumes = [d.get("volume", 0) for d in data]

    # ── ATR (Average True Range) - 14 períodos ──
    tr_list = []
    for i in range(1, len(data)):
        high_low = highs[i] - lows[i]
        high_close = abs(highs[i] - closes[i-1])
        low_close = abs(lows[i] - closes[i-1])
        tr = max(high_low, high_close, low_close)
        tr_list.append(tr)
    atr = calc_ema(tr_list[-14:], 14) if len(tr_list) >= 14 else sum(tr_list) / max(len(tr_list), 1)

    # ── ADX (Average Directional Index) - 14 períodos ──
    plus_dm_list = []
    minus_dm_list = []
    for i in range(1, len(data)):
        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        plus_dm = up_move if up_move > down_move and up_move > 0 else 0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)

    if len(tr_list) >= 14 and atr > 0:
        plus_di = 100 * calc_ema(plus_dm_list[-14:], 14) / atr
        minus_di = 100 * calc_ema(minus_dm_list[-14:], 14) / atr
        dx = 100 * abs(plus_di - minus_di) / max(plus_di + minus_di, 0.0001)
        adx = dx  # Simplificado
    else:
        plus_di = minus_di = adx = 0

    # ── Stochastic Oscillator (14, 3, 3) ──
    period = 14
    if len(closes) >= period:
        recent_closes = closes[-period:]
        recent_highs = highs[-period:]
        recent_lows = lows[-period:]
        lowest_low = min(recent_lows)
        highest_high = max(recent_highs)
        if highest_high - lowest_low > 0:
            stoch_k = 100 * (closes[-1] - lowest_low) / (highest_high - lowest_low)
        else:
            stoch_k = 50
        # %D é SMA de 3 períodos do %K (simplificado)
        stoch_d = stoch_k  # Em implementação real, seria média de 3 %K
    else:
        stoch_k = stoch_d = 50

    # ── VWAP (Volume Weighted Average Price) ──
    total_volume = sum(volumes) if volumes else 1
    if total_volume > 0:
        typical_prices = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
        vwap = sum(tp * v for tp, v in zip(typical_prices, volumes)) / total_volume
    else:
        vwap = closes[-1] if closes else 0

    # ── OBV (On Balance Volume) ──
    obv = 0
    obv_list = [0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            obv += volumes[i]
        elif closes[i] < closes[i-1]:
            obv -= volumes[i]
        obv_list.append(obv)
    obv_trend = "ALTA" if len(obv_list) >= 2 and obv_list[-1] > obv_list[-5] else "BAIXA" if len(obv_list) >= 5 and obv_list[-1] < obv_list[-5] else "NEUTRO"

    # ── Força da tendência baseada no ADX ──
    if adx >= 25:
        trend_strength = "FORTE"
    elif adx >= 20:
        trend_strength = "MODERADA"
    else:
        trend_strength = "FRACA"

    return {
        "ticker": ticker,
        "price": closes[-1] if closes else 0,
        "adx": {
            "value": round(adx, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "trend_strength": trend_strength
        },
        "stochastic": {
            "k": round(stoch_k, 2),
            "d": round(stoch_d, 2),
            "signal": "SOBRECOMPRADO" if stoch_k > 80 else "SOBREVENDIDO" if stoch_k < 20 else "NEUTRO"
        },
        "atr": {
            "value": round(atr, 4),
            "percent": round((atr / closes[-1]) * 100, 2) if closes[-1] > 0 else 0
        },
        "vwap": {
            "value": round(vwap, 2),
            "position": "ACIMA" if closes[-1] > vwap else "ABAIXO"
        },
        "obv": {
            "value": obv,
            "trend": obv_trend
        },
        "source": "CALCULATED",
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# TOOL 6 — Análise de Sentimento
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def analyze_sentiment(text: str) -> dict:
    """Analisa sentimento de texto/notícia (positivo/negativo/neutro)"""
    # Palavras-chave para análise de sentimento do mercado financeiro
    positive_words = [
        "alta", "subir", "valorização", "lucro", "crescimento", "positivo",
        "otimismo", "compra", "recuperação", "ganho", "recorde", "supera",
        "expansão", "avanço", "melhora", "forte", "bullish", "bull",
        "dividendos", "aquisição", "fusão", "upgrade", "recomendação"
    ]
    negative_words = [
        "queda", "baixa", "desvalorização", "prejuízo", "perda", "negativo",
        "pessimismo", "venda", "crise", "recessão", "colapso", "derrocada",
        "retração", "piora", "fraco", "bearish", "bear", "default",
        "falência", "investigação", "fraude", "downgrade", "corte"
    ]

    text_lower = text.lower()

    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)

    total = positive_count + negative_count
    if total == 0:
        sentiment = "NEUTRO"
        score = 0
        confidence = 30
    elif positive_count > negative_count:
        sentiment = "POSITIVO"
        score = min(100, int((positive_count / total) * 100))
        confidence = min(90, 50 + (positive_count - negative_count) * 10)
    else:
        sentiment = "NEGATIVO"
        score = max(-100, -int((negative_count / total) * 100))
        confidence = min(90, 50 + (negative_count - positive_count) * 10)

    return {
        "text_preview": text[:100] + "..." if len(text) > 100 else text,
        "sentiment": sentiment,
        "score": score,
        "confidence": confidence,
        "positive_indicators": positive_count,
        "negative_indicators": negative_count,
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# TOOL 7 — Position Sizing (Tamanho da Posição)
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def calc_position_size(
    ticker: str,
    capital: float,
    risk_percent: float = 2.0,
    stop_loss_percent: float = 3.0,
    use_kelly: bool = False,
    win_rate: float = 0.55,
    avg_win: float = 1.5,
    avg_loss: float = 1.0
) -> dict:
    """Calcula tamanho ideal da posição baseado em risco e ATR"""
    quote = await get_quote(ticker)
    if "error" in quote:
        return quote

    price = quote.get("price", 0)
    if price <= 0:
        return {"error": "Preço inválido", "ticker": ticker}

    # Buscar ATR para stop dinâmico
    adv_ind = await calc_advanced_indicators(ticker)
    atr = adv_ind.get("atr", {}).get("value", price * 0.03) if "error" not in adv_ind else price * 0.03

    # Método 1: Position sizing baseado em risco fixo
    risk_amount = capital * (risk_percent / 100)
    stop_distance = price * (stop_loss_percent / 100)
    position_fixed = int(risk_amount / stop_distance)

    # Método 2: Position sizing baseado em ATR
    atr_multiplier = 2.0  # Stop a 2x ATR
    stop_atr = atr * atr_multiplier
    position_atr = int(risk_amount / stop_atr) if stop_atr > 0 else position_fixed

    # Método 3: Kelly Criterion simplificado
    if use_kelly and avg_loss > 0:
        # Kelly = W - [(1-W) / R] onde W = win rate, R = avg_win/avg_loss
        r = avg_win / avg_loss
        kelly_fraction = win_rate - ((1 - win_rate) / r)
        kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap em 25% do capital
        kelly_amount = capital * kelly_fraction
        position_kelly = int(kelly_amount / price)
    else:
        kelly_fraction = 0
        position_kelly = 0

    # Recomendação: usar o mais conservador
    recommended = min(position_fixed, position_atr) if not use_kelly else min(position_fixed, position_atr, position_kelly)
    recommended = max(1, recommended)  # Mínimo 1 ação

    return {
        "ticker": ticker,
        "price": price,
        "capital": capital,
        "risk_percent": risk_percent,
        "risk_amount": round(risk_amount, 2),
        "methods": {
            "fixed_stop": {
                "quantity": position_fixed,
                "stop_price": round(price - stop_distance, 2),
                "total_cost": round(position_fixed * price, 2)
            },
            "atr_based": {
                "quantity": position_atr,
                "atr": round(atr, 4),
                "stop_price": round(price - stop_atr, 2),
                "total_cost": round(position_atr * price, 2)
            },
            "kelly": {
                "quantity": position_kelly,
                "kelly_fraction": round(kelly_fraction * 100, 2),
                "total_cost": round(position_kelly * price, 2)
            } if use_kelly else None
        },
        "recommended": {
            "quantity": recommended,
            "total_cost": round(recommended * price, 2),
            "percent_of_capital": round((recommended * price / capital) * 100, 2)
        },
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# TOOL 8 — Trailing Stop Dinâmico
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def get_trailing_stop(
    ticker: str,
    entry_price: float,
    current_price: float = 0,
    method: str = "atr",
    atr_multiplier: float = 2.0,
    percent: float = 3.0
) -> dict:
    """Calcula trailing stop dinâmico baseado em ATR ou percentual"""
    if current_price <= 0:
        quote = await get_quote(ticker)
        if "error" in quote:
            return quote
        current_price = quote.get("price", entry_price)

    profit_percent = ((current_price - entry_price) / entry_price) * 100

    if method == "atr":
        adv_ind = await calc_advanced_indicators(ticker)
        if "error" in adv_ind:
            atr = current_price * 0.03
        else:
            atr = adv_ind.get("atr", {}).get("value", current_price * 0.03)

        stop_distance = atr * atr_multiplier
        trailing_stop = current_price - stop_distance
    else:
        stop_distance = current_price * (percent / 100)
        trailing_stop = current_price - stop_distance

    # Stop nunca abaixo do preço de entrada (proteger capital)
    breakeven_stop = entry_price

    # Se em lucro > 2%, mover stop para breakeven
    if profit_percent > 2:
        trailing_stop = max(trailing_stop, breakeven_stop)

    # Se em lucro > 5%, proteger 50% do lucro
    if profit_percent > 5:
        profit_protection = entry_price + (current_price - entry_price) * 0.5
        trailing_stop = max(trailing_stop, profit_protection)

    return {
        "ticker": ticker,
        "entry_price": entry_price,
        "current_price": current_price,
        "profit_percent": round(profit_percent, 2),
        "method": method,
        "trailing_stop": round(trailing_stop, 2),
        "stop_distance": round(stop_distance, 2),
        "stop_distance_percent": round((stop_distance / current_price) * 100, 2),
        "risk_reward": round(profit_percent / (stop_distance / current_price * 100), 2) if stop_distance > 0 else 0,
        "recommendation": "MANTER" if current_price > trailing_stop else "STOP ACIONADO",
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# HELPER: Regime Detection (Bull/Bear/Neutro)
# ══════════════════════════════════════════════════════════════
def detect_market_regime(prices: list, lookback: int = 10) -> dict:
    """Detecta regime de mercado baseado em tendencia e volatilidade"""
    if len(prices) < lookback:
        return {"regime": "NEUTRO", "volatility": 1.0, "trend": 0}

    recent = prices[-lookback:]

    # Calcular retornos
    returns = [(recent[i] - recent[i-1]) / recent[i-1] * 100 for i in range(1, len(recent))]

    # Volatilidade
    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    volatility = variance ** 0.5

    # Tendencia
    trend = (recent[-1] - recent[0]) / recent[0] * 100

    # Classificar
    if trend > 3 and mean_ret > 0.2:
        regime = "BULL"
    elif trend < -3 and mean_ret < -0.2:
        regime = "BEAR"
    else:
        regime = "NEUTRO"

    return {
        "regime": regime,
        "volatility": round(volatility, 2),
        "trend": round(trend, 2),
        "recommendation": "OPERAR" if regime == "BULL" else "CAUTELA" if regime == "BEAR" else "AGUARDAR"
    }


# ══════════════════════════════════════════════════════════════
# TOOL 9 — Score Composto Melhorado v2.0
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def calc_score(
    ticker: str,
    peso_rsi: float = 0.06,     # v3.0 TURBO: ELIMINADO (pior indicador)
    peso_macd: float = 1.19,    # v3.0 TURBO: Mantido
    peso_bb: float = 0.09,      # v3.0 TURBO: ELIMINADO
    peso_adx: float = 2.45,     # v3.0 TURBO: MUITO ALTO (60.6% WR)
    peso_stoch: float = 2.66,   # v3.0 TURBO: DOMINANTE (66.3% WR - melhor!)
    peso_volume: float = 2.05,  # v3.0 TURBO: ALTO (60.1% WR)
    peso_news: float = 1.07     # v3.0 TURBO: Moderado
) -> dict:
    """Calcula score composto melhorado (-100 a +100) com todos os indicadores"""
    # Buscar indicadores básicos e avançados
    ind = await calc_indicators(ticker)

    # Se não há dados históricos, usar modo simplificado baseado na cotação
    if "error" in ind:
        quote = await get_quote(ticker)
        if "error" in quote:
            return quote

        # Score simplificado baseado na variação do dia
        change = quote.get("changePercent", 0)
        price = quote.get("price", 0)
        volume = quote.get("volume", 0)
        high = quote.get("high", price)
        low = quote.get("low", price)

        score = 0
        reasons = []

        # Score baseado na variação diária
        if change <= -3:
            score += 40
            reasons.append(f"Queda forte ({change:.2f}%) - oportunidade")
        elif change <= -1.5:
            score += 25
            reasons.append(f"Queda moderada ({change:.2f}%)")
        elif change >= 3:
            score -= 30
            reasons.append(f"Alta forte ({change:.2f}%) - sobrecomprado")
        elif change >= 1.5:
            score += 10
            reasons.append(f"Momentum positivo ({change:.2f}%)")

        # Score baseado na posição no range do dia
        if high > low:
            position = (price - low) / (high - low)
            if position < 0.3:
                score += 20
                reasons.append("Preço próximo da mínima do dia")
            elif position > 0.7:
                score -= 15
                reasons.append("Preço próximo da máxima do dia")

        # Volume alto = mais confiança
        if volume > 1000000:
            score += 10
            reasons.append("Volume alto")

        normalized_score = max(-100, min(100, score))
        confidence = min(abs(normalized_score) + 30, 100)

        if normalized_score >= 30:
            signal = "COMPRAR"
        elif normalized_score <= -25:
            signal = "VENDER"
        else:
            signal = "NEUTRO"

        return {
            "ticker": ticker,
            "score": normalized_score,
            "raw_score": score,
            "signal": signal,
            "confidence": confidence,
            "reasons": reasons,
            "breakdown": {"variation": {"score": score, "weighted": score}},
            "indicators": {"price": price, "change": change, "volume": volume, "mode": "SIMPLIFIED"},
            "advanced": None,
            "weights": {},
            "timestamp": datetime.now().isoformat()
        }

    adv = await calc_advanced_indicators(ticker)

    score = 0
    max_score = 0
    reasons = []
    breakdown = {}

    rsi = ind["rsi"]
    price = ind["price"]
    macd_h = ind["macd"]["histogram"]
    bb = ind["bollinger"]
    ema9 = ind["ema9"]
    ema21 = ind["ema21"]

    # ── RSI Score (-30 a +30) ──
    rsi_score = 0
    if rsi < 30:
        rsi_score = 30
        reasons.append(f"RSI sobrevendido ({rsi})")
    elif rsi < 40:
        rsi_score = 15
        reasons.append(f"RSI baixo ({rsi})")
    elif rsi > 70:
        rsi_score = -30
        reasons.append(f"RSI sobrecomprado ({rsi})")
    elif rsi > 60:
        rsi_score = -15
        reasons.append(f"RSI alto ({rsi})")
    score += rsi_score * peso_rsi
    max_score += 30 * peso_rsi
    breakdown["rsi"] = {"score": rsi_score, "weighted": round(rsi_score * peso_rsi, 2)}

    # ── MACD Score (-25 a +25) ──
    macd_score = 25 if macd_h > 0 else -25
    reasons.append("MACD positivo (bullish)" if macd_h > 0 else "MACD negativo (bearish)")
    score += macd_score * peso_macd
    max_score += 25 * peso_macd
    breakdown["macd"] = {"score": macd_score, "weighted": round(macd_score * peso_macd, 2)}

    # ── Bollinger Score (-25 a +25) ──
    bb_score = 0
    if price <= bb["lower"]:
        bb_score = 25
        reasons.append("Preço na banda inferior (oversold)")
    elif price >= bb["upper"]:
        bb_score = -25
        reasons.append("Preço na banda superior (overbought)")
    score += bb_score * peso_bb
    max_score += 25 * peso_bb
    breakdown["bollinger"] = {"score": bb_score, "weighted": round(bb_score * peso_bb, 2)}

    # ── EMA Crossover (-20 a +20) ──
    ema_score = 20 if ema9 > ema21 else -20
    reasons.append("EMA9 > EMA21 (tendência alta)" if ema9 > ema21 else "EMA9 < EMA21 (tendência baixa)")
    score += ema_score
    max_score += 20
    breakdown["ema"] = {"score": ema_score, "weighted": ema_score}

    # ── ADX Score (-15 a +15) ──
    adx_score = 0
    if "error" not in adv:
        adx = adv.get("adx", {})
        adx_val = adx.get("value", 0)
        plus_di = adx.get("plus_di", 0)
        minus_di = adx.get("minus_di", 0)

        if adx_val >= 25:
            if plus_di > minus_di:
                adx_score = 15
                reasons.append(f"ADX forte tendência de alta ({adx_val})")
            else:
                adx_score = -15
                reasons.append(f"ADX forte tendência de baixa ({adx_val})")
        score += adx_score * peso_adx
        max_score += 15 * peso_adx
        breakdown["adx"] = {"score": adx_score, "weighted": round(adx_score * peso_adx, 2)}

    # ── Stochastic Score (-15 a +15) ──
    stoch_score = 0
    if "error" not in adv:
        stoch_k = adv.get("stochastic", {}).get("k", 50)
        if stoch_k < 20:
            stoch_score = 15
            reasons.append(f"Stochastic sobrevendido ({stoch_k})")
        elif stoch_k > 80:
            stoch_score = -15
            reasons.append(f"Stochastic sobrecomprado ({stoch_k})")
        score += stoch_score * peso_stoch
        max_score += 15 * peso_stoch
        breakdown["stochastic"] = {"score": stoch_score, "weighted": round(stoch_score * peso_stoch, 2)}

    # ── Volume/OBV Score (-10 a +10) ──
    volume_score = 0
    if "error" not in adv:
        obv_trend = adv.get("obv", {}).get("trend", "NEUTRO")
        vwap_pos = adv.get("vwap", {}).get("position", "NEUTRO")

        if obv_trend == "ALTA" and vwap_pos == "ACIMA":
            volume_score = 10
            reasons.append("OBV em alta + Preço acima VWAP")
        elif obv_trend == "BAIXA" and vwap_pos == "ABAIXO":
            volume_score = -10
            reasons.append("OBV em baixa + Preço abaixo VWAP")
        score += volume_score * peso_volume
        max_score += 10 * peso_volume
        breakdown["volume"] = {"score": volume_score, "weighted": round(volume_score * peso_volume, 2)}

    # Normalizar score para -100 a +100
    if max_score > 0:
        normalized_score = int((score / max_score) * 100)
    else:
        normalized_score = 0
    normalized_score = max(-100, min(100, normalized_score))

    confidence = min(abs(normalized_score), 100)

    # Sinais com limiares ajustados
    if normalized_score >= 40:
        signal = "COMPRA FORTE"
    elif normalized_score >= 20:
        signal = "COMPRAR"
    elif normalized_score <= -40:
        signal = "VENDA FORTE"
    elif normalized_score <= -20:
        signal = "VENDER"
    else:
        signal = "NEUTRO"

    # Detectar regime de mercado
    hist_data = await get_history(ticker, 15)
    regime_info = {"regime": "NEUTRO", "volatility": 1.0, "trend": 0}
    if "error" not in hist_data:
        hist_prices = [d.get("close", 0) for d in hist_data.get("data", []) if d.get("close", 0) > 0]
        if len(hist_prices) >= 5:
            regime_info = detect_market_regime(hist_prices, 10)

    # Ajustar confianca baseado no regime
    regime_multiplier = 1.2 if regime_info["regime"] == "BULL" else 0.85 if regime_info["regime"] == "BEAR" else 1.0
    adjusted_confidence = min(100, int(confidence * regime_multiplier))

    return {
        "ticker": ticker,
        "score": normalized_score,
        "raw_score": round(score, 2),
        "signal": signal,
        "confidence": adjusted_confidence,
        "reasons": reasons,
        "breakdown": breakdown,
        "indicators": ind,
        "advanced": adv if "error" not in adv else None,
        "regime": regime_info,
        "weights": {
            "rsi": peso_rsi,
            "macd": peso_macd,
            "bb": peso_bb,
            "adx": peso_adx,
            "stoch": peso_stoch,
            "volume": peso_volume,
            "news": peso_news
        },
        "version": "2.0",
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# HELPER: Google News RSS (gratuito, sem limite)
# ══════════════════════════════════════════════════════════════
async def fetch_google_news(query: str, max_results: int = 5) -> list:
    """Busca noticias via Google News RSS (gratuito)"""
    try:
        from urllib.parse import quote
        url = f"https://news.google.com/rss/search?q={quote(query)}+Brasil+mercado&hl=pt-BR&gl=BR&ceid=BR:pt-419"

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            content = r.text

            # Parse simples do RSS XML
            results = []
            items = content.split("<item>")[1:max_results+1]

            for item in items:
                # Extrair titulo
                title_start = item.find("<title>") + 7
                title_end = item.find("</title>")
                title = item[title_start:title_end] if title_start > 6 else ""
                title = title.replace("<![CDATA[", "").replace("]]>", "").strip()

                # Extrair link
                link_start = item.find("<link>") + 6
                link_end = item.find("</link>")
                link = item[link_start:link_end] if link_start > 5 else "#"

                # Extrair data
                pub_start = item.find("<pubDate>") + 9
                pub_end = item.find("</pubDate>")
                pub_date = item[pub_start:pub_end] if pub_start > 8 else ""

                # Extrair fonte
                source_start = item.find("<source")
                source_end = item.find("</source>")
                source = ""
                if source_start > 0 and source_end > source_start:
                    source_text = item[source_start:source_end]
                    s_start = source_text.find(">") + 1
                    source = source_text[s_start:] if s_start > 0 else ""

                if title:
                    results.append({
                        "title": title,
                        "url": link,
                        "content": f"{title} - {source}",
                        "source_name": source,
                        "pub_date": pub_date
                    })

            return results
    except Exception as e:
        return []


# ══════════════════════════════════════════════════════════════
# TOOL 10 — Noticias (Tavily + Google News RSS backup)
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def search_news(query: str, max_results: int = 5) -> dict:
    """Busca noticias em tempo real (Tavily + Google News RSS backup)"""
    # Cache de 30 minutos
    cache_key = f"news_{query.lower().strip()}"
    cached = get_cache(cache_key, ttl=1800)
    if cached:
        cached["from_cache"] = True
        return cached

    # Tentar Tavily primeiro (se configurado)
    if TAVILY_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": TAVILY_KEY,
                        "query": f"{query} mercado financeiro Brasil",
                        "max_results": max_results,
                        "search_depth": "basic",
                        "include_answer": True
                    }
                )
                data = r.json()

                if "results" in data and data.get("results"):
                    results = []
                    total_sentiment = 0
                    for n in data.get("results", []):
                        content = n.get("content", "")
                        sentiment = await analyze_sentiment(content)
                        results.append({
                            "title": n.get("title"),
                            "url": n.get("url"),
                            "content": content[:200],
                            "sentiment": sentiment.get("sentiment"),
                            "sentiment_score": sentiment.get("score")
                        })
                        total_sentiment += sentiment.get("score", 0)

                    avg_sentiment = total_sentiment / len(results) if results else 0
                    result = {
                        "query": query,
                        "answer": data.get("answer", ""),
                        "results": results,
                        "overall_sentiment": "POSITIVO" if avg_sentiment > 20 else "NEGATIVO" if avg_sentiment < -20 else "NEUTRO",
                        "sentiment_score": round(avg_sentiment, 2),
                        "source": "TAVILY",
                        "timestamp": datetime.now().isoformat()
                    }
                    set_cache(cache_key, result)
                    return result
        except:
            pass  # Fallback para Google News

    # Backup: Google News RSS (gratuito, sem limite)
    google_results = await fetch_google_news(query, max_results)
    if google_results:
        results = []
        total_sentiment = 0
        for n in google_results:
            sentiment = await analyze_sentiment(n.get("title", ""))
            results.append({
                "title": n.get("title"),
                "url": n.get("url"),
                "content": n.get("content", "")[:200],
                "sentiment": sentiment.get("sentiment"),
                "sentiment_score": sentiment.get("score"),
                "source_name": n.get("source_name", "")
            })
            total_sentiment += sentiment.get("score", 0)

        avg_sentiment = total_sentiment / len(results) if results else 0
        result = {
            "query": query,
            "answer": f"Ultimas noticias sobre {query} do Google News",
            "results": results,
            "overall_sentiment": "POSITIVO" if avg_sentiment > 20 else "NEGATIVO" if avg_sentiment < -20 else "NEUTRO",
            "sentiment_score": round(avg_sentiment, 2),
            "source": "GOOGLE_NEWS",
            "timestamp": datetime.now().isoformat()
        }
        set_cache(cache_key, result)
        return result

    # Ultimo recurso: Fallback estatico
    fallback_news = {
        "query": query,
        "answer": "Mercado opera com volatilidade moderada. Investidores aguardam dados economicos.",
        "results": [
            {"title": "Ibovespa opera estavel aguardando decisoes do Fed", "url": "#", "content": "O principal indice da bolsa brasileira opera proximo da estabilidade...", "sentiment": "NEUTRO", "sentiment_score": 0},
            {"title": "Dolar recua frente ao real com fluxo estrangeiro", "url": "#", "content": "A moeda americana apresenta leve queda em relacao ao real...", "sentiment": "POSITIVO", "sentiment_score": 15},
            {"title": "Commodities em alta beneficiam exportadoras", "url": "#", "content": "Precos de minerio e petroleo sustentam acoes do setor...", "sentiment": "POSITIVO", "sentiment_score": 20}
        ],
        "overall_sentiment": "NEUTRO",
        "sentiment_score": 11.67,
        "source": "FALLBACK",
        "timestamp": datetime.now().isoformat()
    }
    set_cache(cache_key, fallback_news)
    return fallback_news


# ══════════════════════════════════════════════════════════════
# TOOL 11 — Scanner de mercado (múltiplos ativos)
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def scan_market(category: str = "all") -> dict:
    """Escaneia múltiplos ativos e retorna rankings por score"""
    categories = {
        # ALTA VOLATILIDADE - Day Trade (mais lucrativos)
        "volateis": [
            "PETR4","VALE3","MGLU3","PRIO3","VBBR3","ENEV3","CVCB3","AZUL4","GOLL4",
            "COGN3","IRBR3","OIBR3","BHIA3","CIEL3","BRFS3","MRFG3","BEEF3","LWSA3"
        ],
        # BLUE CHIPS - Maior liquidez
        "blue_chips": [
            "PETR4","VALE3","ITUB4","BBDC4","BBAS3","WEGE3","ABEV3","B3SA3","RENT3",
            "SUZB3","GGBR4","CSNA3","JBSS3","RADL3","RAIL3","SBSP3","VIVT3","TOTS3"
        ],
        # PETRÓLEO E ENERGIA - Em alta 2026
        "energia": [
            "PETR4","PETR3","PRIO3","RRRP3","RECV3","VBBR3","UGPA3","CSAN3","RAIZ4",
            "ENEV3","ELET3","ELET6","CMIG4","CPLE6","CPFE3","EGIE3","TAEE11","AURE3"
        ],
        # SMALL CAPS - Alto potencial
        "small_caps": [
            "VAMO3","SIMH3","SOJA3","RANI3","PRNR3","TTEN3","PLPL3","TEND3","POMO3",
            "INTB3","SBFG3","MLAS3","AERI3","DESK3","ESPA3","KEPL3","MDNE3","TRIS3",
            "SMFT3","MBLY3","SEQL3","ALLD3","MTRE3","DIRR3","EVEN3","LAVV3"
        ],
        # VAREJO - Alta volatilidade
        "varejo": [
            "MGLU3","LREN3","AZZA3","AMER3","PETZ3","SOMA3","CEAB3","GUAR3","GRND3",
            "VIVA3","ASAI3","CRFB3","PCAR3","MDIA3","NTCO3","LJQQ3","AMAR3","LEVE3"
        ],
        # BANCOS E FINANCEIRO
        "financeiro": [
            "ITUB4","BBDC4","BBAS3","SANB11","BPAC11","BRSR6","BMGB4","BIDI11","MODL11",
            "B3SA3","CIEL3","PAGS34","STNE34","XPBR31","WIZC3","SULA11","BBSE3","IRBR3"
        ],
        # COMMODITIES
        "commodities": [
            "VALE3","CSNA3","GGBR4","USIM5","GOAU4","CMIN3","SUZB3","KLBN11","DTEX3",
            "SLCE3","SOJA3","AGRO3","SMTO3","BEEF3","JBSS3","BRFS3","MRFG3","MDIA3"
        ],
        # BDRs - Empresas internacionais
        "bdrs": [
            "AAPL34","MSFT34","GOOGL34","AMZN34","NVDA34","META34","TSLA34","NFLX34",
            "DISB34","NIKE34","COCA34","MCDL34","VISA34","JPMC34","BABA34","INTU34",
            "MELI34","AMZO34","GOGL34","M1TA34","A1MD34","PYPL34","UBER34","ABNB34"
        ],
        # ETFs
        "etfs": [
            "IVVB11","BOVA11","SMAL11","NASD11","HASH11","QBTC11","ETHE11","GOLD11",
            "DIVO11","XFIX11","FIND11","SPXI11","BOVV11","MATB11","GOVE11","TECK11"
        ],
        # FIIs - Fundos Imobiliários
        "fiis": [
            "HGLG11","MXRF11","KNCR11","XPML11","VISC11","HGBS11","HSML11","XPLG11",
            "VILG11","BTLG11","RBRP11","BRCR11","KNRI11","PVBI11","CPTS11","RECR11"
        ],
        # RECOMENDAÇÕES ANALISTAS 2026
        "recomendados_2026": [
            "PRIO3","LREN3","AZZA3","SBFG3","ASAI3","INTB3","VBBR3","ENEV3","WEGE3",
            "RENT3","TOTS3","RADL3","B3SA3","EQTL3","VIVT3","FLRY3","RDOR3","HAPV3"
        ]
    }

    # "all" retorna mix otimizado para trading
    if category == "all":
        tickers = list(set(
            categories["volateis"][:12] +
            categories["blue_chips"][:8] +
            categories["energia"][:6] +
            categories["small_caps"][:10] +
            categories["recomendados_2026"][:8]
        ))
    else:
        tickers = categories.get(category, categories["blue_chips"])
    results = []
    for t in tickers:
        s = await calc_score(t)
        if "error" not in s:
            results.append(s)
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"category": category, "scanned": len(results), "ranking": results}


# ══════════════════════════════════════════════════════════════
# TOOL 12 — Simulador de portfolio
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def simulate_trade(ticker: str, action: str, quantity: int, price: float = 0) -> dict:
    """Simula compra/venda de ativos (modo paper trading)"""
    if price == 0:
        quote = await get_quote(ticker)
        price = quote.get("price", 0)
    total = price * quantity
    fee = total * 0.000325  # emolumentos B3
    return {
        "ticker": ticker,
        "action": action.upper(),
        "quantity": quantity,
        "price": price,
        "total": round(total, 2),
        "fee": round(fee, 2),
        "net": round(total + fee if action.upper() == "COMPRAR" else total - fee, 2),
        "mode": "SIMULADO",
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# TOOL 13 — Alerta WhatsApp (placeholder)
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def send_alert(message: str, ticker: str = "") -> dict:
    """Envia alerta via WhatsApp (placeholder — precisa Twilio/Z-API)"""
    return {
        "status": "QUEUED",
        "to": WHATSAPP_NUMBER,
        "message": f"NEXUS TRADE: {ticker} — {message}",
        "note": "WhatsApp API não configurada. Mensagem logada.",
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# TOOL 14 — Polymarket (mercados de previsão)
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def get_predictions(topic: str = "brazil economy") -> dict:
    """Busca probabilidades de mercados de previsão (Polymarket)"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://gamma-api.polymarket.com/markets",
                params={"limit": 5, "active": True, "tag": topic}
            )
            markets = r.json()
            return {
                "topic": topic,
                "markets": [
                    {"question": m.get("question", ""), "probability": m.get("outcomePrices", "[]")}
                    for m in (markets if isinstance(markets, list) else [])
                ][:5],
                "source": "POLYMARKET"
            }
    except Exception as e:
        return {"error": str(e), "topic": topic}


# ══════════════════════════════════════════════════════════════
# TOOL 15 — Status do servidor
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def server_status() -> dict:
    """Retorna status do servidor e configurações ativas"""
    status = {
        "status": "OK",
        "version": "3.5.0",
        "name": "Nexus Trade Pro",
        "tools_count": 25,
        "features": [
            "ADX", "Stochastic", "ATR", "VWAP", "OBV",
            "Trailing Stop", "Position Sizing", "Sentiment Analysis",
            "Score Composto Melhorado", "Risk Manager",
            "Data Providers (Yahoo Finance)", "Multi-Timeframe Analysis",
            "Advanced Filters", "Ensemble Model"
        ],
        "modules": {
            "data_providers": DATA_PROVIDERS_AVAILABLE,
            "multi_timeframe": MTF_AVAILABLE,
            "advanced_filters": FILTERS_AVAILABLE,
            "ensemble_model": ENSEMBLE_AVAILABLE,
            "risk_manager": RISK_MANAGER_AVAILABLE
        },
        "brapi_configured": bool(BRAPI_TOKEN),
        "tavily_configured": bool(TAVILY_KEY),
        "whatsapp": WHATSAPP_NUMBER,
        "timestamp": datetime.now().isoformat()
    }
    return status


# ══════════════════════════════════════════════════════════════
# TOOL 16 — Análise completa de ativo
# ══════════════════════════════════════════════════════════════
@mcp.tool()
async def full_analysis(ticker: str) -> dict:
    """Análise completa: cotação + indicadores + avançados + score + notícias"""
    quote = await get_quote(ticker)
    indicators = await calc_indicators(ticker)
    advanced = await calc_advanced_indicators(ticker)
    score = await calc_score(ticker)
    news = await search_news(ticker, 3)

    return {
        "ticker": ticker,
        "quote": quote,
        "indicators": indicators,
        "advanced": advanced if "error" not in advanced else None,
        "score": score,
        "news": news,
        "timestamp": datetime.now().isoformat()
    }


# ══════════════════════════════════════════════════════════════
# REST API endpoints (para o dashboard HTML)
# ══════════════════════════════════════════════════════════════
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Nexus Trade Pro API v2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/status")
async def api_status():
    return await server_status()

@app.get("/api/quote/{ticker}")
async def api_quote(ticker: str):
    return await get_quote(ticker.upper())

@app.get("/api/quotes")
async def api_quotes(tickers: str = "PETR4,VALE3,ITUB4"):
    return await get_quotes_batch(tickers)

@app.get("/api/history/{ticker}")
async def api_history(ticker: str, days: int = 30):
    return await get_history(ticker.upper(), days)

@app.get("/api/indicators/{ticker}")
async def api_indicators(ticker: str):
    return await calc_indicators(ticker.upper())

@app.get("/api/advanced/{ticker}")
async def api_advanced(ticker: str):
    return await calc_advanced_indicators(ticker.upper())

@app.get("/api/score/{ticker}")
async def api_score(ticker: str, peso_rsi: float = 0.06, peso_macd: float = 1.19, peso_bb: float = 0.09, peso_adx: float = 2.45, peso_stoch: float = 2.66, peso_volume: float = 2.05, peso_news: float = 1.07):
    """Score v3.0 TURBO (1848 trades, GA+SA+PSO) | WR: 60.1% | PF: 2.28"""
    return await calc_score(ticker.upper(), peso_rsi, peso_macd, peso_bb, peso_adx, peso_stoch, peso_volume, peso_news)

@app.get("/api/training-results")
async def api_training_results():
    """Retorna resultados do ultimo treinamento"""
    import os
    training_file = os.path.join(os.path.dirname(__file__), "training_results.json")
    if os.path.exists(training_file):
        with open(training_file, "r") as f:
            return json.load(f)
    return {
        "training_date": None,
        "results": {
            "total_trades": 0,
            "win_rate": 0,
            "optimized_weights": {
                "rsi": 0.6, "macd": 1.0, "bb": 1.0, "adx": 1.5,
                "stoch": 1.0, "volume": 0.7, "news": 0.5
            },
            "insights": ["Nenhum treinamento realizado ainda"]
        }
    }

@app.get("/api/sentiment")
async def api_sentiment(text: str):
    return await analyze_sentiment(text)

@app.get("/api/position-size/{ticker}")
async def api_position_size(ticker: str, capital: float = 10000, risk_percent: float = 2.0, stop_loss_percent: float = 3.0):
    return await calc_position_size(ticker.upper(), capital, risk_percent, stop_loss_percent)

@app.get("/api/trailing-stop/{ticker}")
async def api_trailing_stop(ticker: str, entry_price: float, current_price: float = 0, method: str = "atr", atr_multiplier: float = 2.0, percent: float = 3.0):
    return await get_trailing_stop(ticker.upper(), entry_price, current_price, method, atr_multiplier, percent)

@app.get("/api/news")
async def api_news(q: str = "mercado financeiro"):
    return await search_news(q)

@app.get("/api/scan")
async def api_scan(category: str = "acoes"):
    return await scan_market(category)

@app.get("/api/analysis/{ticker}")
async def api_analysis(ticker: str):
    return await full_analysis(ticker.upper())

@app.get("/api/trade")
async def api_trade(ticker: str, action: str = "COMPRAR", qty: int = 1):
    return await simulate_trade(ticker.upper(), action, qty)


# ══════════════════════════════════════════════════════════════
# RISK MANAGER - Controle de Drawdown e Risco
# ══════════════════════════════════════════════════════════════
try:
    from risk_manager import (
        risk_manager,
        RiskConfig,
        can_trade as risk_can_trade,
        get_position_size as risk_get_position_size,
        register_trade as risk_register_trade,
        get_status as risk_get_status,
        update_capital as risk_update_capital,
        reset as risk_reset,
        force_unblock as risk_force_unblock
    )
    RISK_MANAGER_AVAILABLE = True
    print("[OK] Risk Manager carregado")
except ImportError as e:
    RISK_MANAGER_AVAILABLE = False
    print(f"[X] Risk Manager nao disponivel: {e}")


# ══════════════════════════════════════════════════════════════
# TRADING REAL - Integracao com Corretoras
# ══════════════════════════════════════════════════════════════
try:
    from broker_integration import (
        connect as broker_connect,
        disconnect as broker_disconnect,
        get_balance as broker_balance,
        get_positions as broker_positions,
        buy as broker_buy,
        sell as broker_sell,
        close_position as broker_close,
        TRADING_MODE, MAX_ORDER_VALUE, DAILY_LOSS_LIMIT
    )
    BROKER_AVAILABLE = True
except ImportError:
    BROKER_AVAILABLE = False
    TRADING_MODE = "PAPER"


@app.get("/api/broker/status")
async def api_broker_status():
    """Status da conexao com corretora"""
    if not BROKER_AVAILABLE:
        return {"error": "Modulo broker nao disponivel", "mode": "PAPER"}

    return {
        "available": BROKER_AVAILABLE,
        "mode": TRADING_MODE,
        "max_order_value": MAX_ORDER_VALUE,
        "daily_loss_limit": DAILY_LOSS_LIMIT
    }


@app.get("/api/broker/connect")
async def api_broker_connect():
    """Conectar a corretora"""
    if not BROKER_AVAILABLE:
        return {"error": "Modulo broker nao disponivel"}

    if broker_connect():
        return {"success": True, "message": "Conectado", "mode": TRADING_MODE}
    return {"error": "Falha na conexao"}


@app.get("/api/broker/disconnect")
async def api_broker_disconnect():
    """Desconectar da corretora"""
    if not BROKER_AVAILABLE:
        return {"error": "Modulo broker nao disponivel"}

    broker_disconnect()
    return {"success": True, "message": "Desconectado"}


@app.get("/api/broker/balance")
async def api_broker_balance():
    """Obter saldo da corretora"""
    if not BROKER_AVAILABLE:
        return {"error": "Modulo broker nao disponivel"}

    return broker_balance()


@app.get("/api/broker/positions")
async def api_broker_positions():
    """Listar posicoes abertas"""
    if not BROKER_AVAILABLE:
        return {"error": "Modulo broker nao disponivel"}

    return {"positions": broker_positions()}


@app.post("/api/broker/buy")
async def api_broker_buy(ticker: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0):
    """Executar ordem de compra"""
    if not BROKER_AVAILABLE:
        return {"error": "Modulo broker nao disponivel"}

    # Validar antes de executar
    if price > 0:
        order_value = price * quantity
        if order_value > MAX_ORDER_VALUE:
            return {"error": f"Valor R$ {order_value:.2f} excede limite de R$ {MAX_ORDER_VALUE}"}

    return broker_buy(ticker.upper(), quantity, price, stop_loss, take_profit)


@app.post("/api/broker/sell")
async def api_broker_sell(ticker: str, quantity: int, price: float = 0, stop_loss: float = 0, take_profit: float = 0):
    """Executar ordem de venda"""
    if not BROKER_AVAILABLE:
        return {"error": "Modulo broker nao disponivel"}

    return broker_sell(ticker.upper(), quantity, price, stop_loss, take_profit)


@app.post("/api/broker/close/{position_id}")
async def api_broker_close(position_id: int):
    """Fechar posicao"""
    if not BROKER_AVAILABLE:
        return {"error": "Modulo broker nao disponivel"}

    return broker_close(position_id)


@app.post("/api/broker/execute")
async def api_broker_execute(ticker: str, action: str = "BUY", quantity: int = 100):
    """Executar operacao baseada no score do ativo COM CONTROLE DE RISCO"""
    if not BROKER_AVAILABLE:
        return {"error": "Modulo broker nao disponivel"}

    # Obter cotacao e score
    quote = await get_quote(ticker.upper())
    if "error" in quote:
        return quote

    score_data = await calc_score(ticker.upper())
    price = quote.get("price", 0)
    score = score_data.get("score", 0)
    confidence = score_data.get("confidence", 0)

    # === VERIFICAR RISK MANAGER ===
    if RISK_MANAGER_AVAILABLE:
        # Obter volatilidade (ATR%)
        adv = await calc_advanced_indicators(ticker.upper())
        volatility = adv.get("atr", {}).get("percent", 0) if "error" not in adv else 0

        # Verificar se pode operar
        can_trade, reason, risk_details = risk_can_trade(
            order_value=price * quantity,
            confidence=confidence,
            score=abs(score),
            volatility=volatility
        )

        if not can_trade:
            return {
                "error": f"Operacao bloqueada pelo Risk Manager",
                "reason": reason,
                "risk_status": risk_details,
                "ticker": ticker.upper(),
                "score": score,
                "confidence": confidence
            }

        # Ajustar quantidade baseado no multiplicador de risco
        multiplier = risk_details.get("position_multiplier", 1.0)
        adjusted_quantity = max(1, int(quantity * multiplier))

        if adjusted_quantity != quantity:
            print(f"[RiskManager] Quantidade ajustada: {quantity} -> {adjusted_quantity} (mult: {multiplier})")
            quantity = adjusted_quantity

    # Conectar se nao estiver conectado
    broker_connect()

    if action.upper() == "BUY":
        result = broker_buy(ticker.upper(), quantity, price)
    else:
        result = broker_sell(ticker.upper(), quantity, price)

    # Registrar trade no Risk Manager
    if RISK_MANAGER_AVAILABLE and result.get("success"):
        risk_register_trade(
            ticker=ticker.upper(),
            action=action.upper(),
            quantity=quantity,
            entry_price=price
        )

    result["quote"] = quote
    result["score"] = score
    result["signal"] = score_data.get("signal")
    result["risk_adjusted_quantity"] = quantity

    return result


# ══════════════════════════════════════════════════════════════
# RISK MANAGER - API Endpoints
# ══════════════════════════════════════════════════════════════

@app.get("/api/risk/status")
async def api_risk_status():
    """Retorna status completo do Risk Manager"""
    if not RISK_MANAGER_AVAILABLE:
        return {"error": "Risk Manager nao disponivel", "available": False}

    return risk_get_status()


@app.get("/api/risk/can-trade")
async def api_risk_can_trade(
    order_value: float = 0,
    confidence: float = 100,
    score: float = 100,
    volatility: float = 0
):
    """Verifica se pode executar trade"""
    if not RISK_MANAGER_AVAILABLE:
        return {"can_trade": True, "reason": "Risk Manager nao disponivel"}

    can_trade, reason, details = risk_can_trade(order_value, confidence, score, volatility)
    return {
        "can_trade": can_trade,
        "reason": reason,
        "details": details
    }


@app.get("/api/risk/position-size/{ticker}")
async def api_risk_position_size(
    ticker: str,
    stop_loss_percent: float = 3.0,
    win_rate: float = 0.60,
    avg_win_loss_ratio: float = 1.5
):
    """Calcula tamanho ideal da posicao com controle de risco"""
    if not RISK_MANAGER_AVAILABLE:
        return {"error": "Risk Manager nao disponivel"}

    # Obter preco atual
    quote = await get_quote(ticker.upper())
    if "error" in quote:
        return quote

    price = quote.get("price", 0)
    if price <= 0:
        return {"error": "Preco invalido"}

    # Calcular position size
    result = risk_manager.calculate_position_size(
        price=price,
        stop_loss_percent=stop_loss_percent,
        win_rate=win_rate,
        avg_win_loss_ratio=avg_win_loss_ratio
    )

    result["ticker"] = ticker.upper()
    result["quote"] = quote
    return result


@app.post("/api/risk/register-trade")
async def api_risk_register_trade(
    ticker: str,
    action: str,
    quantity: int,
    entry_price: float,
    exit_price: float = 0,
    pnl: float = 0
):
    """Registra um trade no Risk Manager"""
    if not RISK_MANAGER_AVAILABLE:
        return {"error": "Risk Manager nao disponivel"}

    trade = risk_register_trade(
        ticker=ticker.upper(),
        action=action.upper(),
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl=pnl
    )
    return {"success": True, "trade": trade, "status": risk_get_status()}


@app.post("/api/risk/close-trade")
async def api_risk_close_trade(
    ticker: str,
    action: str,
    quantity: int,
    entry_price: float,
    exit_price: float
):
    """Fecha um trade e atualiza o Risk Manager"""
    if not RISK_MANAGER_AVAILABLE:
        return {"error": "Risk Manager nao disponivel"}

    trade = risk_register_trade(
        ticker=ticker.upper(),
        action=action.upper(),
        quantity=quantity,
        entry_price=entry_price,
        exit_price=exit_price
    )
    return {"success": True, "trade": trade, "status": risk_get_status()}


@app.post("/api/risk/update-capital")
async def api_risk_update_capital(capital: float):
    """Atualiza o capital atual"""
    if not RISK_MANAGER_AVAILABLE:
        return {"error": "Risk Manager nao disponivel"}

    risk_update_capital(capital)
    return {"success": True, "status": risk_get_status()}


@app.post("/api/risk/reset")
async def api_risk_reset(initial_capital: float = 500.0):
    """Reseta o Risk Manager"""
    if not RISK_MANAGER_AVAILABLE:
        return {"error": "Risk Manager nao disponivel"}

    risk_reset(initial_capital)
    return {"success": True, "message": f"Risk Manager resetado com capital R$ {initial_capital:.2f}"}


@app.post("/api/risk/unblock")
async def api_risk_unblock():
    """Forca desbloqueio do Risk Manager (usar com cuidado!)"""
    if not RISK_MANAGER_AVAILABLE:
        return {"error": "Risk Manager nao disponivel"}

    risk_force_unblock()
    return {"success": True, "message": "Risk Manager desbloqueado", "status": risk_get_status()}


@app.get("/api/risk/check-trade/{ticker}")
async def api_risk_check_trade(ticker: str, quantity: int = 100):
    """Verifica se um trade especifico pode ser executado"""
    if not RISK_MANAGER_AVAILABLE:
        return {"can_trade": True, "reason": "Risk Manager nao disponivel"}

    # Obter dados do ativo
    quote = await get_quote(ticker.upper())
    if "error" in quote:
        return quote

    score_data = await calc_score(ticker.upper())
    adv = await calc_advanced_indicators(ticker.upper())

    price = quote.get("price", 0)
    score = score_data.get("score", 0)
    confidence = score_data.get("confidence", 0)
    volatility = adv.get("atr", {}).get("percent", 0) if "error" not in adv else 0
    order_value = price * quantity

    # Verificar
    can_trade, reason, details = risk_can_trade(order_value, confidence, abs(score), volatility)

    # Calcular position size recomendado
    position_size = risk_manager.calculate_position_size(price, stop_loss_percent=3.0)

    return {
        "ticker": ticker.upper(),
        "can_trade": can_trade,
        "reason": reason,
        "details": details,
        "quote": quote,
        "score": score,
        "confidence": confidence,
        "volatility_atr_percent": volatility,
        "order_value": order_value,
        "recommended_position": position_size.get("recommended", {}),
        "risk_status": risk_get_status()
    }


# ══════════════════════════════════════════════════════════════
# DATA PROVIDERS - API Endpoints
# ══════════════════════════════════════════════════════════════

@app.get("/api/providers/status")
async def api_providers_status():
    """Status dos provedores de dados"""
    if not DATA_PROVIDERS_AVAILABLE:
        return {"error": "Data Providers nao disponiveis", "available": False}
    return get_provider_stats()


@app.get("/api/providers/quote/{ticker}")
async def api_providers_quote(ticker: str):
    """Busca cotacao via Data Providers (Yahoo Finance prioritario)"""
    if not DATA_PROVIDERS_AVAILABLE:
        return await get_quote(ticker.upper())
    return await dp_get_quote(ticker.upper())


@app.get("/api/providers/history/{ticker}")
async def api_providers_history(ticker: str, days: int = 30):
    """Busca historico via Data Providers"""
    if not DATA_PROVIDERS_AVAILABLE:
        return await get_history(ticker.upper(), days)
    return await dp_get_history(ticker.upper(), days)


# ══════════════════════════════════════════════════════════════
# MULTI-TIMEFRAME - API Endpoints
# ══════════════════════════════════════════════════════════════

@app.get("/api/mtf/{ticker}")
async def api_mtf_analysis(ticker: str):
    """Analise Multi-Timeframe"""
    if not MTF_AVAILABLE:
        return {"error": "Multi-Timeframe nao disponivel", "available": False}

    # Buscar historico
    hist = await get_history(ticker.upper(), 60)
    if "error" in hist:
        return hist

    prices = [d.get("close", 0) for d in hist.get("data", []) if d.get("close")]
    if len(prices) < 20:
        return {"error": "Dados insuficientes para MTF"}

    # Analise rapida
    result = quick_mtf_analysis(prices, ticker.upper())
    return result


@app.get("/api/mtf/recommendation/{ticker}")
async def api_mtf_recommendation(ticker: str):
    """Recomendacao baseada em Multi-Timeframe"""
    if not MTF_AVAILABLE:
        return {"error": "Multi-Timeframe nao disponivel"}

    # Buscar historico
    hist = await get_history(ticker.upper(), 60)
    if "error" in hist:
        return hist

    prices = [d.get("close", 0) for d in hist.get("data", []) if d.get("close")]
    if len(prices) < 20:
        return {"error": "Dados insuficientes"}

    # Analise
    result = quick_mtf_analysis(prices, ticker.upper())

    # Resumo simplificado
    return {
        "ticker": ticker.upper(),
        "trend": result.get("primary_trend"),
        "alignment": result.get("alignment"),
        "recommendation": result.get("recommendation"),
        "confidence": result.get("confidence"),
        "entry_zone": result.get("entry_zone"),
        "stop_loss": result.get("stop_loss"),
        "take_profit": result.get("take_profit")
    }


# ══════════════════════════════════════════════════════════════
# ADVANCED FILTERS - API Endpoints
# ══════════════════════════════════════════════════════════════

@app.get("/api/filters/{ticker}")
async def api_filters_check(ticker: str, direction: str = "LONG"):
    """Executa todos os filtros para um ativo"""
    if not FILTERS_AVAILABLE:
        return {"error": "Advanced Filters nao disponiveis", "available": False}

    # Buscar dados
    quote = await get_quote(ticker.upper())
    hist = await get_history(ticker.upper(), 30)

    if "error" in quote or "error" in hist:
        return {"error": "Falha ao obter dados"}

    prices = [d.get("close", 0) for d in hist.get("data", []) if d.get("close")]
    volume = quote.get("volume", 5000000)

    # Executar filtros
    result = check_filters(
        prices=prices,
        volume=volume,
        avg_volume=volume,  # Simplificado
        direction=direction.upper()
    )

    result["ticker"] = ticker.upper()
    result["quote"] = quote
    return result


@app.get("/api/filters/regime/{ticker}")
async def api_filters_regime(ticker: str):
    """Detecta regime de mercado"""
    if not FILTERS_AVAILABLE:
        return {"error": "Advanced Filters nao disponiveis"}

    hist = await get_history(ticker.upper(), 30)
    if "error" in hist:
        return hist

    prices = [d.get("close", 0) for d in hist.get("data", []) if d.get("close")]
    if len(prices) < 10:
        return {"error": "Dados insuficientes"}

    regime = detect_regime(prices)
    regime["ticker"] = ticker.upper()
    return regime


@app.get("/api/filters/time-check")
async def api_filters_time():
    """Verifica se e um bom horario para operar"""
    if not FILTERS_AVAILABLE:
        return {"error": "Advanced Filters nao disponiveis"}

    return is_good_time_to_trade()


# ══════════════════════════════════════════════════════════════
# ENSEMBLE MODEL - API Endpoints
# ══════════════════════════════════════════════════════════════

@app.get("/api/ensemble/{ticker}")
async def api_ensemble_predict(ticker: str):
    """Previsao do Ensemble de Modelos"""
    if not ENSEMBLE_AVAILABLE:
        return {"error": "Ensemble Model nao disponivel", "available": False}

    # Buscar indicadores
    quote = await get_quote(ticker.upper())
    ind = await calc_indicators(ticker.upper())
    adv = await calc_advanced_indicators(ticker.upper())

    if "error" in quote:
        return quote

    # Montar dicionario de indicadores
    indicators = {
        "price": quote.get("price", 0),
        "rsi": ind.get("rsi", 50) if "error" not in ind else 50,
        "macd_histogram": ind.get("macd", {}).get("histogram", 0) if "error" not in ind else 0,
        "ema9": ind.get("ema9", 0) if "error" not in ind else 0,
        "ema21": ind.get("ema21", 0) if "error" not in ind else 0,
        "bb_upper": ind.get("bollinger", {}).get("upper", 0) if "error" not in ind else 0,
        "bb_lower": ind.get("bollinger", {}).get("lower", 0) if "error" not in ind else 0,
        "bb_middle": ind.get("bollinger", {}).get("middle", 0) if "error" not in ind else 0,
    }

    if "error" not in adv:
        indicators.update({
            "adx": adv.get("adx", {}).get("value", 0),
            "plus_di": adv.get("adx", {}).get("plus_di", 0),
            "minus_di": adv.get("adx", {}).get("minus_di", 0),
            "stoch_k": adv.get("stochastic", {}).get("k", 50),
            "obv_trend": adv.get("obv", {}).get("trend", "NEUTRO"),
            "vwap_position": adv.get("vwap", {}).get("position", "NEUTRO"),
        })

    # Previsao do ensemble
    result = ensemble_predict(indicators)
    result["ticker"] = ticker.upper()
    result["quote"] = quote

    return result


@app.get("/api/ensemble/performance")
async def api_ensemble_performance():
    """Performance do Ensemble"""
    if not ENSEMBLE_AVAILABLE:
        return {"error": "Ensemble Model nao disponivel"}

    return get_ensemble_performance()


@app.get("/api/ensemble/weights")
async def api_ensemble_weights():
    """Pesos combinados otimos do Ensemble"""
    if not ENSEMBLE_AVAILABLE:
        return {"error": "Ensemble Model nao disponivel"}

    return {
        "combined_weights": get_combined_weights(),
        "model_performance": get_ensemble_performance()
    }


# ══════════════════════════════════════════════════════════════
# ANALISE COMPLETA v2 - Combina todos os modulos
# ══════════════════════════════════════════════════════════════

@app.get("/api/analysis-pro/{ticker}")
async def api_full_analysis_pro(ticker: str, direction: str = "LONG"):
    """
    Analise completa PRO combinando todos os modulos:
    - Cotacao e indicadores
    - Multi-Timeframe
    - Filtros avancados
    - Ensemble
    - Risk Manager
    """
    ticker = ticker.upper()

    # Dados base
    quote = await get_quote(ticker)
    if "error" in quote:
        return quote

    ind = await calc_indicators(ticker)
    adv = await calc_advanced_indicators(ticker)
    score_data = await calc_score(ticker)
    hist = await get_history(ticker, 60)

    prices = [d.get("close", 0) for d in hist.get("data", []) if d.get("close")] if "error" not in hist else []

    result = {
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "quote": quote,
        "indicators": ind if "error" not in ind else None,
        "advanced": adv if "error" not in adv else None,
        "score": score_data
    }

    # Multi-Timeframe
    if MTF_AVAILABLE and len(prices) >= 20:
        result["mtf"] = quick_mtf_analysis(prices, ticker)
    else:
        result["mtf"] = None

    # Filtros
    if FILTERS_AVAILABLE and len(prices) >= 10:
        result["filters"] = check_filters(
            prices=prices,
            volume=quote.get("volume", 5000000),
            avg_volume=quote.get("volume", 5000000),
            direction=direction.upper()
        )
    else:
        result["filters"] = None

    # Ensemble
    if ENSEMBLE_AVAILABLE:
        indicators = {
            "price": quote.get("price", 0),
            "rsi": ind.get("rsi", 50) if "error" not in ind else 50,
            "macd_histogram": ind.get("macd", {}).get("histogram", 0) if "error" not in ind else 0,
            "ema9": ind.get("ema9", 0) if "error" not in ind else 0,
            "ema21": ind.get("ema21", 0) if "error" not in ind else 0,
            "bb_upper": ind.get("bollinger", {}).get("upper", 0) if "error" not in ind else 0,
            "bb_lower": ind.get("bollinger", {}).get("lower", 0) if "error" not in ind else 0,
            "bb_middle": ind.get("bollinger", {}).get("middle", 0) if "error" not in ind else 0,
        }
        if "error" not in adv:
            indicators.update({
                "adx": adv.get("adx", {}).get("value", 0),
                "plus_di": adv.get("adx", {}).get("plus_di", 0),
                "minus_di": adv.get("adx", {}).get("minus_di", 0),
                "stoch_k": adv.get("stochastic", {}).get("k", 50),
                "obv_trend": adv.get("obv", {}).get("trend", "NEUTRO"),
                "vwap_position": adv.get("vwap", {}).get("position", "NEUTRO"),
            })
        result["ensemble"] = ensemble_predict(indicators)
    else:
        result["ensemble"] = None

    # Risk Manager
    if RISK_MANAGER_AVAILABLE:
        result["risk"] = risk_get_status()
    else:
        result["risk"] = None

    # Recomendacao final
    can_trade = True
    reasons = []

    # Check filtros
    if result["filters"] and not result["filters"].get("can_trade", True):
        can_trade = False
        reasons.append(result["filters"].get("summary", "Filtros bloquearam"))

    # Check risk
    if result["risk"] and result["risk"].get("status") == "BLOCKED":
        can_trade = False
        reasons.append(f"Risk Manager: {result['risk'].get('block_reason', 'Bloqueado')}")

    # Determinar sinal final
    signals = []
    if result["score"]:
        signals.append(result["score"].get("signal", "NEUTRO"))
    if result["mtf"]:
        signals.append(result["mtf"].get("recommendation", "NEUTRO"))
    if result["ensemble"]:
        signals.append(result["ensemble"].get("signal", "NEUTRO"))

    # Votacao simples
    buy_count = sum(1 for s in signals if "COMPRA" in str(s) or "BUY" in str(s))
    sell_count = sum(1 for s in signals if "VENDA" in str(s) or "SELL" in str(s))

    if buy_count > sell_count and can_trade:
        final_signal = "COMPRA"
    elif sell_count > buy_count and can_trade:
        final_signal = "VENDA"
    else:
        final_signal = "AGUARDAR"

    result["final_recommendation"] = {
        "signal": final_signal,
        "can_trade": can_trade,
        "reasons": reasons if reasons else ["Analise completa OK"],
        "signals_breakdown": signals
    }

    return result


# ══════════════════════════════════════════════════════════════
# AUTO TRADER - Sincronizacao com Dashboard
# ══════════════════════════════════════════════════════════════

@app.get("/api/autotrader/trades")
async def api_autotrader_trades():
    """Retorna trades do forward test para sincronizar com dashboard"""
    log_file = os.path.join(os.path.dirname(__file__), "..", "data", "forward_test_log.json")
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"signals": [], "trades": [], "stats": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0, "pnl": 0}}

@app.get("/api/autotrader/status")
async def api_autotrader_status():
    """Retorna status completo do auto trader"""
    log_file = os.path.join(os.path.dirname(__file__), "..", "data", "forward_test_log.json")
    risk_file = os.path.join(os.path.dirname(__file__), "..", "data", "risk_state.json")

    result = {
        "running": True,
        "mode": "forward_test",
        "trades": [],
        "positions": [],
        "stats": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0, "pnl": 0},
        "capital": {"initial": 500, "current": 500}
    }

    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            result["trades"] = data.get("trades", [])
            result["positions"] = [t for t in data.get("trades", []) if t.get("status") == "OPEN"]
            result["stats"] = data.get("stats", result["stats"])

    if os.path.exists(risk_file):
        with open(risk_file, "r", encoding="utf-8") as f:
            risk = json.load(f)
            result["capital"] = {
                "initial": risk.get("initial_capital", 500),
                "current": risk.get("current_capital", 500)
            }
            result["stats"]["total"] = risk.get("total_trades", 0)
            result["stats"]["wins"] = risk.get("total_wins", 0)
            result["stats"]["losses"] = risk.get("total_losses", 0)
            result["stats"]["win_rate"] = risk.get("win_rate", 0)
            result["stats"]["pnl"] = risk.get("total_pnl", 0)

    return result


# ══════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "http":
        import uvicorn
        print("=" * 60)
        print("  NEXUS TRADE PRO v3.5 - Servidor HTTP")
        print("=" * 60)
        print("  Modulos:")
        print(f"    Data Providers:  {'[OK]' if DATA_PROVIDERS_AVAILABLE else '[X]'}")
        print(f"    Multi-Timeframe: {'[OK]' if MTF_AVAILABLE else '[X]'}")
        print(f"    Advanced Filters:{'[OK]' if FILTERS_AVAILABLE else '[X]'}")
        print(f"    Ensemble Model:  {'[OK]' if ENSEMBLE_AVAILABLE else '[X]'}")
        print(f"    Risk Manager:    {'[OK]' if RISK_MANAGER_AVAILABLE else '[X]'}")
        print("=" * 60)
        print(f"  brapi.dev: {'[OK]' if BRAPI_TOKEN else '[X]'}")
        print(f"  Tavily:    {'[OK]' if TAVILY_KEY else '[X]'}")
        print("=" * 60)
        if RISK_MANAGER_AVAILABLE:
            status = risk_get_status()
            print(f"  Capital:   R$ {status['capital']['current']:.2f}")
            print(f"  Drawdown:  {status['drawdown']['current']:.1f}%")
            print(f"  Status:    {status['status']}")
            print("=" * 60)
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("Iniciando FastMCP server...")
        mcp.run()

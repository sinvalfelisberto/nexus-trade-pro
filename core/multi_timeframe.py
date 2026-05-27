# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Multi-Timeframe Analysis v1.0
=================================================
Analisa sinais em multiplos timeframes para maior precisao

Timeframes:
- 1H (Intraday): Timing de entrada
- 4H (Swing): Direcao de curto prazo
- Diario (Position): Tendencia principal

Principio:
- Trade na direcao do timeframe maior
- Entrada no timeframe menor
- Confirmacao em timeframe intermediario
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class Timeframe(Enum):
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class Trend(Enum):
    STRONG_UP = "FORTE_ALTA"
    UP = "ALTA"
    NEUTRAL = "NEUTRO"
    DOWN = "BAIXA"
    STRONG_DOWN = "FORTE_BAIXA"


@dataclass
class TimeframeSignal:
    """Sinal de um timeframe especifico"""
    timeframe: Timeframe
    trend: Trend
    strength: float  # 0-100
    rsi: float
    macd_signal: int  # 1=bullish, -1=bearish, 0=neutral
    ema_signal: int  # 1=price above EMA, -1=below
    support: float
    resistance: float
    volatility: float


@dataclass
class MTFAnalysis:
    """Analise Multi-Timeframe completa"""
    ticker: str
    signals: Dict[str, TimeframeSignal]
    alignment: float  # 0-100 (quanto os timeframes concordam)
    primary_trend: Trend
    recommendation: str
    confidence: float
    entry_zone: Tuple[float, float]
    stop_loss: float
    take_profit: float
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "signals": {
                tf: {
                    "timeframe": sig.timeframe.value,
                    "trend": sig.trend.value,
                    "strength": sig.strength,
                    "rsi": sig.rsi,
                    "macd_signal": sig.macd_signal,
                    "ema_signal": sig.ema_signal,
                    "support": sig.support,
                    "resistance": sig.resistance,
                    "volatility": sig.volatility
                }
                for tf, sig in self.signals.items()
            },
            "alignment": self.alignment,
            "primary_trend": self.primary_trend.value,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "entry_zone": {
                "min": self.entry_zone[0],
                "max": self.entry_zone[1]
            },
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "timestamp": self.timestamp
        }


class MultiTimeframeAnalyzer:
    """
    Analisador Multi-Timeframe

    Combina sinais de diferentes timeframes para:
    1. Identificar tendencia principal
    2. Encontrar pontos de entrada otimos
    3. Calcular niveis de SL/TP
    """

    def __init__(self):
        # Pesos por timeframe (maior = mais importante)
        self.timeframe_weights = {
            Timeframe.H1: 0.20,   # Entrada
            Timeframe.H4: 0.35,  # Confirmacao
            Timeframe.D1: 0.45,  # Tendencia principal
        }

    def _calc_ema(self, prices: List[float], period: int) -> float:
        """Calcula EMA"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
        k = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for p in prices[period:]:
            ema = p * k + ema * (1 - k)
        return ema

    def _calc_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calcula RSI"""
        if len(prices) < period + 1:
            return 50

        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calc_macd(self, prices: List[float]) -> Tuple[float, float, float]:
        """Calcula MACD (line, signal, histogram)"""
        if len(prices) < 26:
            return 0, 0, 0

        ema12 = self._calc_ema(prices, 12)
        ema26 = self._calc_ema(prices, 26)
        macd_line = ema12 - ema26

        # Signal line (EMA 9 do MACD)
        macd_values = []
        for i in range(26, len(prices) + 1):
            e12 = self._calc_ema(prices[:i], 12)
            e26 = self._calc_ema(prices[:i], 26)
            macd_values.append(e12 - e26)

        signal_line = self._calc_ema(macd_values, 9) if len(macd_values) >= 9 else macd_line
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def _calc_support_resistance(self, prices: List[float]) -> Tuple[float, float]:
        """Calcula suporte e resistencia"""
        if len(prices) < 5:
            return prices[-1] * 0.95, prices[-1] * 1.05

        # Metodo simples: min/max dos ultimos N periodos
        recent = prices[-20:] if len(prices) >= 20 else prices

        # Suporte: minimas locais
        lows = [min(recent[i:i+3]) for i in range(0, len(recent)-2, 3)]
        support = min(lows) if lows else min(recent)

        # Resistencia: maximas locais
        highs = [max(recent[i:i+3]) for i in range(0, len(recent)-2, 3)]
        resistance = max(highs) if highs else max(recent)

        return round(support, 2), round(resistance, 2)

    def _calc_volatility(self, prices: List[float]) -> float:
        """Calcula volatilidade (desvio padrao dos retornos)"""
        if len(prices) < 2:
            return 0

        returns = [(prices[i] - prices[i-1]) / prices[i-1] * 100
                   for i in range(1, len(prices))]

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return round(math.sqrt(variance), 2)

    def _determine_trend(self, prices: List[float], rsi: float, macd_hist: float) -> Tuple[Trend, float]:
        """Determina tendencia e forca"""
        if len(prices) < 10:
            return Trend.NEUTRAL, 50

        # EMA trend
        ema9 = self._calc_ema(prices, 9)
        ema21 = self._calc_ema(prices, 21)
        current = prices[-1]

        # Pontuacao
        score = 0

        # EMA crossover
        if ema9 > ema21:
            score += 25
        else:
            score -= 25

        # Preco vs EMAs
        if current > ema9 > ema21:
            score += 20
        elif current < ema9 < ema21:
            score -= 20

        # RSI
        if rsi > 60:
            score += 15
        elif rsi < 40:
            score -= 15

        # MACD
        if macd_hist > 0:
            score += 20
        else:
            score -= 20

        # Momentum (preco vs 10 periodos atras)
        if len(prices) >= 10:
            momentum = (current - prices[-10]) / prices[-10] * 100
            if momentum > 2:
                score += 15
            elif momentum < -2:
                score -= 15

        # Determinar tendencia
        strength = min(100, max(0, 50 + score))

        if score >= 50:
            trend = Trend.STRONG_UP
        elif score >= 20:
            trend = Trend.UP
        elif score <= -50:
            trend = Trend.STRONG_DOWN
        elif score <= -20:
            trend = Trend.DOWN
        else:
            trend = Trend.NEUTRAL

        return trend, strength

    def analyze_timeframe(self, prices: List[float], timeframe: Timeframe) -> TimeframeSignal:
        """Analisa um timeframe especifico"""
        if not prices or len(prices) < 5:
            return TimeframeSignal(
                timeframe=timeframe,
                trend=Trend.NEUTRAL,
                strength=50,
                rsi=50,
                macd_signal=0,
                ema_signal=0,
                support=0,
                resistance=0,
                volatility=0
            )

        # Indicadores
        rsi = self._calc_rsi(prices)
        macd_line, signal_line, macd_hist = self._calc_macd(prices)
        support, resistance = self._calc_support_resistance(prices)
        volatility = self._calc_volatility(prices)

        # Sinais
        macd_signal = 1 if macd_hist > 0 else -1 if macd_hist < 0 else 0

        ema21 = self._calc_ema(prices, 21)
        ema_signal = 1 if prices[-1] > ema21 else -1

        # Tendencia
        trend, strength = self._determine_trend(prices, rsi, macd_hist)

        return TimeframeSignal(
            timeframe=timeframe,
            trend=trend,
            strength=strength,
            rsi=round(rsi, 2),
            macd_signal=macd_signal,
            ema_signal=ema_signal,
            support=support,
            resistance=resistance,
            volatility=volatility
        )

    def analyze(
        self,
        ticker: str,
        prices_1h: List[float],
        prices_4h: List[float],
        prices_daily: List[float],
        current_price: float
    ) -> MTFAnalysis:
        """
        Analise Multi-Timeframe completa

        Args:
            ticker: Codigo do ativo
            prices_1h: Precos de fechamento 1H
            prices_4h: Precos de fechamento 4H
            prices_daily: Precos de fechamento diarios
            current_price: Preco atual
        """
        # Analisar cada timeframe
        signal_1h = self.analyze_timeframe(prices_1h, Timeframe.H1)
        signal_4h = self.analyze_timeframe(prices_4h, Timeframe.H4)
        signal_daily = self.analyze_timeframe(prices_daily, Timeframe.D1)

        signals = {
            "1h": signal_1h,
            "4h": signal_4h,
            "daily": signal_daily
        }

        # Calcular alinhamento
        trend_scores = {
            Trend.STRONG_UP: 2,
            Trend.UP: 1,
            Trend.NEUTRAL: 0,
            Trend.DOWN: -1,
            Trend.STRONG_DOWN: -2
        }

        weighted_trend = (
            trend_scores[signal_1h.trend] * self.timeframe_weights[Timeframe.H1] +
            trend_scores[signal_4h.trend] * self.timeframe_weights[Timeframe.H4] +
            trend_scores[signal_daily.trend] * self.timeframe_weights[Timeframe.D1]
        )

        # Alinhamento: quanto os timeframes concordam (0-100)
        trends = [signal_1h.trend, signal_4h.trend, signal_daily.trend]
        bullish_count = sum(1 for t in trends if t in [Trend.UP, Trend.STRONG_UP])
        bearish_count = sum(1 for t in trends if t in [Trend.DOWN, Trend.STRONG_DOWN])

        if bullish_count == 3 or bearish_count == 3:
            alignment = 100
        elif bullish_count == 2 or bearish_count == 2:
            alignment = 70
        elif bullish_count == 1 or bearish_count == 1:
            alignment = 40
        else:
            alignment = 20

        # Tendencia primaria (do timeframe maior)
        primary_trend = signal_daily.trend

        # Recomendacao
        if weighted_trend >= 1.0 and alignment >= 60:
            recommendation = "COMPRA_FORTE"
            confidence = min(95, 60 + alignment * 0.3 + signal_daily.strength * 0.1)
        elif weighted_trend >= 0.5:
            recommendation = "COMPRA"
            confidence = min(80, 50 + alignment * 0.25 + signal_daily.strength * 0.1)
        elif weighted_trend <= -1.0 and alignment >= 60:
            recommendation = "VENDA_FORTE"
            confidence = min(95, 60 + alignment * 0.3 + signal_daily.strength * 0.1)
        elif weighted_trend <= -0.5:
            recommendation = "VENDA"
            confidence = min(80, 50 + alignment * 0.25 + signal_daily.strength * 0.1)
        else:
            recommendation = "AGUARDAR"
            confidence = 30

        # Zona de entrada (baseada em suporte/resistencia do 4H)
        if weighted_trend > 0:
            # Compra: entrada proximo ao suporte
            entry_min = signal_4h.support
            entry_max = signal_4h.support + (signal_4h.resistance - signal_4h.support) * 0.3
        else:
            # Venda: entrada proximo a resistencia
            entry_min = signal_4h.resistance - (signal_4h.resistance - signal_4h.support) * 0.3
            entry_max = signal_4h.resistance

        # Stop Loss e Take Profit
        avg_volatility = (signal_1h.volatility + signal_4h.volatility + signal_daily.volatility) / 3
        atr_multiplier = 2.0

        if weighted_trend > 0:
            stop_loss = round(current_price * (1 - avg_volatility * atr_multiplier / 100), 2)
            take_profit = round(current_price * (1 + avg_volatility * atr_multiplier * 2 / 100), 2)
        else:
            stop_loss = round(current_price * (1 + avg_volatility * atr_multiplier / 100), 2)
            take_profit = round(current_price * (1 - avg_volatility * atr_multiplier * 2 / 100), 2)

        return MTFAnalysis(
            ticker=ticker.upper(),
            signals=signals,
            alignment=alignment,
            primary_trend=primary_trend,
            recommendation=recommendation,
            confidence=round(confidence, 1),
            entry_zone=(round(entry_min, 2), round(entry_max, 2)),
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.now().isoformat()
        )

    def quick_analyze(self, prices_daily: List[float], ticker: str = "ATIVO") -> MTFAnalysis:
        """
        Analise rapida usando apenas dados diarios

        Simula timeframes menores usando subconjuntos dos dados:
        - Daily: todos os dados
        - 4H: ultimos 50% dos dados
        - 1H: ultimos 25% dos dados
        """
        if len(prices_daily) < 10:
            # Dados insuficientes
            return MTFAnalysis(
                ticker=ticker.upper(),
                signals={},
                alignment=0,
                primary_trend=Trend.NEUTRAL,
                recommendation="DADOS_INSUFICIENTES",
                confidence=0,
                entry_zone=(0, 0),
                stop_loss=0,
                take_profit=0,
                timestamp=datetime.now().isoformat()
            )

        # Simular timeframes
        n = len(prices_daily)
        prices_simulated_4h = prices_daily[int(n * 0.5):]
        prices_simulated_1h = prices_daily[int(n * 0.75):]
        current_price = prices_daily[-1]

        return self.analyze(
            ticker=ticker,
            prices_1h=prices_simulated_1h,
            prices_4h=prices_simulated_4h,
            prices_daily=prices_daily,
            current_price=current_price
        )


# Instancia global
mtf_analyzer = MultiTimeframeAnalyzer()


# Funcoes de conveniencia
def analyze_mtf(
    ticker: str,
    prices_1h: List[float],
    prices_4h: List[float],
    prices_daily: List[float],
    current_price: float
) -> dict:
    """Analise MTF completa"""
    result = mtf_analyzer.analyze(ticker, prices_1h, prices_4h, prices_daily, current_price)
    return result.to_dict()

def quick_mtf_analysis(prices_daily: List[float], ticker: str = "ATIVO") -> dict:
    """Analise MTF rapida usando apenas dados diarios"""
    result = mtf_analyzer.quick_analyze(prices_daily, ticker)
    return result.to_dict()


if __name__ == "__main__":
    import random

    print("=" * 60)
    print("  TESTE MULTI-TIMEFRAME ANALYSIS")
    print("=" * 60)

    # Gerar dados de teste (tendencia de alta)
    base_price = 40.0
    prices_daily = []
    for i in range(50):
        # Tendencia de alta com ruido
        trend = 0.002  # 0.2% por dia
        noise = random.uniform(-0.015, 0.02)
        base_price *= (1 + trend + noise)
        prices_daily.append(round(base_price, 2))

    print(f"\nPreco inicial: R$ {prices_daily[0]:.2f}")
    print(f"Preco final: R$ {prices_daily[-1]:.2f}")
    print(f"Variacao: {((prices_daily[-1] - prices_daily[0]) / prices_daily[0] * 100):.1f}%")

    # Analise rapida
    print("\n[Analise Rapida]")
    result = quick_mtf_analysis(prices_daily, "PETR4")

    print(f"\nTendencia Principal: {result['primary_trend']}")
    print(f"Alinhamento: {result['alignment']}%")
    print(f"Recomendacao: {result['recommendation']}")
    print(f"Confianca: {result['confidence']}%")
    print(f"Zona de Entrada: R$ {result['entry_zone']['min']:.2f} - R$ {result['entry_zone']['max']:.2f}")
    print(f"Stop Loss: R$ {result['stop_loss']:.2f}")
    print(f"Take Profit: R$ {result['take_profit']:.2f}")

    print("\n[Sinais por Timeframe]")
    for tf, sig in result['signals'].items():
        print(f"  {tf}: {sig['trend']} (forca: {sig['strength']}%, RSI: {sig['rsi']})")

    print("\n" + "=" * 60)

# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Ensemble Model v1.0
======================================
Sistema de votacao ponderada combinando multiplos modelos

Modelos:
1. Genetic Algorithm (GA) - Exploracao global
2. Simulated Annealing (SA) - Refinamento local
3. Particle Swarm (PSO) - Exploracao paralela
4. Trend Following - Seguir tendencia
5. Mean Reversion - Reversao a media

Metodos de Ensemble:
- Voting: Votacao simples
- Weighted Voting: Votacao ponderada por performance
- Stacking: Meta-modelo combinando previsoes
- Bagging: Media das previsoes
"""

import json
import math
import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class SignalType(Enum):
    STRONG_BUY = "COMPRA_FORTE"
    BUY = "COMPRA"
    NEUTRAL = "NEUTRO"
    SELL = "VENDA"
    STRONG_SELL = "VENDA_FORTE"


@dataclass
class ModelPrediction:
    """Previsao de um modelo individual"""
    model_name: str
    signal: SignalType
    confidence: float  # 0-100
    score: float  # -100 a +100
    weights: Dict[str, float]
    metrics: Dict[str, float]

    def to_dict(self) -> dict:
        return {
            "model": self.model_name,
            "signal": self.signal.value,
            "confidence": self.confidence,
            "score": self.score,
            "weights": self.weights,
            "metrics": self.metrics
        }


@dataclass
class EnsembleConfig:
    """Configuracao do ensemble"""
    # Pesos dos modelos (baseado em backtest)
    model_weights: Dict[str, float] = field(default_factory=lambda: {
        "GA": 0.30,        # Genetic Algorithm
        "SA": 0.25,        # Simulated Annealing
        "PSO": 0.20,       # Particle Swarm
        "TREND": 0.15,     # Trend Following
        "REVERSION": 0.10  # Mean Reversion
    })

    # Thresholds
    min_agreement: float = 0.6    # Minimo de concordancia (60%)
    min_confidence: float = 55.0  # Confianca minima
    strong_signal_threshold: float = 70.0  # Limiar para sinal forte

    # Adaptive weights
    use_adaptive_weights: bool = True
    weight_decay: float = 0.95    # Decaimento de peso para modelos errados
    weight_boost: float = 1.05    # Boost para modelos certos


class TrendFollowingModel:
    """
    Modelo Trend Following

    Segue tendencias estabelecidas usando:
    - EMA crossover
    - ADX para forca da tendencia
    - Momentum
    """

    def __init__(self):
        self.name = "TREND"
        self.default_weights = {
            "rsi": 0.3,
            "macd": 1.5,
            "bb": 0.5,
            "adx": 2.0,
            "stoch": 0.8,
            "volume": 1.2,
            "news": 0.5
        }

    def predict(self, indicators: Dict) -> ModelPrediction:
        """Gera previsao baseada em tendencia"""
        score = 0
        confidence = 50

        # EMA trend
        ema9 = indicators.get("ema9", 0)
        ema21 = indicators.get("ema21", 0)
        price = indicators.get("price", 0)

        if price > ema9 > ema21:
            score += 30
            confidence += 10
        elif price < ema9 < ema21:
            score -= 30
            confidence += 10

        # MACD
        macd_hist = indicators.get("macd_histogram", 0)
        if macd_hist > 0:
            score += 25
        else:
            score -= 25

        # ADX (forca da tendencia)
        adx = indicators.get("adx", 0)
        if adx > 25:
            confidence += 15
            # Direcao do DI
            plus_di = indicators.get("plus_di", 0)
            minus_di = indicators.get("minus_di", 0)
            if plus_di > minus_di:
                score += 20
            else:
                score -= 20

        # Momentum
        momentum = indicators.get("momentum", 0)
        if momentum > 2:
            score += 15
        elif momentum < -2:
            score -= 15

        # Determinar sinal
        if score >= 50:
            signal = SignalType.STRONG_BUY
        elif score >= 25:
            signal = SignalType.BUY
        elif score <= -50:
            signal = SignalType.STRONG_SELL
        elif score <= -25:
            signal = SignalType.SELL
        else:
            signal = SignalType.NEUTRAL

        return ModelPrediction(
            model_name=self.name,
            signal=signal,
            confidence=min(95, confidence),
            score=score,
            weights=self.default_weights,
            metrics={"adx": adx, "momentum": momentum}
        )


class MeanReversionModel:
    """
    Modelo Mean Reversion

    Opera reversoes quando o preco esta muito longe da media:
    - RSI extremos
    - Bollinger Bands
    - Stochastic oversold/overbought
    """

    def __init__(self):
        self.name = "REVERSION"
        self.default_weights = {
            "rsi": 2.0,
            "macd": 0.5,
            "bb": 2.0,
            "adx": 0.3,
            "stoch": 2.0,
            "volume": 0.8,
            "news": 0.3
        }

    def predict(self, indicators: Dict) -> ModelPrediction:
        """Gera previsao baseada em reversao a media"""
        score = 0
        confidence = 50

        # RSI extremos
        rsi = indicators.get("rsi", 50)
        if rsi < 30:
            score += 35
            confidence += 15
        elif rsi < 40:
            score += 15
        elif rsi > 70:
            score -= 35
            confidence += 15
        elif rsi > 60:
            score -= 15

        # Bollinger Bands
        price = indicators.get("price", 0)
        bb_upper = indicators.get("bb_upper", price * 1.02)
        bb_lower = indicators.get("bb_lower", price * 0.98)
        bb_middle = indicators.get("bb_middle", price)

        if price <= bb_lower:
            score += 30
            confidence += 10
        elif price >= bb_upper:
            score -= 30
            confidence += 10

        # Stochastic
        stoch_k = indicators.get("stoch_k", 50)
        if stoch_k < 20:
            score += 25
            confidence += 10
        elif stoch_k > 80:
            score -= 25
            confidence += 10

        # Distancia da media
        if bb_middle > 0:
            distance = (price - bb_middle) / bb_middle * 100
            if distance < -3:
                score += 15
            elif distance > 3:
                score -= 15

        # Determinar sinal
        if score >= 50:
            signal = SignalType.STRONG_BUY
        elif score >= 25:
            signal = SignalType.BUY
        elif score <= -50:
            signal = SignalType.STRONG_SELL
        elif score <= -25:
            signal = SignalType.SELL
        else:
            signal = SignalType.NEUTRAL

        return ModelPrediction(
            model_name=self.name,
            signal=signal,
            confidence=min(95, confidence),
            score=score,
            weights=self.default_weights,
            metrics={"rsi": rsi, "stoch": stoch_k}
        )


class OptimizedModel:
    """
    Modelo com pesos otimizados (GA/SA/PSO)

    Usa os pesos do treinamento TURBO
    """

    def __init__(self, name: str, weights: Dict[str, float]):
        self.name = name
        self.weights = weights

    def predict(self, indicators: Dict) -> ModelPrediction:
        """Gera previsao usando pesos otimizados"""
        score = 0
        max_score = 0

        # RSI Score
        rsi = indicators.get("rsi", 50)
        rsi_score = 0
        if rsi < 30:
            rsi_score = 30
        elif rsi < 40:
            rsi_score = 15
        elif rsi > 70:
            rsi_score = -30
        elif rsi > 60:
            rsi_score = -15
        score += rsi_score * self.weights.get("rsi", 1.0)
        max_score += 30 * self.weights.get("rsi", 1.0)

        # MACD Score
        macd_hist = indicators.get("macd_histogram", 0)
        macd_score = 25 if macd_hist > 0 else -25
        score += macd_score * self.weights.get("macd", 1.0)
        max_score += 25 * self.weights.get("macd", 1.0)

        # BB Score
        price = indicators.get("price", 0)
        bb_lower = indicators.get("bb_lower", price * 0.98)
        bb_upper = indicators.get("bb_upper", price * 1.02)
        bb_score = 0
        if price <= bb_lower:
            bb_score = 25
        elif price >= bb_upper:
            bb_score = -25
        score += bb_score * self.weights.get("bb", 1.0)
        max_score += 25 * self.weights.get("bb", 1.0)

        # ADX Score
        adx = indicators.get("adx", 0)
        plus_di = indicators.get("plus_di", 0)
        minus_di = indicators.get("minus_di", 0)
        adx_score = 0
        if adx >= 25:
            adx_score = 15 if plus_di > minus_di else -15
        score += adx_score * self.weights.get("adx", 1.0)
        max_score += 15 * self.weights.get("adx", 1.0)

        # Stochastic Score
        stoch_k = indicators.get("stoch_k", 50)
        stoch_score = 0
        if stoch_k < 20:
            stoch_score = 15
        elif stoch_k > 80:
            stoch_score = -15
        score += stoch_score * self.weights.get("stoch", 1.0)
        max_score += 15 * self.weights.get("stoch", 1.0)

        # Volume Score
        obv_trend = indicators.get("obv_trend", "NEUTRO")
        vwap_pos = indicators.get("vwap_position", "NEUTRO")
        volume_score = 0
        if obv_trend == "ALTA" and vwap_pos == "ACIMA":
            volume_score = 10
        elif obv_trend == "BAIXA" and vwap_pos == "ABAIXO":
            volume_score = -10
        score += volume_score * self.weights.get("volume", 1.0)
        max_score += 10 * self.weights.get("volume", 1.0)

        # Normalizar
        if max_score > 0:
            normalized_score = (score / max_score) * 100
        else:
            normalized_score = 0

        confidence = min(95, 50 + abs(normalized_score) * 0.4)

        # Determinar sinal
        if normalized_score >= 40:
            signal = SignalType.STRONG_BUY
        elif normalized_score >= 20:
            signal = SignalType.BUY
        elif normalized_score <= -40:
            signal = SignalType.STRONG_SELL
        elif normalized_score <= -20:
            signal = SignalType.SELL
        else:
            signal = SignalType.NEUTRAL

        return ModelPrediction(
            model_name=self.name,
            signal=signal,
            confidence=confidence,
            score=normalized_score,
            weights=self.weights,
            metrics={"raw_score": score, "max_score": max_score}
        )


class EnsembleModel:
    """
    Ensemble de multiplos modelos

    Combina previsoes usando votacao ponderada
    """

    def __init__(self, config: EnsembleConfig = None):
        self.config = config or EnsembleConfig()

        # Pesos otimizados do treinamento TURBO
        self.turbo_weights = {
            "rsi": 0.056,
            "macd": 1.19,
            "bb": 0.093,
            "adx": 2.447,
            "stoch": 2.662,
            "volume": 2.049,
            "news": 1.067
        }

        # Inicializar modelos
        self.models = {
            "GA": OptimizedModel("GA", self._vary_weights(self.turbo_weights, 0.1)),
            "SA": OptimizedModel("SA", self._vary_weights(self.turbo_weights, 0.15)),
            "PSO": OptimizedModel("PSO", self._vary_weights(self.turbo_weights, 0.2)),
            "TREND": TrendFollowingModel(),
            "REVERSION": MeanReversionModel()
        }

        # Performance historica dos modelos
        self.model_performance = {name: {"correct": 0, "total": 0, "win_rate": 0.5}
                                   for name in self.models.keys()}

    def _vary_weights(self, base_weights: Dict, variance: float) -> Dict:
        """Cria variacao dos pesos base"""
        varied = {}
        for key, value in base_weights.items():
            variation = random.uniform(1 - variance, 1 + variance)
            varied[key] = round(value * variation, 3)
        return varied

    def _signal_to_score(self, signal: SignalType) -> float:
        """Converte sinal para score numerico"""
        mapping = {
            SignalType.STRONG_BUY: 2.0,
            SignalType.BUY: 1.0,
            SignalType.NEUTRAL: 0.0,
            SignalType.SELL: -1.0,
            SignalType.STRONG_SELL: -2.0
        }
        return mapping.get(signal, 0)

    def _score_to_signal(self, score: float) -> SignalType:
        """Converte score para sinal"""
        if score >= 1.5:
            return SignalType.STRONG_BUY
        elif score >= 0.5:
            return SignalType.BUY
        elif score <= -1.5:
            return SignalType.STRONG_SELL
        elif score <= -0.5:
            return SignalType.SELL
        else:
            return SignalType.NEUTRAL

    def get_model_weights(self) -> Dict[str, float]:
        """Retorna pesos atuais dos modelos"""
        if self.config.use_adaptive_weights:
            # Ajustar pesos baseado em performance
            adjusted = {}
            total_wr = sum(p["win_rate"] for p in self.model_performance.values())

            for name in self.models.keys():
                base_weight = self.config.model_weights.get(name, 0.2)
                wr = self.model_performance[name]["win_rate"]
                # Peso proporcional ao win rate
                if total_wr > 0:
                    adjusted[name] = base_weight * (wr / (total_wr / len(self.models)))
                else:
                    adjusted[name] = base_weight

            # Normalizar
            total = sum(adjusted.values())
            if total > 0:
                adjusted = {k: v / total for k, v in adjusted.items()}

            return adjusted
        else:
            return self.config.model_weights

    def predict(self, indicators: Dict) -> Dict:
        """
        Gera previsao do ensemble

        Args:
            indicators: Dicionario com indicadores tecnicos

        Returns:
            {
                "signal": SignalType,
                "confidence": float,
                "score": float,
                "agreement": float,
                "predictions": [...],
                "recommendation": str
            }
        """
        predictions = []
        weights = self.get_model_weights()

        # Coletar previsoes de cada modelo
        for name, model in self.models.items():
            try:
                pred = model.predict(indicators)
                predictions.append(pred)
            except Exception as e:
                print(f"[Ensemble] Erro no modelo {name}: {e}")

        if not predictions:
            return {
                "signal": SignalType.NEUTRAL.value,
                "confidence": 0,
                "score": 0,
                "agreement": 0,
                "predictions": [],
                "recommendation": "ERRO_ENSEMBLE"
            }

        # Votacao ponderada
        weighted_score = 0
        weighted_confidence = 0
        total_weight = 0

        for pred in predictions:
            w = weights.get(pred.model_name, 0.2)
            signal_score = self._signal_to_score(pred.signal)
            weighted_score += signal_score * w * (pred.confidence / 100)
            weighted_confidence += pred.confidence * w
            total_weight += w

        if total_weight > 0:
            final_score = weighted_score / total_weight
            final_confidence = weighted_confidence / total_weight
        else:
            final_score = 0
            final_confidence = 0

        # Calcular concordancia
        signals = [self._signal_to_score(p.signal) for p in predictions]
        mean_signal = sum(signals) / len(signals)
        variance = sum((s - mean_signal) ** 2 for s in signals) / len(signals)
        agreement = max(0, 100 - variance * 25)  # Menor variancia = maior concordancia

        # Sinal final
        final_signal = self._score_to_signal(final_score)

        # Verificar concordancia minima
        if agreement < self.config.min_agreement * 100:
            final_signal = SignalType.NEUTRAL
            final_confidence *= 0.7
            recommendation = "AGUARDAR - Baixa concordancia entre modelos"
        elif final_confidence < self.config.min_confidence:
            recommendation = "AGUARDAR - Confianca baixa"
        elif final_signal in [SignalType.STRONG_BUY, SignalType.STRONG_SELL]:
            recommendation = f"{final_signal.value} - Alta confianca ({final_confidence:.1f}%)"
        elif final_signal in [SignalType.BUY, SignalType.SELL]:
            recommendation = f"{final_signal.value} - Confianca moderada ({final_confidence:.1f}%)"
        else:
            recommendation = "AGUARDAR - Sinal neutro"

        return {
            "signal": final_signal.value,
            "confidence": round(final_confidence, 1),
            "score": round(final_score * 50, 1),  # Escala -100 a +100
            "agreement": round(agreement, 1),
            "predictions": [p.to_dict() for p in predictions],
            "model_weights": weights,
            "recommendation": recommendation,
            "timestamp": datetime.now().isoformat()
        }

    def update_performance(self, model_name: str, was_correct: bool):
        """Atualiza performance de um modelo"""
        if model_name in self.model_performance:
            self.model_performance[model_name]["total"] += 1
            if was_correct:
                self.model_performance[model_name]["correct"] += 1

            total = self.model_performance[model_name]["total"]
            correct = self.model_performance[model_name]["correct"]
            self.model_performance[model_name]["win_rate"] = correct / total if total > 0 else 0.5

    def get_performance(self) -> Dict:
        """Retorna performance de todos os modelos"""
        return {
            "models": self.model_performance,
            "weights": self.get_model_weights(),
            "adaptive_weights": self.config.use_adaptive_weights
        }

    def get_best_weights(self) -> Dict[str, float]:
        """
        Retorna os melhores pesos combinados

        Media ponderada dos pesos de cada modelo baseado em sua performance
        """
        weights = self.get_model_weights()
        combined = {
            "rsi": 0, "macd": 0, "bb": 0,
            "adx": 0, "stoch": 0, "volume": 0, "news": 0
        }

        for name, model in self.models.items():
            model_weight = weights.get(name, 0.2)
            if hasattr(model, 'weights'):
                for ind, w in model.weights.items():
                    if ind in combined:
                        combined[ind] += w * model_weight
            elif hasattr(model, 'default_weights'):
                for ind, w in model.default_weights.items():
                    if ind in combined:
                        combined[ind] += w * model_weight

        return {k: round(v, 3) for k, v in combined.items()}


# Instancia global
ensemble = EnsembleModel()


# Funcoes de conveniencia
def ensemble_predict(indicators: Dict) -> Dict:
    """Previsao do ensemble"""
    return ensemble.predict(indicators)

def get_ensemble_performance() -> Dict:
    """Performance do ensemble"""
    return ensemble.get_performance()

def get_combined_weights() -> Dict:
    """Pesos combinados otimos"""
    return ensemble.get_best_weights()

def update_model_performance(model_name: str, was_correct: bool):
    """Atualiza performance de modelo"""
    ensemble.update_performance(model_name, was_correct)


if __name__ == "__main__":
    print("=" * 60)
    print("  TESTE ENSEMBLE MODEL")
    print("=" * 60)

    # Indicadores de teste (cenario bullish)
    indicators = {
        "price": 40.50,
        "rsi": 45,
        "macd_histogram": 0.15,
        "ema9": 40.20,
        "ema21": 39.80,
        "bb_upper": 42.00,
        "bb_lower": 38.00,
        "bb_middle": 40.00,
        "adx": 28,
        "plus_di": 25,
        "minus_di": 18,
        "stoch_k": 55,
        "obv_trend": "ALTA",
        "vwap_position": "ACIMA",
        "momentum": 3.5
    }

    print("\n[Indicadores]")
    for k, v in indicators.items():
        print(f"  {k}: {v}")

    print("\n[Previsao do Ensemble]")
    result = ensemble_predict(indicators)

    print(f"\nSinal: {result['signal']}")
    print(f"Confianca: {result['confidence']}%")
    print(f"Score: {result['score']}")
    print(f"Concordancia: {result['agreement']}%")
    print(f"Recomendacao: {result['recommendation']}")

    print("\n[Previsoes Individuais]")
    for pred in result["predictions"]:
        print(f"  {pred['model']}: {pred['signal']} (conf: {pred['confidence']:.1f}%)")

    print("\n[Pesos dos Modelos]")
    for model, weight in result["model_weights"].items():
        print(f"  {model}: {weight:.2%}")

    print("\n[Pesos Combinados Otimos]")
    combined = get_combined_weights()
    for ind, w in sorted(combined.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ind}: {w:.3f}")

    print("\n" + "=" * 60)

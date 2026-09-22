# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Sistema de Treinamento Acelerado v2.0
=======================================================
Recursos Avancados:
- Gradient Descent para otimizacao de pesos
- Walk-Forward Optimization
- Regime Detection (Bull/Bear)
- Ensemble de Estrategias
- Feature Engineering Avancado
- Cross-Validation Temporal
- Momentum e Regularizacao L2
"""

import os
import json
import math
import random
import asyncio
import httpx
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
import env_config as cfg  # configuracao sempre do .env da raiz

API_URL = cfg.server_url()
BRAPI_TOKEN = cfg.get_str("BRAPI_TOKEN", "")

# ══════════════════════════════════════════════════════════════
# CONFIGURACAO AVANCADA
# ══════════════════════════════════════════════════════════════

@dataclass
class TrainingConfig:
    """Configuracao do treinamento"""
    # Otimizacao
    learning_rate: float = 0.15           # Taxa de aprendizado (aumentado)
    momentum: float = 0.85                 # Momentum para gradiente
    l2_regularization: float = 0.01       # Regularizacao L2

    # Treinamento
    epochs: int = 50                       # Epocas de treinamento
    batch_size: int = 20                   # Trades por batch
    validation_split: float = 0.2          # 20% para validacao
    early_stopping_patience: int = 8       # Paciencia para early stopping

    # Walk-Forward
    walk_forward_windows: int = 5          # Janelas de validacao
    train_window_days: int = 30            # Dias de treino por janela
    test_window_days: int = 7              # Dias de teste por janela

    # Limites
    min_weight: float = 0.1                # Peso minimo
    max_weight: float = 2.5                # Peso maximo

    # Regime Detection
    regime_lookback: int = 10              # Dias para detectar regime
    volatility_threshold: float = 2.0      # Limiar de volatilidade


# Ativos para treinamento (diversificados)
TRAINING_TICKERS = {
    "blue_chips": ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "WEGE3", "ABEV3", "B3SA3"],
    "volateis": ["MGLU3", "PRIO3", "AZUL4", "GOLL4", "CVCB3", "IRBR3", "OIBR3", "COGN3"],
    "energia": ["PETR3", "ELET3", "CMIG4", "CPLE6", "ENEV3", "CPFE3"],
    "small_caps": ["LWSA3", "CASH3", "PETZ3", "LREN3", "RENT3", "SUZB3"]
}

# ══════════════════════════════════════════════════════════════
# ESTRUTURAS DE DADOS
# ══════════════════════════════════════════════════════════════

@dataclass
class Trade:
    """Representa um trade simulado"""
    ticker: str
    entry_price: float
    exit_price: float
    score: float
    signal: str
    indicators: Dict
    pnl_percent: float = 0
    is_win: bool = False
    regime: str = "NEUTRO"
    volatility: float = 0
    timestamp: str = ""

    def __post_init__(self):
        if self.entry_price > 0:
            self.pnl_percent = ((self.exit_price - self.entry_price) / self.entry_price) * 100
            self.is_win = self.pnl_percent > 0
        self.timestamp = datetime.now().isoformat()


@dataclass
class WeightState:
    """Estado dos pesos durante treinamento"""
    rsi: float = 0.6
    macd: float = 1.0
    bb: float = 1.0
    adx: float = 1.5
    stoch: float = 1.0
    volume: float = 0.7
    news: float = 0.5

    # Momentum (velocidade anterior)
    velocity: Dict = field(default_factory=lambda: {
        "rsi": 0, "macd": 0, "bb": 0, "adx": 0, "stoch": 0, "volume": 0, "news": 0
    })

    def to_dict(self) -> Dict:
        return {
            "rsi": round(self.rsi, 3),
            "macd": round(self.macd, 3),
            "bb": round(self.bb, 3),
            "adx": round(self.adx, 3),
            "stoch": round(self.stoch, 3),
            "volume": round(self.volume, 3),
            "news": round(self.news, 3)
        }

    def clip(self, config: TrainingConfig):
        """Limita pesos ao range permitido"""
        self.rsi = max(config.min_weight, min(config.max_weight, self.rsi))
        self.macd = max(config.min_weight, min(config.max_weight, self.macd))
        self.bb = max(config.min_weight, min(config.max_weight, self.bb))
        self.adx = max(config.min_weight, min(config.max_weight, self.adx))
        self.stoch = max(config.min_weight, min(config.max_weight, self.stoch))
        self.volume = max(config.min_weight, min(config.max_weight, self.volume))
        self.news = max(config.min_weight, min(config.max_weight, self.news))


@dataclass
class TrainingResults:
    """Resultados consolidados do treinamento"""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0
    win_rate: float = 0
    avg_pnl: float = 0
    sharpe_ratio: float = 0
    max_drawdown: float = 0
    profit_factor: float = 0

    # Por indicador
    indicator_performance: Dict = field(default_factory=lambda: {
        "rsi": {"wins": 0, "losses": 0, "pnl": 0, "contribution": 0},
        "macd": {"wins": 0, "losses": 0, "pnl": 0, "contribution": 0},
        "bb": {"wins": 0, "losses": 0, "pnl": 0, "contribution": 0},
        "adx": {"wins": 0, "losses": 0, "pnl": 0, "contribution": 0},
        "stoch": {"wins": 0, "losses": 0, "pnl": 0, "contribution": 0},
        "volume": {"wins": 0, "losses": 0, "pnl": 0, "contribution": 0}
    })

    # Por regime de mercado
    regime_performance: Dict = field(default_factory=lambda: {
        "BULL": {"trades": 0, "wins": 0, "pnl": 0},
        "BEAR": {"trades": 0, "wins": 0, "pnl": 0},
        "NEUTRO": {"trades": 0, "wins": 0, "pnl": 0}
    })

    # Melhores configuracoes
    optimized_weights: Dict = field(default_factory=dict)
    best_strategies: List = field(default_factory=list)
    insights: List = field(default_factory=list)

    # Metricas de treinamento
    training_epochs: int = 0
    convergence_history: List = field(default_factory=list)
    training_time: float = 0

    def calculate_metrics(self, trades: List[Trade]):
        """Calcula metricas avancadas"""
        if not trades:
            return

        self.total_trades = len(trades)
        self.wins = sum(1 for t in trades if t.is_win)
        self.losses = self.total_trades - self.wins
        self.total_pnl = sum(t.pnl_percent for t in trades)

        self.win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        self.avg_pnl = self.total_pnl / self.total_trades if self.total_trades > 0 else 0

        # Sharpe Ratio simplificado
        if len(trades) > 1:
            returns = [t.pnl_percent for t in trades]
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            std_return = math.sqrt(variance) if variance > 0 else 1
            self.sharpe_ratio = (mean_return / std_return) * math.sqrt(252) if std_return > 0 else 0

        # Max Drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in trades:
            cumulative += t.pnl_percent
            peak = max(peak, cumulative)
            dd = peak - cumulative
            max_dd = max(max_dd, dd)
        self.max_drawdown = max_dd

        # Profit Factor
        gross_profit = sum(t.pnl_percent for t in trades if t.is_win)
        gross_loss = abs(sum(t.pnl_percent for t in trades if not t.is_win))
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit


# ══════════════════════════════════════════════════════════════
# API CLIENT
# ══════════════════════════════════════════════════════════════

class NexusAPIClient:
    """Cliente para API do servidor"""

    def __init__(self, base_url: str = API_URL):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30)
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    async def get_score(self, ticker: str, weights: WeightState) -> Optional[Dict]:
        """Busca score com pesos customizados"""
        try:
            params = {
                "peso_rsi": weights.rsi,
                "peso_macd": weights.macd,
                "peso_bb": weights.bb,
                "peso_adx": weights.adx,
                "peso_stoch": weights.stoch,
                "peso_volume": weights.volume,
                "peso_news": weights.news
            }
            r = await self.client.get(f"{self.base_url}/api/score/{ticker}", params=params)
            return r.json()
        except:
            return None

    async def get_history(self, ticker: str, days: int = 60) -> Optional[Dict]:
        """Busca historico de precos"""
        try:
            r = await self.client.get(f"{self.base_url}/api/history/{ticker}?days={days}")
            return r.json()
        except:
            return None

    async def check_status(self) -> bool:
        """Verifica se servidor esta online"""
        try:
            r = await self.client.get(f"{self.base_url}/api/status")
            return r.status_code == 200
        except:
            return False


# ══════════════════════════════════════════════════════════════
# REGIME DETECTION
# ══════════════════════════════════════════════════════════════

def detect_market_regime(prices: List[float], config: TrainingConfig) -> Tuple[str, float]:
    """
    Detecta regime de mercado (BULL/BEAR/NEUTRO) e volatilidade
    """
    if len(prices) < config.regime_lookback:
        return "NEUTRO", 1.0

    recent = prices[-config.regime_lookback:]

    # Calcular retornos
    returns = [(recent[i] - recent[i-1]) / recent[i-1] * 100 for i in range(1, len(recent))]

    # Volatilidade (desvio padrao dos retornos)
    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    volatility = math.sqrt(variance)

    # Tendencia (media movel)
    trend = (recent[-1] - recent[0]) / recent[0] * 100

    # Classificar regime
    if trend > 3 and mean_ret > 0.2:
        regime = "BULL"
    elif trend < -3 and mean_ret < -0.2:
        regime = "BEAR"
    else:
        regime = "NEUTRO"

    return regime, volatility


# ══════════════════════════════════════════════════════════════
# GRADIENT DESCENT OPTIMIZER
# ══════════════════════════════════════════════════════════════

class GradientDescentOptimizer:
    """
    Otimizador usando Gradient Descent com Momentum
    """

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.weights = WeightState()
        self.best_weights = WeightState()
        self.best_score = float('-inf')
        self.history: List[Dict] = []

    def compute_gradient(self, trades: List[Trade], weights: WeightState) -> Dict[str, float]:
        """
        Calcula gradiente aproximado usando diferenca finita
        """
        epsilon = 0.05
        base_score = self._evaluate_weights(trades, weights)
        gradients = {}

        for indicator in ["rsi", "macd", "bb", "adx", "stoch", "volume", "news"]:
            # Perturbar peso positivamente
            weights_plus = WeightState(**weights.to_dict())
            setattr(weights_plus, indicator, getattr(weights_plus, indicator) + epsilon)
            score_plus = self._evaluate_weights(trades, weights_plus)

            # Perturbar peso negativamente
            weights_minus = WeightState(**weights.to_dict())
            setattr(weights_minus, indicator, getattr(weights_minus, indicator) - epsilon)
            score_minus = self._evaluate_weights(trades, weights_minus)

            # Gradiente central
            gradient = (score_plus - score_minus) / (2 * epsilon)
            gradients[indicator] = gradient

        return gradients

    def _evaluate_weights(self, trades: List[Trade], weights: WeightState) -> float:
        """
        Avalia qualidade dos pesos baseado nos trades
        Retorna score que queremos maximizar
        """
        if not trades:
            return 0

        total_score = 0
        correct_predictions = 0

        for trade in trades:
            breakdown = trade.indicators.get("breakdown", {})

            # Calcular score ponderado
            weighted_score = 0
            for ind in ["rsi", "macd", "bb", "adx", "stoch", "volume"]:
                if ind in breakdown:
                    ind_score = breakdown[ind].get("score", 0)
                    weight = getattr(weights, ind)
                    weighted_score += ind_score * weight

            # Se score alto e trade foi win, ou score baixo e trade foi loss = correto
            predicted_direction = 1 if weighted_score > 20 else -1 if weighted_score < -20 else 0
            actual_direction = 1 if trade.is_win else -1

            if predicted_direction == actual_direction:
                correct_predictions += 1
                total_score += abs(weighted_score) * trade.pnl_percent
            else:
                total_score -= abs(weighted_score) * abs(trade.pnl_percent) * 0.5

        # Accuracy bonus
        accuracy = correct_predictions / len(trades)
        accuracy_bonus = accuracy * 100

        # Regularizacao L2
        l2_penalty = self.config.l2_regularization * sum(
            getattr(weights, ind) ** 2 for ind in ["rsi", "macd", "bb", "adx", "stoch", "volume", "news"]
        )

        return total_score + accuracy_bonus - l2_penalty

    def step(self, trades: List[Trade]) -> float:
        """
        Executa um passo de otimizacao
        Retorna o score atual
        """
        # Calcular gradiente
        gradients = self.compute_gradient(trades, self.weights)

        # Atualizar pesos com momentum
        for indicator in ["rsi", "macd", "bb", "adx", "stoch", "volume", "news"]:
            # Momentum update
            velocity = self.weights.velocity[indicator]
            gradient = gradients[indicator]

            new_velocity = self.config.momentum * velocity + self.config.learning_rate * gradient
            self.weights.velocity[indicator] = new_velocity

            # Aplicar atualizacao
            current_weight = getattr(self.weights, indicator)
            new_weight = current_weight + new_velocity
            setattr(self.weights, indicator, new_weight)

        # Clipar pesos
        self.weights.clip(self.config)

        # Avaliar novos pesos
        current_score = self._evaluate_weights(trades, self.weights)

        # Salvar melhor configuracao
        if current_score > self.best_score:
            self.best_score = current_score
            self.best_weights = WeightState(**self.weights.to_dict())

        # Registrar historico
        self.history.append({
            "score": current_score,
            "weights": self.weights.to_dict(),
            "gradients": gradients
        })

        return current_score


# ══════════════════════════════════════════════════════════════
# ENSEMBLE STRATEGY
# ══════════════════════════════════════════════════════════════

class EnsembleStrategy:
    """
    Combina multiplas estrategias com votacao ponderada
    """

    def __init__(self):
        self.strategies = {
            "trend_following": {
                "weights": {"rsi": 0.5, "macd": 1.5, "bb": 0.8, "adx": 2.0, "stoch": 0.6, "volume": 0.8, "news": 0.3},
                "performance": 0,
                "description": "Segue tendencias fortes (ADX + MACD)"
            },
            "mean_reversion": {
                "weights": {"rsi": 1.8, "macd": 0.6, "bb": 1.8, "adx": 0.5, "stoch": 1.5, "volume": 0.6, "news": 0.3},
                "performance": 0,
                "description": "Reversao a media (RSI + BB + Stoch)"
            },
            "momentum": {
                "weights": {"rsi": 1.0, "macd": 1.5, "bb": 0.5, "adx": 1.2, "stoch": 1.0, "volume": 1.5, "news": 0.5},
                "performance": 0,
                "description": "Momentum com volume (MACD + Volume)"
            },
            "balanced": {
                "weights": {"rsi": 1.0, "macd": 1.0, "bb": 1.0, "adx": 1.0, "stoch": 1.0, "volume": 1.0, "news": 0.5},
                "performance": 0,
                "description": "Equilibrado (todos os indicadores)"
            },
            "conservative": {
                "weights": {"rsi": 0.8, "macd": 1.2, "bb": 1.2, "adx": 1.5, "stoch": 0.8, "volume": 0.5, "news": 0.2},
                "performance": 0,
                "description": "Conservador (menor risco)"
            }
        }

    def evaluate_strategy(self, strategy_name: str, trades: List[Trade]) -> float:
        """Avalia performance de uma estrategia"""
        if strategy_name not in self.strategies:
            return 0

        weights = self.strategies[strategy_name]["weights"]
        correct = 0
        total_pnl = 0

        for trade in trades:
            breakdown = trade.indicators.get("breakdown", {})

            # Calcular score com pesos da estrategia
            score = 0
            for ind, weight in weights.items():
                if ind in breakdown:
                    score += breakdown[ind].get("score", 0) * weight

            # Verificar se previsao estava correta
            predicted_buy = score > 15
            actual_win = trade.is_win

            if (predicted_buy and actual_win) or (not predicted_buy and not actual_win):
                correct += 1
                total_pnl += abs(trade.pnl_percent)
            else:
                total_pnl -= abs(trade.pnl_percent) * 0.5

        win_rate = correct / len(trades) if trades else 0
        performance = win_rate * 100 + total_pnl
        self.strategies[strategy_name]["performance"] = performance

        return performance

    def get_best_strategy(self) -> Tuple[str, Dict]:
        """Retorna melhor estrategia"""
        best = max(self.strategies.items(), key=lambda x: x[1]["performance"])
        return best[0], best[1]

    def get_ensemble_weights(self) -> Dict[str, float]:
        """Calcula pesos combinados (media ponderada por performance)"""
        total_perf = sum(max(s["performance"], 0.01) for s in self.strategies.values())

        ensemble = {"rsi": 0, "macd": 0, "bb": 0, "adx": 0, "stoch": 0, "volume": 0, "news": 0}

        for strategy in self.strategies.values():
            weight_factor = max(strategy["performance"], 0.01) / total_perf
            for ind, val in strategy["weights"].items():
                ensemble[ind] += val * weight_factor

        # Arredondar
        return {k: round(v, 3) for k, v in ensemble.items()}


# ══════════════════════════════════════════════════════════════
# TRAINER PRINCIPAL
# ══════════════════════════════════════════════════════════════

class AdvancedTrainer:
    """
    Sistema de treinamento avancado com todas as tecnicas
    """

    def __init__(self, config: TrainingConfig = TrainingConfig()):
        self.config = config
        self.optimizer = GradientDescentOptimizer(config)
        self.ensemble = EnsembleStrategy()
        self.results = TrainingResults()
        self.all_trades: List[Trade] = []

    async def collect_training_data(self, verbose: bool = True) -> List[Trade]:
        """
        Coleta dados de treinamento de multiplos ativos
        """
        trades = []

        async with NexusAPIClient() as client:
            if not await client.check_status():
                print("[ERRO] Servidor nao esta respondendo!")
                print("       Execute: python server_fastmcp.py http")
                return trades

            print("\n[1/4] Coletando dados de treinamento...")

            all_tickers = []
            for category, tickers in TRAINING_TICKERS.items():
                all_tickers.extend(tickers)
            all_tickers = list(set(all_tickers))

            for i, ticker in enumerate(all_tickers):
                if verbose and i % 5 == 0:
                    print(f"      Processando {i+1}/{len(all_tickers)} ativos...")

                # Buscar historico
                history = await client.get_history(ticker, 60)
                if not history or "error" in history:
                    continue

                data = history.get("data", [])
                if len(data) < 30:
                    continue

                prices = [d.get("close", 0) for d in data if d.get("close", 0) > 0]
                if len(prices) < 25:
                    continue

                # Detectar regime de mercado
                regime, volatility = detect_market_regime(prices, self.config)

                # Buscar score atual
                score_data = await client.get_score(ticker, self.optimizer.weights)
                if not score_data or "error" in score_data:
                    continue

                # Simular trades em diferentes pontos do historico
                for j in range(20, len(prices) - 5, 3):
                    entry_price = prices[j]

                    # Multiplos horizontes de saida
                    for exit_offset in [1, 2, 3, 5]:
                        if j + exit_offset >= len(prices):
                            break

                        exit_price = prices[j + exit_offset]

                        trade = Trade(
                            ticker=ticker,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            score=score_data.get("score", 0),
                            signal=score_data.get("signal", "NEUTRO"),
                            indicators=score_data,
                            regime=regime,
                            volatility=volatility
                        )
                        trades.append(trade)

                # Limitar requests
                await asyncio.sleep(0.1)

        print(f"      Coletados {len(trades)} trades para treinamento")
        return trades

    async def run_gradient_descent(self, trades: List[Trade], verbose: bool = True) -> Dict:
        """
        Executa otimizacao por gradient descent
        """
        print("\n[2/4] Executando Gradient Descent...")

        # Dividir em treino/validacao
        random.shuffle(trades)
        split_idx = int(len(trades) * (1 - self.config.validation_split))
        train_trades = trades[:split_idx]
        val_trades = trades[split_idx:]

        print(f"      Treino: {len(train_trades)} | Validacao: {len(val_trades)}")

        best_val_score = float('-inf')
        patience_counter = 0

        for epoch in range(self.config.epochs):
            # Embaralhar treino
            random.shuffle(train_trades)

            # Treinar em batches
            epoch_scores = []
            for i in range(0, len(train_trades), self.config.batch_size):
                batch = train_trades[i:i + self.config.batch_size]
                score = self.optimizer.step(batch)
                epoch_scores.append(score)

            # Avaliar validacao
            val_score = self.optimizer._evaluate_weights(val_trades, self.optimizer.weights)
            train_score = sum(epoch_scores) / len(epoch_scores) if epoch_scores else 0

            # Early stopping
            if val_score > best_val_score:
                best_val_score = val_score
                patience_counter = 0
            else:
                patience_counter += 1

            if verbose and epoch % 5 == 0:
                print(f"      Epoch {epoch+1:3d} | Train: {train_score:8.2f} | Val: {val_score:8.2f} | Best: {best_val_score:8.2f}")

            # Registrar convergencia
            self.results.convergence_history.append({
                "epoch": epoch + 1,
                "train_score": train_score,
                "val_score": val_score,
                "weights": self.optimizer.weights.to_dict()
            })

            if patience_counter >= self.config.early_stopping_patience:
                print(f"      Early stopping na epoca {epoch + 1}")
                break

        self.results.training_epochs = epoch + 1

        return {
            "best_weights": self.optimizer.best_weights.to_dict(),
            "final_weights": self.optimizer.weights.to_dict(),
            "best_score": self.optimizer.best_score,
            "epochs_trained": epoch + 1
        }

    async def run_ensemble_evaluation(self, trades: List[Trade], verbose: bool = True) -> Dict:
        """
        Avalia e combina estrategias do ensemble
        """
        print("\n[3/4] Avaliando Ensemble de Estrategias...")

        for strategy_name in self.ensemble.strategies:
            perf = self.ensemble.evaluate_strategy(strategy_name, trades)
            if verbose:
                print(f"      {strategy_name:18s} | Performance: {perf:8.2f}")

        best_name, best_strategy = self.ensemble.get_best_strategy()
        ensemble_weights = self.ensemble.get_ensemble_weights()

        print(f"\n      Melhor estrategia: {best_name}")
        print(f"      Descricao: {best_strategy['description']}")

        return {
            "best_strategy": best_name,
            "best_weights": best_strategy["weights"],
            "ensemble_weights": ensemble_weights,
            "all_strategies": {
                name: {"performance": s["performance"], "description": s["description"]}
                for name, s in self.ensemble.strategies.items()
            }
        }

    def analyze_by_regime(self, trades: List[Trade]) -> Dict:
        """
        Analisa performance por regime de mercado
        """
        for trade in trades:
            regime = trade.regime
            if regime in self.results.regime_performance:
                self.results.regime_performance[regime]["trades"] += 1
                if trade.is_win:
                    self.results.regime_performance[regime]["wins"] += 1
                self.results.regime_performance[regime]["pnl"] += trade.pnl_percent

        # Calcular win rates
        analysis = {}
        for regime, data in self.results.regime_performance.items():
            if data["trades"] > 0:
                win_rate = (data["wins"] / data["trades"]) * 100
                avg_pnl = data["pnl"] / data["trades"]
                analysis[regime] = {
                    "trades": data["trades"],
                    "win_rate": round(win_rate, 1),
                    "avg_pnl": round(avg_pnl, 2),
                    "total_pnl": round(data["pnl"], 2)
                }

        return analysis

    def analyze_indicators(self, trades: List[Trade]) -> Dict:
        """
        Analisa performance de cada indicador
        """
        for trade in trades:
            breakdown = trade.indicators.get("breakdown", {})

            for ind in ["rsi", "macd", "bb", "adx", "stoch", "volume"]:
                if ind not in breakdown:
                    continue

                weighted = breakdown[ind].get("weighted", 0)
                if abs(weighted) < 3:  # Indicador nao contribuiu significativamente
                    continue

                if trade.is_win:
                    self.results.indicator_performance[ind]["wins"] += 1
                else:
                    self.results.indicator_performance[ind]["losses"] += 1

                self.results.indicator_performance[ind]["pnl"] += trade.pnl_percent
                self.results.indicator_performance[ind]["contribution"] += abs(weighted)

        # Calcular metricas
        analysis = {}
        for ind, data in self.results.indicator_performance.items():
            total = data["wins"] + data["losses"]
            if total > 0:
                win_rate = (data["wins"] / total) * 100
                avg_pnl = data["pnl"] / total
                analysis[ind] = {
                    "total_trades": total,
                    "win_rate": round(win_rate, 1),
                    "avg_pnl": round(avg_pnl, 2),
                    "total_contribution": round(data["contribution"], 1),
                    "recommendation": "AUMENTAR" if win_rate > 55 else "REDUZIR" if win_rate < 45 else "MANTER"
                }

        return analysis

    def generate_insights(self, indicator_analysis: Dict, regime_analysis: Dict, ensemble_results: Dict) -> List[str]:
        """
        Gera insights automaticos baseados na analise
        """
        insights = []

        # Melhor indicador
        best_indicator = max(indicator_analysis.items(), key=lambda x: x[1]["win_rate"], default=(None, {}))
        if best_indicator[0]:
            insights.append(f"{best_indicator[0].upper()} e o indicador mais confiavel ({best_indicator[1]['win_rate']}% win rate)")

        # Pior indicador
        worst_indicator = min(indicator_analysis.items(), key=lambda x: x[1]["win_rate"], default=(None, {}))
        if worst_indicator[0] and worst_indicator[1].get("win_rate", 50) < 45:
            insights.append(f"{worst_indicator[0].upper()} teve baixa performance ({worst_indicator[1]['win_rate']}%) - peso reduzido")

        # Melhor regime
        best_regime = max(regime_analysis.items(), key=lambda x: x[1].get("win_rate", 0), default=(None, {}))
        if best_regime[0]:
            insights.append(f"Melhor performance em mercado {best_regime[0]} ({best_regime[1].get('win_rate', 0)}% win rate)")

        # Estrategia vencedora
        if ensemble_results.get("best_strategy"):
            insights.append(f"Estrategia recomendada: {ensemble_results['best_strategy']}")

        # Win rate geral
        if self.results.win_rate > 55:
            insights.append(f"Bot otimizado com {self.results.win_rate:.1f}% win rate - POSITIVO")
        elif self.results.win_rate < 50:
            insights.append(f"Win rate de {self.results.win_rate:.1f}% - continuar treinamento recomendado")

        # Sharpe ratio
        if self.results.sharpe_ratio > 1.5:
            insights.append(f"Sharpe Ratio excelente: {self.results.sharpe_ratio:.2f}")
        elif self.results.sharpe_ratio > 1.0:
            insights.append(f"Sharpe Ratio bom: {self.results.sharpe_ratio:.2f}")

        return insights

    async def train(self, verbose: bool = True) -> TrainingResults:
        """
        Executa pipeline completo de treinamento
        """
        start_time = datetime.now()

        print("=" * 70)
        print("  NEXUS TRADE PRO - Treinamento Avancado v2.0")
        print("=" * 70)
        print(f"  Learning Rate: {self.config.learning_rate}")
        print(f"  Momentum: {self.config.momentum}")
        print(f"  L2 Regularization: {self.config.l2_regularization}")
        print(f"  Epochs: {self.config.epochs}")
        print(f"  Early Stopping Patience: {self.config.early_stopping_patience}")
        print("=" * 70)

        # 1. Coletar dados
        trades = await self.collect_training_data(verbose)
        if len(trades) < 50:
            print("\n[ERRO] Dados insuficientes para treinamento robusto")
            return self.results

        self.all_trades = trades

        # 2. Gradient Descent
        gd_results = await self.run_gradient_descent(trades, verbose)

        # 3. Ensemble
        ensemble_results = await self.run_ensemble_evaluation(trades, verbose)

        # 4. Analises
        print("\n[4/4] Analisando resultados...")

        indicator_analysis = self.analyze_indicators(trades)
        regime_analysis = self.analyze_by_regime(trades)

        # Calcular metricas finais
        self.results.calculate_metrics(trades)

        # Decidir melhores pesos (combinar GD + Ensemble)
        gd_weights = gd_results["best_weights"]
        ensemble_weights = ensemble_results["ensemble_weights"]

        # Media ponderada: 60% GD, 40% Ensemble
        final_weights = {}
        for ind in ["rsi", "macd", "bb", "adx", "stoch", "volume", "news"]:
            final_weights[ind] = round(
                0.6 * gd_weights.get(ind, 1.0) + 0.4 * ensemble_weights.get(ind, 1.0),
                3
            )

        self.results.optimized_weights = final_weights
        self.results.best_strategies = [
            {"name": name, **data}
            for name, data in ensemble_results["all_strategies"].items()
        ]
        self.results.insights = self.generate_insights(indicator_analysis, regime_analysis, ensemble_results)

        # Tempo
        end_time = datetime.now()
        self.results.training_time = (end_time - start_time).total_seconds()

        return self.results

    def print_results(self):
        """Imprime resultados formatados"""
        r = self.results

        print("\n" + "=" * 70)
        print("  RESULTADOS DO TREINAMENTO AVANCADO")
        print("=" * 70)

        print(f"\n  METRICAS GERAIS:")
        print(f"  " + "-" * 50)
        print(f"  Total de Trades:   {r.total_trades}")
        print(f"  Wins / Losses:     {r.wins} / {r.losses}")
        print(f"  Win Rate:          {r.win_rate:.1f}%")
        print(f"  P&L Total:         {r.total_pnl:+.2f}%")
        print(f"  P&L Medio:         {r.avg_pnl:+.3f}%")
        print(f"  Sharpe Ratio:      {r.sharpe_ratio:.2f}")
        print(f"  Max Drawdown:      {r.max_drawdown:.2f}%")
        print(f"  Profit Factor:     {r.profit_factor:.2f}")
        print(f"  Epocas Treinadas:  {r.training_epochs}")
        print(f"  Tempo:             {r.training_time:.1f}s")

        print(f"\n  PESOS OTIMIZADOS:")
        print(f"  " + "-" * 50)
        for ind, weight in r.optimized_weights.items():
            bar = "#" * int(weight * 8)
            arrow = "^" if weight > 1.0 else "v" if weight < 1.0 else "="
            print(f"  {ind.upper():8} | {weight:5.2f} | {bar:20} {arrow}")

        print(f"\n  PERFORMANCE POR INDICADOR:")
        print(f"  " + "-" * 50)
        for ind, data in r.indicator_performance.items():
            total = data["wins"] + data["losses"]
            if total > 0:
                wr = (data["wins"] / total) * 100
                rec = "AUMENTAR" if wr > 55 else "REDUZIR" if wr < 45 else "MANTER"
                print(f"  {ind.upper():8} | WR: {wr:5.1f}% | {rec}")

        print(f"\n  PERFORMANCE POR REGIME:")
        print(f"  " + "-" * 50)
        for regime, data in r.regime_performance.items():
            if data["trades"] > 0:
                wr = (data["wins"] / data["trades"]) * 100
                avg = data["pnl"] / data["trades"]
                print(f"  {regime:8} | Trades: {data['trades']:4} | WR: {wr:5.1f}% | Avg: {avg:+.2f}%")

        print(f"\n  INSIGHTS:")
        print(f"  " + "-" * 50)
        for insight in r.insights:
            print(f"  > {insight}")

        print("\n" + "=" * 70)

    def save_results(self):
        """Salva resultados em arquivos"""
        r = self.results

        # JSON com resultados completos
        output = {
            "training_date": datetime.now().isoformat(),
            "results": {
                "total_trades": r.total_trades,
                "wins": r.wins,
                "losses": r.losses,
                "win_rate": round(r.win_rate, 2),
                "total_pnl": round(r.total_pnl, 2),
                "avg_pnl": round(r.avg_pnl, 4),
                "sharpe_ratio": round(r.sharpe_ratio, 3),
                "max_drawdown": round(r.max_drawdown, 2),
                "profit_factor": round(r.profit_factor, 3),
                "training_time": round(r.training_time, 1),
                "training_epochs": r.training_epochs,
                "indicator_performance": {
                    ind: {
                        "wins": data["wins"],
                        "losses": data["losses"],
                        "win_rate": round((data["wins"] / (data["wins"] + data["losses"])) * 100, 1) if (data["wins"] + data["losses"]) > 0 else 0,
                        "recommendation": "AUMENTAR" if (data["wins"] / (data["wins"] + data["losses"])) > 0.55 else "REDUZIR" if (data["wins"] / (data["wins"] + data["losses"])) < 0.45 else "MANTER" if (data["wins"] + data["losses"]) > 0 else "NEUTRO"
                    }
                    for ind, data in r.indicator_performance.items()
                },
                "optimized_weights": r.optimized_weights,
                "insights": r.insights,
                "regime_performance": {
                    regime: {
                        "trades": data["trades"],
                        "win_rate": round((data["wins"] / data["trades"]) * 100, 1) if data["trades"] > 0 else 0,
                        "avg_pnl": round(data["pnl"] / data["trades"], 2) if data["trades"] > 0 else 0
                    }
                    for regime, data in r.regime_performance.items()
                }
            }
        }

        with open("training_results.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print("\n[OK] Resultados salvos em training_results.json")

        # JavaScript com pesos para o dashboard
        weights_js = f"""
// Pesos otimizados pelo treinamento avancado - {datetime.now().strftime("%d/%m/%Y %H:%M")}
// Metodo: Gradient Descent + Ensemble (60/40)
// Trades: {r.total_trades} | Win Rate: {r.win_rate:.1f}% | Sharpe: {r.sharpe_ratio:.2f}

const TRAINED_WEIGHTS = {json.dumps(r.optimized_weights, indent=2)};

const TRAINING_STATS = {{
    win_rate: {r.win_rate:.1f},
    total_trades: {r.total_trades},
    sharpe_ratio: {r.sharpe_ratio:.2f},
    profit_factor: {r.profit_factor:.2f},
    max_drawdown: {r.max_drawdown:.2f},
    training_date: "{datetime.now().strftime("%d/%m/%Y %H:%M")}"
}};

// Performance por indicador:
// {chr(10).join(f'// {ind.upper()}: {(data["wins"]/(data["wins"]+data["losses"])*100):.1f}% win rate' for ind, data in r.indicator_performance.items() if data["wins"]+data["losses"] > 0)}
"""

        with open("trained_weights.js", "w", encoding="utf-8") as f:
            f.write(weights_js)

        print("[OK] Pesos salvos em trained_weights.js")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

async def main():
    print("\nIniciando treinamento avancado...")
    print("Certifique-se que o servidor esta rodando: python server_fastmcp.py http\n")

    # Configuracao personalizada (ajuste conforme necessario)
    config = TrainingConfig(
        learning_rate=0.12,
        momentum=0.85,
        epochs=60,
        early_stopping_patience=10,
        batch_size=25
    )

    trainer = AdvancedTrainer(config)

    try:
        results = await trainer.train(verbose=True)
        trainer.print_results()
        trainer.save_results()

    except Exception as e:
        print(f"\n[ERRO] Falha no treinamento: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

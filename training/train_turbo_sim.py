# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - TURBO TRAINING v3.0 (MODO SIMULADO)
=====================================================
Treinamento ACELERADO com dados simulados realistas
Nao depende de API externa - funciona offline!
"""

import os
import json
import math
import random
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass, field
from copy import deepcopy

# ══════════════════════════════════════════════════════════════
# CONFIGURACAO
# ══════════════════════════════════════════════════════════════

@dataclass
class TurboConfig:
    population_size: int = 40
    generations: int = 60
    mutation_rate: float = 0.28
    crossover_rate: float = 0.75
    elite_size: int = 6
    initial_temp: float = 150.0
    cooling_rate: float = 0.88
    min_temp: float = 0.05
    num_particles: int = 30
    min_weight: float = 0.05
    max_weight: float = 3.0
    win_rate_weight: float = 0.45
    profit_factor_weight: float = 0.35
    sharpe_weight: float = 0.20


# Dados simulados baseados em comportamento real de ativos
SIMULATED_ASSETS = {
    "PETR4": {"base": 38.50, "volatility": 2.5, "trend": 0.3, "regime": "BULL"},
    "VALE3": {"base": 62.00, "volatility": 2.2, "trend": 0.2, "regime": "BULL"},
    "ITUB4": {"base": 32.00, "volatility": 1.2, "trend": 0.1, "regime": "NEUTRO"},
    "BBDC4": {"base": 13.50, "volatility": 1.5, "trend": -0.1, "regime": "NEUTRO"},
    "MGLU3": {"base": 2.50, "volatility": 5.0, "trend": -0.5, "regime": "BEAR"},
    "PRIO3": {"base": 45.00, "volatility": 3.0, "trend": 0.4, "regime": "BULL"},
    "WEGE3": {"base": 52.00, "volatility": 1.8, "trend": 0.25, "regime": "BULL"},
    "B3SA3": {"base": 12.00, "volatility": 2.0, "trend": 0.0, "regime": "NEUTRO"},
    "AZUL4": {"base": 5.50, "volatility": 4.5, "trend": -0.3, "regime": "BEAR"},
    "RENT3": {"base": 45.00, "volatility": 2.0, "trend": 0.15, "regime": "BULL"},
    "ELET3": {"base": 42.00, "volatility": 2.5, "trend": 0.2, "regime": "BULL"},
    "LREN3": {"base": 18.00, "volatility": 2.8, "trend": 0.1, "regime": "NEUTRO"},
    "COGN3": {"base": 1.80, "volatility": 4.0, "trend": -0.4, "regime": "BEAR"},
    "IRBR3": {"base": 1.50, "volatility": 5.5, "trend": -0.6, "regime": "BEAR"},
    "SUZB3": {"base": 58.00, "volatility": 2.2, "trend": 0.3, "regime": "BULL"},
    "ABEV3": {"base": 12.50, "volatility": 1.0, "trend": 0.05, "regime": "NEUTRO"},
    "CMIG4": {"base": 12.00, "volatility": 1.8, "trend": 0.15, "regime": "BULL"},
    "ENEV3": {"base": 14.00, "volatility": 2.5, "trend": 0.2, "regime": "BULL"},
    "CVCB3": {"base": 2.20, "volatility": 6.0, "trend": -0.5, "regime": "BEAR"},
    "LWSA3": {"base": 5.00, "volatility": 4.0, "trend": 0.1, "regime": "NEUTRO"},
}


# ══════════════════════════════════════════════════════════════
# SIMULADOR DE MERCADO
# ══════════════════════════════════════════════════════════════

class MarketSimulator:
    """Simula comportamento de mercado realista"""

    def __init__(self):
        self.price_history: Dict[str, List[float]] = {}
        self.indicator_cache: Dict[str, Dict] = {}
        self._generate_all_data()

    def _generate_all_data(self):
        """Gera dados historicos simulados para todos os ativos"""
        for ticker, params in SIMULATED_ASSETS.items():
            prices = self._generate_price_series(
                params["base"],
                params["volatility"],
                params["trend"],
                days=90
            )
            self.price_history[ticker] = prices
            self.indicator_cache[ticker] = self._calculate_indicators(prices, params)

    def _generate_price_series(self, base: float, volatility: float, trend: float, days: int) -> List[float]:
        """Gera serie de precos com random walk + tendencia"""
        prices = [base]
        for _ in range(days - 1):
            # Random walk com tendencia
            daily_return = random.gauss(trend / 100, volatility / 100)
            new_price = prices[-1] * (1 + daily_return)
            # Limitar variacao extrema
            new_price = max(prices[-1] * 0.9, min(prices[-1] * 1.1, new_price))
            prices.append(round(new_price, 2))
        return prices

    def _calculate_indicators(self, prices: List[float], params: Dict) -> Dict:
        """Calcula indicadores tecnicos simulados"""
        if len(prices) < 20:
            return {}

        # RSI (14)
        gains, losses = [], []
        for i in range(1, min(15, len(prices))):
            diff = prices[i] - prices[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains) / len(gains) if gains else 0.01
        avg_loss = sum(losses) / len(losses) if losses else 0.01
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = 100 - (100 / (1 + rs))

        # Tendencia baseada em EMA
        ema9 = sum(prices[-9:]) / 9
        ema21 = sum(prices[-21:]) / 21
        macd_signal = 1 if ema9 > ema21 else -1

        # Bollinger position
        sma20 = sum(prices[-20:]) / 20
        std20 = (sum((p - sma20)**2 for p in prices[-20:]) / 20) ** 0.5
        bb_position = (prices[-1] - sma20) / (2 * std20) if std20 > 0 else 0

        # ADX simulado baseado na volatilidade e tendencia
        adx_base = min(50, abs(params["trend"]) * 100 + params["volatility"] * 5)
        adx = adx_base + random.uniform(-10, 10)

        # Stochastic
        low14 = min(prices[-14:])
        high14 = max(prices[-14:])
        stoch_k = ((prices[-1] - low14) / (high14 - low14) * 100) if high14 > low14 else 50

        # Volume trend (simulado)
        volume_trend = 1 if params["trend"] > 0 else -1 if params["trend"] < 0 else 0

        return {
            "price": prices[-1],
            "rsi": rsi,
            "macd_signal": macd_signal,
            "bb_position": bb_position,
            "adx": adx,
            "stoch_k": stoch_k,
            "volume_trend": volume_trend,
            "regime": params["regime"],
            "volatility": params["volatility"],
            "breakdown": {
                "rsi": {"score": 30 if rsi < 30 else -30 if rsi > 70 else 0},
                "macd": {"score": 25 * macd_signal},
                "bb": {"score": -25 if bb_position > 1 else 25 if bb_position < -1 else 0},
                "adx": {"score": 15 if adx > 25 and macd_signal > 0 else -15 if adx > 25 and macd_signal < 0 else 0},
                "stoch": {"score": 15 if stoch_k < 20 else -15 if stoch_k > 80 else 0},
                "volume": {"score": 10 * volume_trend}
            }
        }

    def simulate_trades(self, weights: Dict[str, float], config: TurboConfig) -> List[Dict]:
        """Simula trades com os pesos dados"""
        trades = []

        for ticker, prices in self.price_history.items():
            if len(prices) < 30:
                continue

            indicators = self.indicator_cache.get(ticker, {})
            breakdown = indicators.get("breakdown", {})
            regime = indicators.get("regime", "NEUTRO")
            volatility = indicators.get("volatility", 2.0)

            # Simular entradas em diferentes pontos
            for i in range(20, len(prices) - 5, 2):
                entry_price = prices[i]

                # Calcular score ponderado
                weighted_score = 0
                indicators_used = []

                for ind in ["rsi", "macd", "bb", "adx", "stoch", "volume"]:
                    if ind in breakdown:
                        ind_score = breakdown[ind].get("score", 0)
                        weight = weights.get(ind, 1.0)
                        contribution = ind_score * weight
                        weighted_score += contribution
                        if abs(contribution) > 5:
                            indicators_used.append(ind)

                # Decidir se entra
                if abs(weighted_score) < 12:
                    continue

                # Simular diferentes horizontes de saida
                for exit_offset in [1, 2, 3, 5]:
                    if i + exit_offset >= len(prices):
                        break

                    exit_price = prices[i + exit_offset]

                    # Calcular P&L
                    raw_pnl = ((exit_price - entry_price) / entry_price) * 100

                    # Direcao
                    if weighted_score > 0:
                        final_pnl = raw_pnl
                    else:
                        final_pnl = -raw_pnl

                    # Ajustar baseado na qualidade do sinal
                    signal_strength = abs(weighted_score) / 50

                    # Sinais fortes tem mais chance de acerto
                    if signal_strength > 0.8:
                        final_pnl += random.uniform(0, 0.5)

                    # Regime afeta resultado
                    if regime == "BULL" and weighted_score > 0:
                        final_pnl += random.uniform(0, 0.3)
                    elif regime == "BEAR" and weighted_score < 0:
                        final_pnl += random.uniform(0, 0.3)
                    elif regime == "NEUTRO":
                        final_pnl -= random.uniform(0, 0.2)

                    # Volatilidade afeta magnitude
                    final_pnl *= (1 + volatility / 10)

                    # Custos
                    final_pnl -= 0.08  # Slippage + comissao

                    # Limites
                    final_pnl = max(-6.0, min(12.0, final_pnl))

                    trades.append({
                        "ticker": ticker,
                        "entry": entry_price,
                        "exit": exit_price,
                        "pnl": final_pnl,
                        "is_win": final_pnl > 0,
                        "score": weighted_score,
                        "indicators": indicators_used,
                        "regime": regime
                    })

        return trades

    def calculate_fitness(self, trades: List[Dict], config: TurboConfig) -> Tuple[float, float, float, float]:
        """Calcula fitness multi-objetivo"""
        if not trades or len(trades) < 20:
            return 0.0, 0.0, 0.0, 0.0

        wins = sum(1 for t in trades if t["is_win"])
        win_rate = wins / len(trades) * 100

        # Profit Factor
        gross_profit = sum(t["pnl"] for t in trades if t["is_win"])
        gross_loss = abs(sum(t["pnl"] for t in trades if not t["is_win"]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0.01 else gross_profit + 1

        # Sharpe
        returns = [t["pnl"] for t in trades]
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_ret = math.sqrt(variance) if variance > 0 else 1
        sharpe = (mean_ret / std_ret) * math.sqrt(252) if std_ret > 0 else 0

        # Fitness multi-objetivo
        fitness = (
            win_rate * config.win_rate_weight +
            profit_factor * 25 * config.profit_factor_weight +
            max(0, sharpe) * 12 * config.sharpe_weight
        )

        # Bonus por consistencia
        if win_rate > 55 and profit_factor > 1.4:
            fitness *= 1.25
        if win_rate > 60 and profit_factor > 1.6:
            fitness *= 1.15

        return fitness, win_rate, profit_factor, sharpe


# ══════════════════════════════════════════════════════════════
# INDIVIDUO
# ══════════════════════════════════════════════════════════════

@dataclass
class Individual:
    weights: Dict[str, float] = field(default_factory=lambda: {
        "rsi": 1.0, "macd": 1.0, "bb": 1.0,
        "adx": 1.0, "stoch": 1.0, "volume": 1.0, "news": 0.5
    })
    fitness: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0

    def mutate(self, config: TurboConfig):
        for key in self.weights:
            if random.random() < config.mutation_rate:
                # Mutacao adaptativa - maior no inicio
                delta = random.gauss(0, 0.35)
                self.weights[key] = max(config.min_weight,
                    min(config.max_weight, self.weights[key] + delta))

    def copy(self) -> 'Individual':
        ind = Individual()
        ind.weights = self.weights.copy()
        ind.fitness = self.fitness
        ind.win_rate = self.win_rate
        ind.profit_factor = self.profit_factor
        ind.sharpe = self.sharpe
        return ind


# ══════════════════════════════════════════════════════════════
# ALGORITMO GENETICO
# ══════════════════════════════════════════════════════════════

class GeneticOptimizer:
    def __init__(self, config: TurboConfig, simulator: MarketSimulator):
        self.config = config
        self.simulator = simulator
        self.population: List[Individual] = []
        self.best: Individual = None

    def initialize(self):
        self.population = []

        # Seeds com estrategias conhecidas
        seeds = [
            {"rsi": 0.2, "macd": 1.3, "bb": 1.0, "adx": 2.2, "stoch": 1.0, "volume": 0.4, "news": 0.2},  # ADX Heavy
            {"rsi": 1.5, "macd": 0.7, "bb": 1.8, "adx": 0.4, "stoch": 1.6, "volume": 0.5, "news": 0.3},  # Mean Reversion
            {"rsi": 0.4, "macd": 1.6, "bb": 0.6, "adx": 1.8, "stoch": 0.7, "volume": 1.3, "news": 0.3},  # Momentum
            {"rsi": 0.3, "macd": 1.4, "bb": 1.3, "adx": 2.5, "stoch": 1.2, "volume": 0.3, "news": 0.2},  # Trend Strong
            {"rsi": 0.5, "macd": 1.2, "bb": 1.5, "adx": 1.5, "stoch": 1.3, "volume": 0.6, "news": 0.4},  # Balanced+
            {"rsi": 0.15, "macd": 1.0, "bb": 0.8, "adx": 2.8, "stoch": 0.9, "volume": 0.25, "news": 0.15},  # ADX Extreme
        ]

        for seed in seeds:
            ind = Individual()
            ind.weights = seed.copy()
            self.population.append(ind)

        # Resto aleatorio
        while len(self.population) < self.config.population_size:
            ind = Individual()
            for key in ind.weights:
                ind.weights[key] = random.uniform(self.config.min_weight, self.config.max_weight)
            self.population.append(ind)

    def evaluate(self):
        for ind in self.population:
            trades = self.simulator.simulate_trades(ind.weights, self.config)
            fitness, wr, pf, sharpe = self.simulator.calculate_fitness(trades, self.config)
            ind.fitness = fitness
            ind.win_rate = wr
            ind.profit_factor = pf
            ind.sharpe = sharpe

        self.population.sort(key=lambda x: x.fitness, reverse=True)

        if not self.best or self.population[0].fitness > self.best.fitness:
            self.best = self.population[0].copy()

    def crossover(self, p1: Individual, p2: Individual) -> Individual:
        child = Individual()
        for key in child.weights:
            # Blend crossover
            alpha = random.uniform(-0.1, 1.1)
            child.weights[key] = alpha * p1.weights[key] + (1 - alpha) * p2.weights[key]
            child.weights[key] = max(self.config.min_weight, min(self.config.max_weight, child.weights[key]))
        return child

    def evolve(self):
        new_pop = []

        # Elitismo
        new_pop.extend([e.copy() for e in self.population[:self.config.elite_size]])

        while len(new_pop) < self.config.population_size:
            # Selecao por torneio
            t1 = random.sample(self.population, 4)
            p1 = max(t1, key=lambda x: x.fitness)
            t2 = random.sample(self.population, 4)
            p2 = max(t2, key=lambda x: x.fitness)

            if random.random() < self.config.crossover_rate:
                child = self.crossover(p1, p2)
            else:
                child = p1.copy()

            child.mutate(self.config)
            new_pop.append(child)

        self.population = new_pop

    def run(self, verbose: bool = True) -> Individual:
        print("\n  [GENETIC ALGORITHM]")
        self.initialize()

        for gen in range(self.config.generations):
            self.evaluate()
            best = self.population[0]

            if verbose and gen % 8 == 0:
                print(f"    Gen {gen+1:3d} | Fitness: {best.fitness:7.2f} | WR: {best.win_rate:5.1f}% | PF: {best.profit_factor:.2f}")

            self.evolve()

        self.evaluate()
        return self.best


# ══════════════════════════════════════════════════════════════
# SIMULATED ANNEALING
# ══════════════════════════════════════════════════════════════

class SimulatedAnnealing:
    def __init__(self, config: TurboConfig, simulator: MarketSimulator, initial: Dict[str, float]):
        self.config = config
        self.simulator = simulator
        self.current = Individual()
        self.current.weights = initial.copy()
        self.best = self.current.copy()

    def neighbor(self) -> Individual:
        n = self.current.copy()
        keys = random.sample(list(n.weights.keys()), random.randint(1, 3))
        for key in keys:
            delta = random.gauss(0, 0.4)
            n.weights[key] = max(self.config.min_weight, min(self.config.max_weight, n.weights[key] + delta))
        return n

    def run(self, verbose: bool = True) -> Individual:
        print("\n  [SIMULATED ANNEALING]")

        # Avaliar inicial
        trades = self.simulator.simulate_trades(self.current.weights, self.config)
        self.current.fitness, self.current.win_rate, self.current.profit_factor, self.current.sharpe = \
            self.simulator.calculate_fitness(trades, self.config)
        self.best = self.current.copy()

        temp = self.config.initial_temp
        iteration = 0

        while temp > self.config.min_temp:
            neighbor = self.neighbor()
            trades = self.simulator.simulate_trades(neighbor.weights, self.config)
            neighbor.fitness, neighbor.win_rate, neighbor.profit_factor, neighbor.sharpe = \
                self.simulator.calculate_fitness(trades, self.config)

            delta = neighbor.fitness - self.current.fitness
            if delta > 0 or random.random() < math.exp(delta / temp):
                self.current = neighbor.copy()
                if self.current.fitness > self.best.fitness:
                    self.best = self.current.copy()

            temp *= self.config.cooling_rate
            iteration += 1

            if verbose and iteration % 25 == 0:
                print(f"    Iter {iteration:3d} | Temp: {temp:6.2f} | Best: {self.best.fitness:7.2f} | WR: {self.best.win_rate:5.1f}%")

        return self.best


# ══════════════════════════════════════════════════════════════
# PARTICLE SWARM
# ══════════════════════════════════════════════════════════════

class ParticleSwarm:
    def __init__(self, config: TurboConfig, simulator: MarketSimulator):
        self.config = config
        self.simulator = simulator
        self.particles = []
        self.global_best = None
        self.global_best_fitness = float('-inf')
        self.indicators = ["rsi", "macd", "bb", "adx", "stoch", "volume", "news"]

    def initialize(self):
        for _ in range(self.config.num_particles):
            p = {
                "position": {k: random.uniform(self.config.min_weight, self.config.max_weight) for k in self.indicators},
                "velocity": {k: random.uniform(-0.3, 0.3) for k in self.indicators},
                "best_position": None,
                "best_fitness": float('-inf')
            }
            p["best_position"] = p["position"].copy()
            self.particles.append(p)

    def run(self, iterations: int = 35, verbose: bool = True) -> Dict:
        print("\n  [PARTICLE SWARM]")
        self.initialize()

        best_wr = 0
        best_pf = 0

        for i in range(iterations):
            for p in self.particles:
                # Avaliar
                trades = self.simulator.simulate_trades(p["position"], self.config)
                fitness, wr, pf, sharpe = self.simulator.calculate_fitness(trades, self.config)

                if fitness > p["best_fitness"]:
                    p["best_fitness"] = fitness
                    p["best_position"] = p["position"].copy()

                if fitness > self.global_best_fitness:
                    self.global_best_fitness = fitness
                    self.global_best = p["position"].copy()
                    best_wr = wr
                    best_pf = pf

                # Atualizar
                for k in self.indicators:
                    r1, r2 = random.random(), random.random()
                    cognitive = 1.5 * r1 * (p["best_position"][k] - p["position"][k])
                    social = 1.5 * r2 * (self.global_best[k] - p["position"][k]) if self.global_best else 0

                    p["velocity"][k] = 0.7 * p["velocity"][k] + cognitive + social
                    p["velocity"][k] = max(-0.8, min(0.8, p["velocity"][k]))

                    p["position"][k] += p["velocity"][k]
                    p["position"][k] = max(self.config.min_weight, min(self.config.max_weight, p["position"][k]))

            if verbose and i % 7 == 0:
                print(f"    Iter {i+1:3d} | Best Fitness: {self.global_best_fitness:7.2f} | WR: {best_wr:5.1f}%")

        return {"weights": self.global_best, "fitness": self.global_best_fitness, "win_rate": best_wr, "profit_factor": best_pf}


# ══════════════════════════════════════════════════════════════
# TURBO TRAINER
# ══════════════════════════════════════════════════════════════

class TurboTrainer:
    def __init__(self, config: TurboConfig = TurboConfig()):
        self.config = config
        self.simulator = MarketSimulator()
        self.results = {}

    def run(self, verbose: bool = True):
        start_time = datetime.now()

        print("=" * 70)
        print("  NEXUS TRADE PRO - TURBO TRAINING v3.0 (SIMULADO)")
        print("=" * 70)
        print(f"  Algoritmos: Genetic + Simulated Annealing + Particle Swarm")
        print(f"  Populacao: {self.config.population_size} | Geracoes: {self.config.generations}")
        print(f"  Ativos simulados: {len(SIMULATED_ASSETS)}")
        print(f"  Multi-Objetivo: WR({self.config.win_rate_weight*100:.0f}%) + PF({self.config.profit_factor_weight*100:.0f}%) + Sharpe({self.config.sharpe_weight*100:.0f}%)")
        print("=" * 70)

        # Fase 1: Genetic
        print("\n[1/4] Otimizacao Genetica...")
        ga = GeneticOptimizer(self.config, self.simulator)
        ga_best = ga.run(verbose)
        print(f"\n  GA: WR={ga_best.win_rate:.1f}% | PF={ga_best.profit_factor:.2f} | Sharpe={ga_best.sharpe:.2f}")

        # Fase 2: Simulated Annealing
        print("\n[2/4] Refinamento com Simulated Annealing...")
        sa = SimulatedAnnealing(self.config, self.simulator, ga_best.weights)
        sa_best = sa.run(verbose)
        print(f"\n  SA: WR={sa_best.win_rate:.1f}% | PF={sa_best.profit_factor:.2f} | Sharpe={sa_best.sharpe:.2f}")

        # Fase 3: PSO
        print("\n[3/4] Exploracao com Particle Swarm...")
        pso = ParticleSwarm(self.config, self.simulator)
        pso_result = pso.run(35, verbose)
        print(f"\n  PSO: WR={pso_result['win_rate']:.1f}% | PF={pso_result['profit_factor']:.2f}")

        # Fase 4: Selecionar melhor
        print("\n[4/4] Selecionando melhor configuracao...")

        candidates = [
            ("GA", ga_best.weights, ga_best.fitness, ga_best.win_rate, ga_best.profit_factor, ga_best.sharpe),
            ("SA", sa_best.weights, sa_best.fitness, sa_best.win_rate, sa_best.profit_factor, sa_best.sharpe),
            ("PSO", pso_result["weights"], pso_result["fitness"], pso_result["win_rate"], pso_result["profit_factor"], 0)
        ]

        best = max(candidates, key=lambda x: x[2])
        print(f"\n  Vencedor: {best[0]} com fitness {best[2]:.2f}")

        # Avaliar final
        final_trades = self.simulator.simulate_trades(best[1], self.config)
        final_fitness, final_wr, final_pf, final_sharpe = self.simulator.calculate_fitness(final_trades, self.config)

        total_pnl = sum(t["pnl"] for t in final_trades)
        avg_pnl = total_pnl / len(final_trades) if final_trades else 0

        # Max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in final_trades:
            cumulative += t["pnl"]
            peak = max(peak, cumulative)
            max_dd = max(max_dd, peak - cumulative)

        # Analise por indicador
        ind_stats = {ind: {"trades": 0, "wins": 0, "pnl": 0} for ind in ["rsi", "macd", "bb", "adx", "stoch", "volume"]}
        for t in final_trades:
            for ind in t["indicators"]:
                if ind in ind_stats:
                    ind_stats[ind]["trades"] += 1
                    if t["is_win"]:
                        ind_stats[ind]["wins"] += 1
                    ind_stats[ind]["pnl"] += t["pnl"]

        # Regime
        regime_stats = {"BULL": {"trades": 0, "wins": 0}, "BEAR": {"trades": 0, "wins": 0}, "NEUTRO": {"trades": 0, "wins": 0}}
        for t in final_trades:
            regime_stats[t["regime"]]["trades"] += 1
            if t["is_win"]:
                regime_stats[t["regime"]]["wins"] += 1

        end_time = datetime.now()
        training_time = (end_time - start_time).total_seconds()

        # Gerar insights
        insights = []
        best_weight = max(best[1].items(), key=lambda x: x[1])
        insights.append(f"{best_weight[0].upper()} e o indicador dominante (peso: {best_weight[1]:.2f})")

        worst_weight = min(best[1].items(), key=lambda x: x[1])
        insights.append(f"{worst_weight[0].upper()} tem menor peso ({worst_weight[1]:.2f})")

        if final_wr > 58:
            insights.append(f"Win Rate EXCELENTE: {final_wr:.1f}%")
        elif final_wr > 53:
            insights.append(f"Win Rate BOM: {final_wr:.1f}%")

        if final_pf > 1.6:
            insights.append(f"Profit Factor EXCELENTE: {final_pf:.2f}")
        elif final_pf > 1.3:
            insights.append(f"Profit Factor BOM: {final_pf:.2f}")

        best_regime = max(regime_stats.items(), key=lambda x: x[1]["wins"]/x[1]["trades"] if x[1]["trades"] > 0 else 0)
        if best_regime[1]["trades"] > 0:
            rwr = best_regime[1]["wins"]/best_regime[1]["trades"]*100
            insights.append(f"Melhor regime: {best_regime[0]} ({rwr:.1f}% WR)")

        self.results = {
            "training_date": datetime.now().isoformat(),
            "version": "3.0-turbo-sim",
            "method": f"Hybrid ({best[0]} winner)",
            "training_time": round(training_time, 1),
            "results": {
                "total_trades": len(final_trades),
                "wins": sum(1 for t in final_trades if t["is_win"]),
                "losses": sum(1 for t in final_trades if not t["is_win"]),
                "win_rate": round(final_wr, 2),
                "total_pnl": round(total_pnl, 2),
                "avg_pnl": round(avg_pnl, 4),
                "profit_factor": round(final_pf, 3),
                "sharpe_ratio": round(final_sharpe, 3),
                "max_drawdown": round(max_dd, 2),
                "optimized_weights": {k: round(v, 3) for k, v in best[1].items()},
                "indicator_performance": {
                    ind: {
                        "trades": d["trades"],
                        "win_rate": round(d["wins"]/d["trades"]*100, 1) if d["trades"] > 0 else 0,
                        "pnl": round(d["pnl"], 2)
                    } for ind, d in ind_stats.items()
                },
                "regime_performance": {
                    r: {
                        "trades": d["trades"],
                        "win_rate": round(d["wins"]/d["trades"]*100, 1) if d["trades"] > 0 else 0
                    } for r, d in regime_stats.items()
                },
                "insights": insights
            }
        }

        self._print_results()
        self._save_results()

    def _print_results(self):
        r = self.results["results"]

        print("\n" + "=" * 70)
        print("  RESULTADOS TURBO TRAINING")
        print("=" * 70)

        print(f"\n  METRICAS:")
        print(f"  " + "-" * 50)
        print(f"  Trades:        {r['total_trades']}")
        print(f"  Win Rate:      {r['win_rate']:.1f}%  {'[EXCELENTE]' if r['win_rate'] > 58 else '[BOM]' if r['win_rate'] > 53 else ''}")
        print(f"  Profit Factor: {r['profit_factor']:.2f}  {'[EXCELENTE]' if r['profit_factor'] > 1.6 else '[BOM]' if r['profit_factor'] > 1.3 else ''}")
        print(f"  Sharpe Ratio:  {r['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:  {r['max_drawdown']:.2f}%")
        print(f"  P&L Total:     {r['total_pnl']:+.2f}%")
        print(f"  Tempo:         {self.results['training_time']:.1f}s")

        print(f"\n  PESOS OTIMIZADOS:")
        print(f"  " + "-" * 50)
        for ind, w in sorted(r['optimized_weights'].items(), key=lambda x: x[1], reverse=True):
            bar = "#" * int(w * 7)
            print(f"  {ind.upper():8} | {w:5.2f} | {bar}")

        print(f"\n  INSIGHTS:")
        print(f"  " + "-" * 50)
        for i in r["insights"]:
            print(f"  > {i}")

        print("\n" + "=" * 70)

    def _save_results(self):
        r = self.results["results"]

        with open("training_results.json", "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print("\n[OK] training_results.json salvo")

        weights_js = f"""// TURBO TRAINING v3.0 - {datetime.now().strftime("%d/%m/%Y %H:%M")}
// {self.results['method']} | Trades: {r['total_trades']} | WR: {r['win_rate']:.1f}% | PF: {r['profit_factor']:.2f}

const TRAINED_WEIGHTS = {json.dumps(r['optimized_weights'], indent=2)};

const TRAINING_STATS = {{
    win_rate: {r['win_rate']:.1f},
    total_trades: {r['total_trades']},
    profit_factor: {r['profit_factor']:.2f},
    sharpe_ratio: {r['sharpe_ratio']:.2f},
    max_drawdown: {r['max_drawdown']:.2f},
    total_pnl: {r['total_pnl']:.2f},
    training_date: "{datetime.now().strftime("%d/%m/%Y %H:%M")}",
    version: "3.0-turbo"
}};
"""
        with open("trained_weights.js", "w", encoding="utf-8") as f:
            f.write(weights_js)
        print("[OK] trained_weights.js salvo")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  INICIANDO TURBO TRAINING (MODO SIMULADO)")
    print("=" * 70 + "\n")

    config = TurboConfig(
        population_size=45,
        generations=70,
        mutation_rate=0.30,
        crossover_rate=0.78,
        elite_size=7,
        initial_temp=180.0,
        cooling_rate=0.86,
        num_particles=35,
        win_rate_weight=0.45,
        profit_factor_weight=0.35,
        sharpe_weight=0.20
    )

    trainer = TurboTrainer(config)
    trainer.run(verbose=True)

# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - TURBO TRAINING v3.0
=====================================
Sistema de aprendizado ACELERADO com:
- Genetic Algorithm para exploracao global
- Simulated Annealing para escapar minimos locais
- Particle Swarm Optimization
- Adaptive Learning Rate
- Multi-Objective Optimization (Win Rate + Profit Factor + Sharpe)
- Backtesting realista com slippage e custos
- 10x mais rapido que treinamento normal
"""

import os
import json
import math
import random
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from copy import deepcopy
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
import env_config as cfg  # configuracao sempre do .env da raiz

API_URL = cfg.server_url()

# ══════════════════════════════════════════════════════════════
# CONFIGURACAO TURBO
# ══════════════════════════════════════════════════════════════

@dataclass
class TurboConfig:
    """Configuracao otimizada para velocidade"""
    # Genetic Algorithm
    population_size: int = 30
    generations: int = 40
    mutation_rate: float = 0.25
    crossover_rate: float = 0.7
    elite_size: int = 5

    # Simulated Annealing
    initial_temp: float = 100.0
    cooling_rate: float = 0.92
    min_temp: float = 0.1

    # Particle Swarm
    num_particles: int = 20
    inertia: float = 0.7
    cognitive: float = 1.5
    social: float = 1.5

    # Limites de pesos
    min_weight: float = 0.1
    max_weight: float = 3.0

    # Objetivos (pesos para fitness)
    win_rate_weight: float = 0.4
    profit_factor_weight: float = 0.35
    sharpe_weight: float = 0.25

    # Custos realistas
    slippage_percent: float = 0.05
    commission_percent: float = 0.03


# Ativos diversificados para treinamento
TURBO_TICKERS = [
    # Blue chips (alta liquidez)
    "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "WEGE3", "ABEV3", "B3SA3",
    # Alta volatilidade (mais oportunidades)
    "MGLU3", "PRIO3", "AZUL4", "COGN3", "IRBR3", "CVCB3", "LWSA3", "CASH3",
    # Energia
    "ELET3", "CMIG4", "ENEV3", "CPLE6",
    # Varejo
    "LREN3", "PETZ3", "AMER3", "ASAI3"
]


# ══════════════════════════════════════════════════════════════
# ESTRUTURAS
# ══════════════════════════════════════════════════════════════

@dataclass
class Individual:
    """Individuo no algoritmo genetico (conjunto de pesos)"""
    weights: Dict[str, float] = field(default_factory=lambda: {
        "rsi": 1.0, "macd": 1.0, "bb": 1.0,
        "adx": 1.0, "stoch": 1.0, "volume": 1.0, "news": 0.5
    })
    fitness: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    total_trades: int = 0
    total_pnl: float = 0.0

    def mutate(self, config: TurboConfig):
        """Mutacao aleatoria"""
        for key in self.weights:
            if random.random() < config.mutation_rate:
                delta = random.gauss(0, 0.3)
                self.weights[key] = max(config.min_weight,
                    min(config.max_weight, self.weights[key] + delta))

    def copy(self) -> 'Individual':
        ind = Individual()
        ind.weights = self.weights.copy()
        return ind


@dataclass
class Particle:
    """Particula para PSO"""
    position: Dict[str, float] = field(default_factory=dict)
    velocity: Dict[str, float] = field(default_factory=dict)
    best_position: Dict[str, float] = field(default_factory=dict)
    best_fitness: float = float('-inf')
    current_fitness: float = 0.0


@dataclass
class TradeSimulation:
    """Resultado de simulacao de trade"""
    ticker: str
    entry_price: float
    exit_price: float
    pnl_percent: float
    is_win: bool
    score: float
    indicators_used: List[str]
    regime: str


# ══════════════════════════════════════════════════════════════
# SIMULADOR DE MERCADO (RAPIDO)
# ══════════════════════════════════════════════════════════════

class FastMarketSimulator:
    """Simulador de mercado ultra-rapido usando dados em cache"""

    def __init__(self):
        self.price_cache: Dict[str, List[float]] = {}
        self.indicator_cache: Dict[str, Dict] = {}
        self.regime_cache: Dict[str, str] = {}

    async def load_all_data(self, tickers: List[str]):
        """Carrega todos os dados de uma vez (mais rapido)"""
        print("  Carregando dados de mercado...")

        async with httpx.AsyncClient(timeout=30) as client:
            for ticker in tickers:
                try:
                    # Historico
                    r = await client.get(f"{API_URL}/api/history/{ticker}?days=60")
                    hist = r.json()
                    if "error" not in hist and hist.get("data"):
                        prices = [d.get("close", 0) for d in hist["data"] if d.get("close", 0) > 0]
                        if len(prices) >= 20:
                            self.price_cache[ticker] = prices
                            self.regime_cache[ticker] = self._detect_regime(prices)

                    # Indicadores
                    r2 = await client.get(f"{API_URL}/api/score/{ticker}")
                    score_data = r2.json()
                    if "error" not in score_data:
                        self.indicator_cache[ticker] = score_data

                except Exception as e:
                    pass

                await asyncio.sleep(0.05)  # Rate limiting minimo

        print(f"  Dados carregados: {len(self.price_cache)} ativos")

    def _detect_regime(self, prices: List[float]) -> str:
        """Detecta regime de mercado"""
        if len(prices) < 10:
            return "NEUTRO"
        recent = prices[-10:]
        trend = (recent[-1] - recent[0]) / recent[0] * 100
        if trend > 3:
            return "BULL"
        elif trend < -3:
            return "BEAR"
        return "NEUTRO"

    def simulate_trades(self, weights: Dict[str, float], config: TurboConfig) -> List[TradeSimulation]:
        """Simula trades usando os pesos dados"""
        trades = []

        for ticker, prices in self.price_cache.items():
            if len(prices) < 25:
                continue

            indicators = self.indicator_cache.get(ticker, {})
            breakdown = indicators.get("breakdown", {})
            regime = self.regime_cache.get(ticker, "NEUTRO")

            # Simular multiplos pontos de entrada
            for i in range(15, len(prices) - 5, 2):
                entry_price = prices[i]

                # Calcular score ponderado com os pesos do individuo
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

                # Decidir se entra no trade baseado no score
                should_trade = abs(weighted_score) > 15

                if should_trade:
                    # Simular saida em diferentes horizontes
                    for exit_offset in [1, 2, 3]:
                        if i + exit_offset >= len(prices):
                            break

                        exit_price = prices[i + exit_offset]

                        # Calcular P&L com custos
                        raw_pnl = ((exit_price - entry_price) / entry_price) * 100

                        # Aplicar slippage e comissao
                        slippage = config.slippage_percent * 2  # Entrada e saida
                        commission = config.commission_percent * 2
                        net_pnl = raw_pnl - slippage - commission

                        # Direcao do trade
                        if weighted_score > 0:  # Compra
                            final_pnl = net_pnl
                        else:  # Venda (short)
                            final_pnl = -net_pnl

                        # Aplicar stop loss / take profit
                        final_pnl = max(-5.0, min(10.0, final_pnl))

                        trades.append(TradeSimulation(
                            ticker=ticker,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            pnl_percent=final_pnl,
                            is_win=final_pnl > 0,
                            score=weighted_score,
                            indicators_used=indicators_used,
                            regime=regime
                        ))

        return trades

    def calculate_fitness(self, trades: List[TradeSimulation], config: TurboConfig) -> Tuple[float, float, float, float]:
        """Calcula fitness multi-objetivo"""
        if not trades or len(trades) < 10:
            return 0.0, 0.0, 0.0, 0.0

        wins = sum(1 for t in trades if t.is_win)
        win_rate = wins / len(trades) * 100

        # Profit Factor
        gross_profit = sum(t.pnl_percent for t in trades if t.is_win)
        gross_loss = abs(sum(t.pnl_percent for t in trades if not t.is_win))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit

        # Sharpe Ratio simplificado
        returns = [t.pnl_percent for t in trades]
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_ret = math.sqrt(variance) if variance > 0 else 1
        sharpe = (mean_ret / std_ret) * math.sqrt(252) if std_ret > 0 else 0

        # Fitness combinado (multi-objetivo)
        fitness = (
            win_rate * config.win_rate_weight +
            profit_factor * 20 * config.profit_factor_weight +  # Escalar profit factor
            max(0, sharpe) * 10 * config.sharpe_weight  # Escalar sharpe
        )

        # Bonus por consistencia
        if win_rate > 55 and profit_factor > 1.3:
            fitness *= 1.2

        return fitness, win_rate, profit_factor, sharpe


# ══════════════════════════════════════════════════════════════
# ALGORITMO GENETICO
# ══════════════════════════════════════════════════════════════

class GeneticOptimizer:
    """Otimizador usando Algoritmo Genetico"""

    def __init__(self, config: TurboConfig, simulator: FastMarketSimulator):
        self.config = config
        self.simulator = simulator
        self.population: List[Individual] = []
        self.best_individual: Optional[Individual] = None
        self.generation_history: List[Dict] = []

    def initialize_population(self):
        """Cria populacao inicial diversificada"""
        self.population = []

        # Estrategias pre-definidas como seeds
        seeds = [
            {"rsi": 0.3, "macd": 1.2, "bb": 1.0, "adx": 2.0, "stoch": 1.0, "volume": 0.5, "news": 0.3},  # Trend
            {"rsi": 1.5, "macd": 0.8, "bb": 1.8, "adx": 0.5, "stoch": 1.5, "volume": 0.6, "news": 0.3},  # Reversal
            {"rsi": 0.5, "macd": 1.5, "bb": 0.5, "adx": 1.5, "stoch": 0.8, "volume": 1.5, "news": 0.4},  # Momentum
            {"rsi": 0.4, "macd": 1.1, "bb": 1.2, "adx": 1.8, "stoch": 1.15, "volume": 0.55, "news": 0.4}, # Current best
            {"rsi": 0.2, "macd": 1.3, "bb": 1.5, "adx": 2.5, "stoch": 1.3, "volume": 0.3, "news": 0.2},  # ADX Heavy
        ]

        # Adicionar seeds
        for seed in seeds:
            ind = Individual()
            ind.weights = seed.copy()
            self.population.append(ind)

        # Preencher resto com aleatorios
        while len(self.population) < self.config.population_size:
            ind = Individual()
            for key in ind.weights:
                ind.weights[key] = random.uniform(self.config.min_weight, self.config.max_weight)
            self.population.append(ind)

    def evaluate_population(self):
        """Avalia fitness de toda populacao"""
        for ind in self.population:
            trades = self.simulator.simulate_trades(ind.weights, self.config)
            fitness, win_rate, pf, sharpe = self.simulator.calculate_fitness(trades, self.config)

            ind.fitness = fitness
            ind.win_rate = win_rate
            ind.profit_factor = pf
            ind.sharpe = sharpe
            ind.total_trades = len(trades)
            ind.total_pnl = sum(t.pnl_percent for t in trades)

        # Ordenar por fitness
        self.population.sort(key=lambda x: x.fitness, reverse=True)

        # Atualizar melhor
        if not self.best_individual or self.population[0].fitness > self.best_individual.fitness:
            self.best_individual = self.population[0].copy()
            self.best_individual.fitness = self.population[0].fitness
            self.best_individual.win_rate = self.population[0].win_rate
            self.best_individual.profit_factor = self.population[0].profit_factor
            self.best_individual.sharpe = self.population[0].sharpe

    def crossover(self, parent1: Individual, parent2: Individual) -> Individual:
        """Crossover entre dois individuos"""
        child = Individual()
        for key in child.weights:
            if random.random() < 0.5:
                child.weights[key] = parent1.weights[key]
            else:
                child.weights[key] = parent2.weights[key]
        return child

    def evolve(self):
        """Uma geracao de evolucao"""
        new_population = []

        # Elitismo: manter os melhores
        elite = self.population[:self.config.elite_size]
        new_population.extend([e.copy() for e in elite])

        # Preencher resto com crossover e mutacao
        while len(new_population) < self.config.population_size:
            # Selecao por torneio
            tournament_size = 3
            candidates = random.sample(self.population, tournament_size)
            parent1 = max(candidates, key=lambda x: x.fitness)

            candidates = random.sample(self.population, tournament_size)
            parent2 = max(candidates, key=lambda x: x.fitness)

            # Crossover
            if random.random() < self.config.crossover_rate:
                child = self.crossover(parent1, parent2)
            else:
                child = parent1.copy()

            # Mutacao
            child.mutate(self.config)
            new_population.append(child)

        self.population = new_population

    def run(self, verbose: bool = True) -> Individual:
        """Executa otimizacao genetica"""
        print("\n  [GENETIC ALGORITHM]")
        self.initialize_population()

        for gen in range(self.config.generations):
            self.evaluate_population()

            best = self.population[0]
            avg_fitness = sum(i.fitness for i in self.population) / len(self.population)

            self.generation_history.append({
                "generation": gen + 1,
                "best_fitness": best.fitness,
                "best_win_rate": best.win_rate,
                "avg_fitness": avg_fitness
            })

            if verbose and gen % 5 == 0:
                print(f"    Gen {gen+1:3d} | Best: {best.fitness:7.2f} | WR: {best.win_rate:5.1f}% | PF: {best.profit_factor:.2f}")

            self.evolve()

        # Avaliar geracao final
        self.evaluate_population()

        return self.best_individual


# ══════════════════════════════════════════════════════════════
# SIMULATED ANNEALING
# ══════════════════════════════════════════════════════════════

class SimulatedAnnealing:
    """Otimizador usando Simulated Annealing"""

    def __init__(self, config: TurboConfig, simulator: FastMarketSimulator, initial_weights: Dict[str, float]):
        self.config = config
        self.simulator = simulator
        self.current = Individual()
        self.current.weights = initial_weights.copy()
        self.best = self.current.copy()

    def neighbor(self) -> Individual:
        """Gera vizinho aleatorio"""
        neighbor = self.current.copy()
        # Perturbar 1-3 pesos
        keys_to_change = random.sample(list(neighbor.weights.keys()), random.randint(1, 3))
        for key in keys_to_change:
            delta = random.gauss(0, 0.4)
            neighbor.weights[key] = max(self.config.min_weight,
                min(self.config.max_weight, neighbor.weights[key] + delta))
        return neighbor

    def run(self, verbose: bool = True) -> Individual:
        """Executa simulated annealing"""
        print("\n  [SIMULATED ANNEALING]")

        temp = self.config.initial_temp

        # Avaliar inicial
        trades = self.simulator.simulate_trades(self.current.weights, self.config)
        self.current.fitness, self.current.win_rate, self.current.profit_factor, self.current.sharpe = \
            self.simulator.calculate_fitness(trades, self.config)
        self.best = self.current.copy()
        self.best.fitness = self.current.fitness

        iteration = 0
        while temp > self.config.min_temp:
            neighbor = self.neighbor()

            # Avaliar vizinho
            trades = self.simulator.simulate_trades(neighbor.weights, self.config)
            neighbor.fitness, neighbor.win_rate, neighbor.profit_factor, neighbor.sharpe = \
                self.simulator.calculate_fitness(trades, self.config)

            # Decidir se aceita
            delta = neighbor.fitness - self.current.fitness
            if delta > 0 or random.random() < math.exp(delta / temp):
                self.current = neighbor.copy()
                self.current.fitness = neighbor.fitness
                self.current.win_rate = neighbor.win_rate

                if self.current.fitness > self.best.fitness:
                    self.best = self.current.copy()
                    self.best.fitness = self.current.fitness
                    self.best.win_rate = self.current.win_rate
                    self.best.profit_factor = self.current.profit_factor
                    self.best.sharpe = self.current.sharpe

            temp *= self.config.cooling_rate
            iteration += 1

            if verbose and iteration % 20 == 0:
                print(f"    Iter {iteration:3d} | Temp: {temp:6.2f} | Best: {self.best.fitness:7.2f} | WR: {self.best.win_rate:5.1f}%")

        return self.best


# ══════════════════════════════════════════════════════════════
# PARTICLE SWARM OPTIMIZATION
# ══════════════════════════════════════════════════════════════

class ParticleSwarmOptimizer:
    """Otimizador usando PSO"""

    def __init__(self, config: TurboConfig, simulator: FastMarketSimulator):
        self.config = config
        self.simulator = simulator
        self.particles: List[Particle] = []
        self.global_best_position: Dict[str, float] = {}
        self.global_best_fitness: float = float('-inf')
        self.indicators = ["rsi", "macd", "bb", "adx", "stoch", "volume", "news"]

    def initialize(self):
        """Inicializa enxame"""
        self.particles = []

        for _ in range(self.config.num_particles):
            p = Particle()
            for key in self.indicators:
                p.position[key] = random.uniform(self.config.min_weight, self.config.max_weight)
                p.velocity[key] = random.uniform(-0.5, 0.5)
            p.best_position = p.position.copy()
            self.particles.append(p)

    def evaluate_particle(self, particle: Particle):
        """Avalia fitness de uma particula"""
        trades = self.simulator.simulate_trades(particle.position, self.config)
        fitness, win_rate, pf, sharpe = self.simulator.calculate_fitness(trades, self.config)
        particle.current_fitness = fitness

        # Atualizar melhor pessoal
        if fitness > particle.best_fitness:
            particle.best_fitness = fitness
            particle.best_position = particle.position.copy()

        # Atualizar melhor global
        if fitness > self.global_best_fitness:
            self.global_best_fitness = fitness
            self.global_best_position = particle.position.copy()

        return win_rate, pf, sharpe

    def update_particle(self, particle: Particle):
        """Atualiza velocidade e posicao"""
        for key in self.indicators:
            # Componentes da velocidade
            r1, r2 = random.random(), random.random()

            cognitive = self.config.cognitive * r1 * (particle.best_position[key] - particle.position[key])
            social = self.config.social * r2 * (self.global_best_position[key] - particle.position[key])

            # Nova velocidade
            particle.velocity[key] = (
                self.config.inertia * particle.velocity[key] +
                cognitive + social
            )

            # Limitar velocidade
            particle.velocity[key] = max(-1.0, min(1.0, particle.velocity[key]))

            # Nova posicao
            particle.position[key] += particle.velocity[key]
            particle.position[key] = max(self.config.min_weight,
                min(self.config.max_weight, particle.position[key]))

    def run(self, iterations: int = 30, verbose: bool = True) -> Dict:
        """Executa PSO"""
        print("\n  [PARTICLE SWARM]")
        self.initialize()

        best_wr = 0
        best_pf = 0

        for i in range(iterations):
            for particle in self.particles:
                wr, pf, sharpe = self.evaluate_particle(particle)
                if pf > best_pf:
                    best_wr = wr
                    best_pf = pf
                self.update_particle(particle)

            if verbose and i % 5 == 0:
                print(f"    Iter {i+1:3d} | Best Fitness: {self.global_best_fitness:7.2f} | WR: {best_wr:5.1f}%")

        return {
            "weights": self.global_best_position,
            "fitness": self.global_best_fitness,
            "win_rate": best_wr,
            "profit_factor": best_pf
        }


# ══════════════════════════════════════════════════════════════
# TURBO TRAINER
# ══════════════════════════════════════════════════════════════

class TurboTrainer:
    """Treinador principal com todos os algoritmos"""

    def __init__(self, config: TurboConfig = TurboConfig()):
        self.config = config
        self.simulator = FastMarketSimulator()
        self.results: Dict = {}

    async def run(self, verbose: bool = True):
        """Executa treinamento turbo completo"""
        start_time = datetime.now()

        print("=" * 70)
        print("  NEXUS TRADE PRO - TURBO TRAINING v3.0")
        print("=" * 70)
        print(f"  Algoritmos: Genetic + Simulated Annealing + Particle Swarm")
        print(f"  Populacao: {self.config.population_size} | Geracoes: {self.config.generations}")
        print(f"  Multi-Objetivo: Win Rate ({self.config.win_rate_weight*100:.0f}%) + ")
        print(f"                  Profit Factor ({self.config.profit_factor_weight*100:.0f}%) + ")
        print(f"                  Sharpe ({self.config.sharpe_weight*100:.0f}%)")
        print("=" * 70)

        # Verificar servidor
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{API_URL}/api/status")
                if r.status_code != 200:
                    raise Exception("Servidor offline")
        except:
            print("\n[ERRO] Servidor nao esta respondendo!")
            print("       Execute: python server_fastmcp.py http")
            return

        print("\n[1/5] Carregando dados de mercado...")
        await self.simulator.load_all_data(TURBO_TICKERS)

        if len(self.simulator.price_cache) < 5:
            print("[ERRO] Dados insuficientes!")
            return

        # Fase 1: Genetic Algorithm
        print("\n[2/5] Otimizacao Genetica...")
        ga = GeneticOptimizer(self.config, self.simulator)
        ga_best = ga.run(verbose)
        print(f"\n  GA Best: WR={ga_best.win_rate:.1f}% | PF={ga_best.profit_factor:.2f} | Sharpe={ga_best.sharpe:.2f}")

        # Fase 2: Refinar com Simulated Annealing
        print("\n[3/5] Refinamento com Simulated Annealing...")
        sa = SimulatedAnnealing(self.config, self.simulator, ga_best.weights)
        sa_best = sa.run(verbose)
        print(f"\n  SA Best: WR={sa_best.win_rate:.1f}% | PF={sa_best.profit_factor:.2f} | Sharpe={sa_best.sharpe:.2f}")

        # Fase 3: Particle Swarm para exploracao adicional
        print("\n[4/5] Exploracao com Particle Swarm...")
        pso = ParticleSwarmOptimizer(self.config, self.simulator)
        pso_result = pso.run(30, verbose)
        print(f"\n  PSO Best: WR={pso_result['win_rate']:.1f}% | PF={pso_result['profit_factor']:.2f}")

        # Fase 4: Selecionar melhor resultado
        print("\n[5/5] Selecionando melhor configuracao...")

        candidates = [
            ("GA", ga_best.weights, ga_best.fitness, ga_best.win_rate, ga_best.profit_factor, ga_best.sharpe),
            ("SA", sa_best.weights, sa_best.fitness, sa_best.win_rate, sa_best.profit_factor, sa_best.sharpe),
            ("PSO", pso_result["weights"], pso_result["fitness"], pso_result["win_rate"], pso_result["profit_factor"], 0)
        ]

        # Escolher baseado em fitness
        best = max(candidates, key=lambda x: x[2])

        # Avaliar resultado final
        final_trades = self.simulator.simulate_trades(best[1], self.config)
        final_fitness, final_wr, final_pf, final_sharpe = self.simulator.calculate_fitness(final_trades, self.config)

        # Calcular metricas adicionais
        total_pnl = sum(t.pnl_percent for t in final_trades)
        avg_pnl = total_pnl / len(final_trades) if final_trades else 0

        # Max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in final_trades:
            cumulative += t.pnl_percent
            peak = max(peak, cumulative)
            max_dd = max(max_dd, peak - cumulative)

        # Analise por indicador
        indicator_analysis = {ind: {"trades": 0, "wins": 0, "pnl": 0} for ind in ["rsi", "macd", "bb", "adx", "stoch", "volume"]}
        for t in final_trades:
            for ind in t.indicators_used:
                if ind in indicator_analysis:
                    indicator_analysis[ind]["trades"] += 1
                    if t.is_win:
                        indicator_analysis[ind]["wins"] += 1
                    indicator_analysis[ind]["pnl"] += t.pnl_percent

        # Analise por regime
        regime_analysis = {"BULL": {"trades": 0, "wins": 0}, "BEAR": {"trades": 0, "wins": 0}, "NEUTRO": {"trades": 0, "wins": 0}}
        for t in final_trades:
            regime_analysis[t.regime]["trades"] += 1
            if t.is_win:
                regime_analysis[t.regime]["wins"] += 1

        # Salvar resultados
        end_time = datetime.now()
        training_time = (end_time - start_time).total_seconds()

        self.results = {
            "training_date": datetime.now().isoformat(),
            "version": "3.0-turbo",
            "method": f"Hybrid (GA + SA + PSO) - Best: {best[0]}",
            "training_time": round(training_time, 1),
            "results": {
                "total_trades": len(final_trades),
                "wins": sum(1 for t in final_trades if t.is_win),
                "losses": sum(1 for t in final_trades if not t.is_win),
                "win_rate": round(final_wr, 2),
                "total_pnl": round(total_pnl, 2),
                "avg_pnl": round(avg_pnl, 4),
                "profit_factor": round(final_pf, 3),
                "sharpe_ratio": round(final_sharpe, 3),
                "max_drawdown": round(max_dd, 2),
                "fitness": round(final_fitness, 2),
                "optimized_weights": {k: round(v, 3) for k, v in best[1].items()},
                "indicator_performance": {
                    ind: {
                        "trades": data["trades"],
                        "win_rate": round(data["wins"] / data["trades"] * 100, 1) if data["trades"] > 0 else 0,
                        "total_pnl": round(data["pnl"], 2)
                    }
                    for ind, data in indicator_analysis.items()
                },
                "regime_performance": {
                    regime: {
                        "trades": data["trades"],
                        "win_rate": round(data["wins"] / data["trades"] * 100, 1) if data["trades"] > 0 else 0
                    }
                    for regime, data in regime_analysis.items()
                },
                "insights": self._generate_insights(best[1], indicator_analysis, final_wr, final_pf)
            }
        }

        self._print_results()
        self._save_results()

    def _generate_insights(self, weights: Dict, ind_analysis: Dict, win_rate: float, pf: float) -> List[str]:
        """Gera insights automaticos"""
        insights = []

        # Melhor peso
        best_weight = max(weights.items(), key=lambda x: x[1])
        insights.append(f"{best_weight[0].upper()} e o indicador dominante (peso: {best_weight[1]:.2f})")

        # Pior peso
        worst_weight = min(weights.items(), key=lambda x: x[1])
        insights.append(f"{worst_weight[0].upper()} tem menor influencia (peso: {worst_weight[1]:.2f})")

        # Performance geral
        if win_rate > 55:
            insights.append(f"Win Rate de {win_rate:.1f}% - EXCELENTE")
        elif win_rate > 50:
            insights.append(f"Win Rate de {win_rate:.1f}% - POSITIVO")
        else:
            insights.append(f"Win Rate de {win_rate:.1f}% - precisa melhorar")

        if pf > 1.5:
            insights.append(f"Profit Factor de {pf:.2f} - MUITO BOM")
        elif pf > 1.2:
            insights.append(f"Profit Factor de {pf:.2f} - BOM")

        # Melhor indicador por win rate
        best_ind = max(ind_analysis.items(), key=lambda x: x[1]["wins"] / x[1]["trades"] if x[1]["trades"] > 0 else 0)
        if best_ind[1]["trades"] > 0:
            wr = best_ind[1]["wins"] / best_ind[1]["trades"] * 100
            insights.append(f"{best_ind[0].upper()} teve melhor taxa de acerto ({wr:.1f}%)")

        return insights

    def _print_results(self):
        """Imprime resultados formatados"""
        r = self.results["results"]

        print("\n" + "=" * 70)
        print("  RESULTADOS DO TURBO TRAINING")
        print("=" * 70)

        print(f"\n  METRICAS PRINCIPAIS:")
        print(f"  " + "-" * 50)
        print(f"  Total Trades:    {r['total_trades']}")
        print(f"  Win Rate:        {r['win_rate']:.1f}%  {'[OTIMO]' if r['win_rate'] > 55 else '[BOM]' if r['win_rate'] > 50 else ''}")
        print(f"  Profit Factor:   {r['profit_factor']:.2f}  {'[OTIMO]' if r['profit_factor'] > 1.5 else '[BOM]' if r['profit_factor'] > 1.2 else ''}")
        print(f"  Sharpe Ratio:    {r['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:    {r['max_drawdown']:.2f}%")
        print(f"  P&L Total:       {r['total_pnl']:+.2f}%")
        print(f"  P&L Medio:       {r['avg_pnl']:+.4f}%")
        print(f"  Tempo:           {self.results['training_time']:.1f}s")

        print(f"\n  PESOS OTIMIZADOS:")
        print(f"  " + "-" * 50)
        for ind, weight in sorted(r['optimized_weights'].items(), key=lambda x: x[1], reverse=True):
            bar = "#" * int(weight * 8)
            status = "MAX" if weight > 2.0 else "ALTO" if weight > 1.3 else "MEDIO" if weight > 0.8 else "BAIXO"
            print(f"  {ind.upper():8} | {weight:5.2f} | {bar:24} [{status}]")

        print(f"\n  INSIGHTS:")
        print(f"  " + "-" * 50)
        for insight in r["insights"]:
            print(f"  > {insight}")

        print("\n" + "=" * 70)

    def _save_results(self):
        """Salva resultados em arquivos"""
        r = self.results["results"]

        # JSON completo
        with open("training_results.json", "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print("\n[OK] Resultados salvos em training_results.json")

        # JavaScript para dashboard
        weights_js = f"""// TURBO TRAINING v3.0 - {datetime.now().strftime("%d/%m/%Y %H:%M")}
// Metodo: {self.results['method']}
// Trades: {r['total_trades']} | Win Rate: {r['win_rate']:.1f}% | PF: {r['profit_factor']:.2f}

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

// Performance por indicador (ordenado por peso):
{chr(10).join(f'// {ind.upper():8}: peso {r["optimized_weights"][ind]:.2f}' for ind in sorted(r['optimized_weights'].keys(), key=lambda x: r['optimized_weights'][x], reverse=True))}
"""

        with open("trained_weights.js", "w", encoding="utf-8") as f:
            f.write(weights_js)
        print("[OK] Pesos salvos em trained_weights.js")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

async def main():
    print("\nIniciando TURBO TRAINING...")
    print("Certifique-se que o servidor esta rodando: python server_fastmcp.py http\n")

    # Configuracao otimizada para velocidade E qualidade
    config = TurboConfig(
        population_size=35,
        generations=50,
        mutation_rate=0.3,
        crossover_rate=0.75,
        elite_size=6,
        initial_temp=120.0,
        cooling_rate=0.90,
        num_particles=25,
        win_rate_weight=0.45,
        profit_factor_weight=0.35,
        sharpe_weight=0.20
    )

    trainer = TurboTrainer(config)

    try:
        await trainer.run(verbose=True)
    except Exception as e:
        print(f"\n[ERRO] Falha no treinamento: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

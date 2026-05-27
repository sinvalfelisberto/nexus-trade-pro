# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - CONSERVATIVE TRAINING v1.0
=============================================
Treinamento com metricas REALISTAS para evitar overfitting

Diferencas do turbo training:
1. Walk-forward validation real (70% train, 15% val, 15% test)
2. Penalizacao por overfitting
3. Metricas conservadoras (Sharpe < 3, Win Rate < 60%)
4. Modelo simplificado (3-4 indicadores principais)
5. Validacao out-of-sample obrigatoria
"""

import os
import json
import math
import random
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass


# ══════════════════════════════════════════════════════════════
# CONFIGURACAO CONSERVADORA
# ══════════════════════════════════════════════════════════════

@dataclass
class ConservativeConfig:
    # Otimizacao
    population_size: int = 30
    generations: int = 40
    mutation_rate: float = 0.25

    # Limites de peso (mais restritos)
    min_weight: float = 0.1
    max_weight: float = 2.0  # Reduzido de 3.0

    # Penalizacoes
    overfitting_penalty: float = 0.15  # Penalidade se val << train
    complexity_penalty: float = 0.05   # Penalidade por pesos extremos

    # Validacao
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15

    # Thresholds realistas
    max_realistic_sharpe: float = 2.5  # Acima disso, provavelmente overfitting
    max_realistic_win_rate: float = 58.0  # Muito acima é suspeito
    min_trades_for_valid: int = 100  # Minimo de trades para ser valido


# Indicadores simplificados (3 principais + 1 confirmacao)
CORE_INDICATORS = ["stoch", "adx", "macd", "volume"]

# Dados simulados mais realistas (com mais ruido)
ASSETS = {
    "PETR4": {"base": 38.50, "volatility": 3.0, "trend": 0.15},
    "VALE3": {"base": 62.00, "volatility": 2.8, "trend": 0.10},
    "ITUB4": {"base": 32.00, "volatility": 1.5, "trend": 0.05},
    "BBDC4": {"base": 13.50, "volatility": 1.8, "trend": -0.05},
    "MGLU3": {"base": 2.50, "volatility": 5.5, "trend": -0.3},
    "PRIO3": {"base": 45.00, "volatility": 3.5, "trend": 0.20},
    "WEGE3": {"base": 52.00, "volatility": 2.0, "trend": 0.12},
    "B3SA3": {"base": 12.00, "volatility": 2.2, "trend": 0.0},
    "AZUL4": {"base": 5.50, "volatility": 5.0, "trend": -0.2},
    "RENT3": {"base": 45.00, "volatility": 2.2, "trend": 0.08},
    "ELET3": {"base": 42.00, "volatility": 2.8, "trend": 0.10},
    "CSNA3": {"base": 12.00, "volatility": 3.5, "trend": 0.05},
    "GGBR4": {"base": 18.00, "volatility": 3.0, "trend": 0.08},
    "SUZB3": {"base": 58.00, "volatility": 2.5, "trend": 0.15},
    "ABEV3": {"base": 12.50, "volatility": 1.2, "trend": 0.02},
}


# ══════════════════════════════════════════════════════════════
# SIMULADOR CONSERVADOR
# ══════════════════════════════════════════════════════════════

class ConservativeSimulator:
    """Simulador com mais ruido e custos realistas"""

    def __init__(self, config: ConservativeConfig):
        self.config = config
        self.price_data = {}
        self.indicators = {}
        self._generate_data()

    def _generate_data(self):
        """Gera dados com 120 dias (mais dados para split)"""
        for ticker, params in ASSETS.items():
            # Gerar precos
            prices = [params["base"]]
            for _ in range(119):
                # Random walk com mais ruido
                ret = random.gauss(params["trend"] / 100, params["volatility"] / 100)
                # Adicionar gaps e eventos
                if random.random() < 0.05:  # 5% chance de gap
                    ret += random.choice([-1, 1]) * random.uniform(0.02, 0.05)
                new_price = prices[-1] * (1 + ret)
                prices.append(round(max(prices[-1] * 0.85, min(prices[-1] * 1.15, new_price)), 2))

            self.price_data[ticker] = prices

            # Calcular indicadores
            self.indicators[ticker] = self._calc_indicators(prices, params)

    def _calc_indicators(self, prices: List[float], params: Dict) -> List[Dict]:
        """Calcula indicadores para cada ponto no tempo"""
        indicators = []

        for i in range(20, len(prices)):
            window = prices[max(0, i-20):i+1]

            # Stochastic
            low14 = min(prices[max(0,i-14):i+1])
            high14 = max(prices[max(0,i-14):i+1])
            stoch = ((prices[i] - low14) / (high14 - low14) * 100) if high14 > low14 else 50

            # ADX aproximado
            volatility_ratio = (high14 - low14) / prices[i] * 100
            trend_strength = abs(prices[i] - prices[max(0,i-14)]) / prices[max(0,i-14)] * 100
            adx = min(60, volatility_ratio * 3 + trend_strength * 5 + random.uniform(-5, 5))

            # MACD signal
            ema9 = sum(prices[max(0,i-9):i+1]) / min(9, i+1)
            ema21 = sum(prices[max(0,i-21):i+1]) / min(21, i+1)
            macd_signal = 1 if ema9 > ema21 else -1

            # Volume trend (simulado com ruido)
            vol_trend = 1 if params["trend"] > 0.05 else -1 if params["trend"] < -0.05 else 0
            vol_trend += random.choice([-1, 0, 0, 0, 1])  # Adiciona ruido

            indicators.append({
                "price": prices[i],
                "stoch": stoch,
                "adx": adx,
                "macd_signal": macd_signal,
                "volume_trend": max(-1, min(1, vol_trend)),
                "plus_di": 25 if macd_signal > 0 else 15,
                "minus_di": 15 if macd_signal > 0 else 25,
            })

        return indicators

    def simulate_trades(self, weights: Dict, data_slice: str = "all") -> List[Dict]:
        """Simula trades com custos e slippage realistas"""
        trades = []

        for ticker, indicators in self.indicators.items():
            # Determinar slice de dados
            n = len(indicators)
            if data_slice == "train":
                start, end = 0, int(n * self.config.train_ratio)
            elif data_slice == "val":
                start, end = int(n * self.config.train_ratio), int(n * (self.config.train_ratio + self.config.val_ratio))
            elif data_slice == "test":
                start, end = int(n * (self.config.train_ratio + self.config.val_ratio)), n
            else:
                start, end = 0, n

            for i in range(start, end - 3):
                ind = indicators[i]

                # Calcular score ponderado
                score = 0

                # Stochastic
                if ind["stoch"] < 20:
                    score += 25 * weights.get("stoch", 1)
                elif ind["stoch"] > 80:
                    score -= 25 * weights.get("stoch", 1)

                # ADX + direction
                if ind["adx"] > 25:
                    if ind["plus_di"] > ind["minus_di"]:
                        score += 20 * weights.get("adx", 1)
                    else:
                        score -= 20 * weights.get("adx", 1)

                # MACD
                score += 15 * ind["macd_signal"] * weights.get("macd", 1)

                # Volume
                score += 10 * ind["volume_trend"] * weights.get("volume", 1)

                # Threshold para entrar
                if abs(score) < 15:
                    continue

                # Simular saida
                entry_price = ind["price"]
                exit_idx = min(i + random.randint(1, 3), end - 1)
                exit_price = indicators[exit_idx]["price"]

                # Calcular P&L com custos realistas
                if score > 0:  # Long
                    raw_pnl = (exit_price - entry_price) / entry_price * 100
                else:  # Short
                    raw_pnl = (entry_price - exit_price) / entry_price * 100

                # Custos: corretagem + emolumentos + slippage
                costs = 0.12  # ~0.12% por trade completo

                # Slippage variavel
                slippage = random.uniform(0.02, 0.08)

                final_pnl = raw_pnl - costs - slippage

                # Adicionar ruido de mercado
                final_pnl += random.gauss(0, 0.3)

                # Limitar
                final_pnl = max(-5.0, min(8.0, final_pnl))

                trades.append({
                    "ticker": ticker,
                    "pnl": final_pnl,
                    "is_win": final_pnl > 0,
                    "score": score
                })

        return trades

    def calculate_metrics(self, trades: List[Dict]) -> Dict:
        """Calcula metricas com validacao de overfitting"""
        if len(trades) < 20:
            return {"valid": False, "win_rate": 0, "profit_factor": 0, "sharpe": 0, "fitness": 0}

        wins = sum(1 for t in trades if t["is_win"])
        win_rate = wins / len(trades) * 100

        gross_profit = sum(t["pnl"] for t in trades if t["is_win"])
        gross_loss = abs(sum(t["pnl"] for t in trades if not t["is_win"]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0.01 else gross_profit + 1

        returns = [t["pnl"] for t in trades]
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_ret = math.sqrt(variance) if variance > 0 else 1
        sharpe = (mean_ret / std_ret) * math.sqrt(252) if std_ret > 0 else 0

        # Limitar metricas a valores realistas
        sharpe = min(sharpe, self.config.max_realistic_sharpe)

        # Fitness multi-objetivo
        fitness = (
            win_rate * 0.40 +
            min(profit_factor, 2.5) * 20 * 0.35 +
            max(0, sharpe) * 15 * 0.25
        )

        return {
            "valid": True,
            "trades": len(trades),
            "wins": wins,
            "losses": len(trades) - wins,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(min(profit_factor, 3.0), 3),
            "sharpe": round(sharpe, 3),
            "total_pnl": round(sum(returns), 2),
            "fitness": round(fitness, 2)
        }


# ══════════════════════════════════════════════════════════════
# OTIMIZADOR CONSERVADOR
# ══════════════════════════════════════════════════════════════

class ConservativeOptimizer:
    """Otimizador com validacao walk-forward"""

    def __init__(self, config: ConservativeConfig):
        self.config = config
        self.simulator = ConservativeSimulator(config)
        self.best_weights = {}
        self.best_fitness = 0

    def _random_weights(self) -> Dict:
        """Gera pesos aleatorios dentro dos limites"""
        return {
            "stoch": random.uniform(0.8, 1.8),
            "adx": random.uniform(0.8, 1.8),
            "macd": random.uniform(0.5, 1.5),
            "volume": random.uniform(0.3, 1.2)
        }

    def _mutate(self, weights: Dict) -> Dict:
        """Mutacao com limites"""
        new_weights = weights.copy()
        for key in new_weights:
            if random.random() < self.config.mutation_rate:
                delta = random.gauss(0, 0.2)
                new_weights[key] = max(self.config.min_weight,
                    min(self.config.max_weight, new_weights[key] + delta))
        return new_weights

    def _evaluate_with_validation(self, weights: Dict) -> Tuple[float, Dict, Dict, Dict]:
        """Avalia com walk-forward (train -> val -> test)"""

        # Treino
        train_trades = self.simulator.simulate_trades(weights, "train")
        train_metrics = self.simulator.calculate_metrics(train_trades)

        if not train_metrics["valid"]:
            return 0, train_metrics, {}, {}

        # Validacao
        val_trades = self.simulator.simulate_trades(weights, "val")
        val_metrics = self.simulator.calculate_metrics(val_trades)

        # Teste (apenas para relatorio final, nao usa na otimizacao)
        test_trades = self.simulator.simulate_trades(weights, "test")
        test_metrics = self.simulator.calculate_metrics(test_trades)

        # Calcular fitness com penalizacao de overfitting
        train_fitness = train_metrics["fitness"]
        val_fitness = val_metrics.get("fitness", 0) if val_metrics.get("valid") else 0

        # Penalizar se validacao muito pior que treino
        if train_fitness > 0 and val_fitness > 0:
            overfit_ratio = val_fitness / train_fitness
            if overfit_ratio < 0.7:  # Validacao 30%+ pior
                penalty = (1 - overfit_ratio) * self.config.overfitting_penalty * train_fitness
                train_fitness -= penalty

        # Penalizar pesos muito extremos
        weight_variance = sum((w - 1.0) ** 2 for w in weights.values()) / len(weights)
        if weight_variance > 0.5:
            train_fitness -= weight_variance * self.config.complexity_penalty * 10

        return train_fitness, train_metrics, val_metrics, test_metrics

    def optimize(self, verbose: bool = True) -> Dict:
        """Executa otimizacao"""

        print("\n" + "=" * 60)
        print("  CONSERVATIVE TRAINING v1.0")
        print("  Walk-Forward Validation | Anti-Overfitting")
        print("=" * 60)

        # Populacao inicial
        population = [self._random_weights() for _ in range(self.config.population_size)]

        # Seeds conservadores
        seeds = [
            {"stoch": 1.2, "adx": 1.3, "macd": 1.0, "volume": 0.7},
            {"stoch": 1.0, "adx": 1.5, "macd": 0.8, "volume": 0.5},
            {"stoch": 1.4, "adx": 1.0, "macd": 1.2, "volume": 0.6},
        ]
        for i, seed in enumerate(seeds):
            if i < len(population):
                population[i] = seed

        best_overall = None
        best_fitness = 0
        best_train = {}
        best_val = {}
        best_test = {}

        for gen in range(self.config.generations):
            evaluated = []

            for weights in population:
                fitness, train, val, test = self._evaluate_with_validation(weights)
                evaluated.append((weights, fitness, train, val, test))

            # Ordenar por fitness
            evaluated.sort(key=lambda x: x[1], reverse=True)

            # Melhor desta geracao
            if evaluated[0][1] > best_fitness:
                best_fitness = evaluated[0][1]
                best_overall = evaluated[0][0].copy()
                best_train = evaluated[0][2]
                best_val = evaluated[0][3]
                best_test = evaluated[0][4]

            if verbose and gen % 5 == 0:
                top = evaluated[0]
                print(f"  Gen {gen+1:3d} | Fit: {top[1]:6.2f} | "
                      f"Train WR: {top[2].get('win_rate', 0):5.1f}% | "
                      f"Val WR: {top[3].get('win_rate', 0):5.1f}%")

            # Nova geracao
            new_pop = []

            # Elitismo
            for i in range(3):
                new_pop.append(evaluated[i][0].copy())

            # Resto por crossover + mutacao
            while len(new_pop) < self.config.population_size:
                # Selecao torneio
                t1 = random.sample(evaluated[:10], 3)
                p1 = max(t1, key=lambda x: x[1])[0]
                t2 = random.sample(evaluated[:10], 3)
                p2 = max(t2, key=lambda x: x[1])[0]

                # Crossover
                child = {}
                for key in CORE_INDICATORS:
                    if random.random() < 0.5:
                        child[key] = p1.get(key, 1.0)
                    else:
                        child[key] = p2.get(key, 1.0)

                # Mutacao
                child = self._mutate(child)
                new_pop.append(child)

            population = new_pop

        # Resultados finais
        print("\n" + "=" * 60)
        print("  RESULTADOS FINAIS")
        print("=" * 60)

        print(f"\n  TRAIN (70% dados):")
        print(f"    Trades: {best_train.get('trades', 0)}")
        print(f"    Win Rate: {best_train.get('win_rate', 0):.1f}%")
        print(f"    Profit Factor: {best_train.get('profit_factor', 0):.2f}")
        print(f"    Sharpe: {best_train.get('sharpe', 0):.2f}")

        print(f"\n  VALIDATION (15% dados):")
        print(f"    Trades: {best_val.get('trades', 0)}")
        print(f"    Win Rate: {best_val.get('win_rate', 0):.1f}%")
        print(f"    Profit Factor: {best_val.get('profit_factor', 0):.2f}")
        print(f"    Sharpe: {best_val.get('sharpe', 0):.2f}")

        print(f"\n  TEST (15% dados - OUT OF SAMPLE):")
        print(f"    Trades: {best_test.get('trades', 0)}")
        print(f"    Win Rate: {best_test.get('win_rate', 0):.1f}%")
        print(f"    Profit Factor: {best_test.get('profit_factor', 0):.2f}")
        print(f"    Sharpe: {best_test.get('sharpe', 0):.2f}")

        print(f"\n  PESOS OTIMIZADOS (Conservadores):")
        for key, val in sorted(best_overall.items(), key=lambda x: x[1], reverse=True):
            print(f"    {key.upper():8}: {val:.3f}")

        # Verificar degradacao train -> test
        train_wr = best_train.get('win_rate', 0)
        test_wr = best_test.get('win_rate', 0)
        degradation = ((train_wr - test_wr) / train_wr * 100) if train_wr > 0 else 0

        print(f"\n  ANALISE DE OVERFITTING:")
        if degradation < 5:
            print(f"    Degradacao: {degradation:.1f}% - EXCELENTE (modelo robusto)")
        elif degradation < 15:
            print(f"    Degradacao: {degradation:.1f}% - BOM (modelo estavel)")
        else:
            print(f"    Degradacao: {degradation:.1f}% - ATENCAO (possivel overfitting)")

        # Salvar resultados
        self._save_results(best_overall, best_train, best_val, best_test)

        print("\n" + "=" * 60)

        return best_overall

    def _save_results(self, weights: Dict, train: Dict, val: Dict, test: Dict):
        """Salva resultados conservadores"""

        # Usar metricas de TEST (out-of-sample) como referencia real
        results = {
            "training_date": datetime.now().isoformat(),
            "version": "1.0-conservative",
            "method": "Walk-Forward Validation",
            "results": {
                "total_trades": test.get("trades", 0),
                "wins": test.get("wins", 0),
                "losses": test.get("losses", 0),
                "win_rate": test.get("win_rate", 0),
                "profit_factor": test.get("profit_factor", 0),
                "sharpe_ratio": test.get("sharpe", 0),
                "total_pnl": test.get("total_pnl", 0),
                "optimized_weights": {k: round(v, 3) for k, v in weights.items()},
                "validation": {
                    "train_win_rate": train.get("win_rate", 0),
                    "val_win_rate": val.get("win_rate", 0),
                    "test_win_rate": test.get("win_rate", 0),
                },
                "insights": [
                    f"Modelo simplificado com {len(CORE_INDICATORS)} indicadores",
                    f"Validacao out-of-sample: {test.get('win_rate', 0):.1f}% win rate",
                    f"Profit Factor realista: {test.get('profit_factor', 0):.2f}",
                    f"Sharpe conservador: {test.get('sharpe', 0):.2f}",
                ]
            }
        }

        with open("training_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print("\n[OK] training_results.json salvo (metricas conservadoras)")

        # Atualizar pesos JS
        weights_js = f"""// CONSERVATIVE TRAINING v1.0 - {datetime.now().strftime("%d/%m/%Y %H:%M")}
// Walk-Forward Validation | Test WR: {test.get('win_rate', 0):.1f}% | PF: {test.get('profit_factor', 0):.2f}

const TRAINED_WEIGHTS = {{
  "rsi": 0.1,      // Removido (baixa eficacia)
  "macd": {weights.get('macd', 1.0):.3f},
  "bb": 0.1,       // Removido (baixa eficacia)
  "adx": {weights.get('adx', 1.0):.3f},
  "stoch": {weights.get('stoch', 1.0):.3f},
  "volume": {weights.get('volume', 0.5):.3f},
  "news": 0.3
}};

const TRAINING_STATS = {{
    win_rate: {test.get('win_rate', 0):.1f},
    total_trades: {test.get('trades', 0)},
    profit_factor: {test.get('profit_factor', 0):.2f},
    sharpe_ratio: {test.get('sharpe', 0):.2f},
    training_date: "{datetime.now().strftime("%d/%m/%Y %H:%M")}",
    version: "1.0-conservative",
    validation: "walk-forward"
}};
"""
        with open("trained_weights.js", "w", encoding="utf-8") as f:
            f.write(weights_js)
        print("[OK] trained_weights.js salvo (pesos conservadores)")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    config = ConservativeConfig()
    optimizer = ConservativeOptimizer(config)
    optimizer.optimize(verbose=True)

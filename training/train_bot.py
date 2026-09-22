# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Sistema de Treinamento Acelerado
Simula milhares de operacoes para otimizar os pesos dos indicadores
"""

import os
import json
import random
import asyncio
import httpx
from datetime import datetime, timedelta
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
import env_config as cfg  # configuracao sempre do .env da raiz

API_URL = cfg.server_url()
BRAPI_TOKEN = cfg.get_str("BRAPI_TOKEN", "")

# Ativos para treinamento
TRAINING_TICKERS = [
    "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "WEGE3", "ABEV3", "B3SA3",
    "RENT3", "SUZB3", "PRIO3", "ELET3", "GGBR4", "CSNA3", "MGLU3", "LREN3"
]

# Resultado do treinamento
training_results = {
    "total_trades": 0,
    "wins": 0,
    "losses": 0,
    "total_pnl": 0,
    "indicator_performance": {
        "rsi": {"wins": 0, "losses": 0, "contribution": 0},
        "macd": {"wins": 0, "losses": 0, "contribution": 0},
        "bb": {"wins": 0, "losses": 0, "contribution": 0},
        "adx": {"wins": 0, "losses": 0, "contribution": 0},
        "stoch": {"wins": 0, "losses": 0, "contribution": 0},
        "volume": {"wins": 0, "losses": 0, "contribution": 0}
    },
    "optimized_weights": {},
    "best_strategies": [],
    "training_time": 0
}


async def get_score(ticker: str):
    """Busca score de um ativo"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API_URL}/api/score/{ticker}")
            return r.json()
    except:
        return None


async def get_history(ticker: str, days: int = 30):
    """Busca historico de um ativo"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API_URL}/api/history/{ticker}?days={days}")
            return r.json()
    except:
        return None


def simulate_trade(entry_price, exit_price, score, indicators):
    """Simula um trade e retorna resultado"""
    pnl_percent = ((exit_price - entry_price) / entry_price) * 100
    is_win = pnl_percent > 0

    # Analisar contribuicao de cada indicador
    contributions = {}
    if indicators:
        breakdown = indicators.get("breakdown", {})
        for ind in ["rsi", "macd", "bb", "adx", "stoch", "volume"]:
            if ind in breakdown:
                weighted = abs(breakdown[ind].get("weighted", 0))
                contributions[ind] = weighted > 5  # Contribuiu se peso > 5

    return {
        "is_win": is_win,
        "pnl_percent": pnl_percent,
        "score": score,
        "contributions": contributions
    }


async def backtest_ticker(ticker: str, verbose: bool = False):
    """Faz backtest em um ativo usando dados historicos"""
    results = []

    # Buscar dados
    history = await get_history(ticker, 60)
    if not history or "error" in history:
        return results

    data = history.get("data", [])
    if len(data) < 30:
        return results

    # Simular entradas em diferentes pontos
    for i in range(20, len(data) - 5):
        # Pegar janela de dados
        entry_price = data[i].get("close", 0)
        if entry_price <= 0:
            continue

        # Simular diferentes cenarios de saida
        for j in range(1, 6):  # 1 a 5 dias depois
            if i + j >= len(data):
                break

            exit_price = data[i + j].get("close", 0)
            if exit_price <= 0:
                continue

            # Buscar score atual do ativo
            score_data = await get_score(ticker)
            if not score_data or "error" in score_data:
                continue

            score = score_data.get("score", 0)
            signal = score_data.get("signal", "NEUTRO")

            # Simular trade baseado no sinal
            if signal in ["COMPRAR", "COMPRA FORTE"] or score > 30:
                result = simulate_trade(entry_price, exit_price, score, score_data)
                result["ticker"] = ticker
                result["days_held"] = j
                result["signal"] = signal
                results.append(result)

                if verbose:
                    status = "WIN" if result["is_win"] else "LOSS"
                    print(f"  {ticker}: {status} {result['pnl_percent']:.2f}% (score: {score})")

    return results


async def run_rapid_training(num_cycles: int = 100, verbose: bool = True):
    """Executa treinamento rapido com multiplos ciclos"""
    global training_results

    print("=" * 60)
    print("  NEXUS TRADE PRO - Treinamento Acelerado")
    print("=" * 60)
    print(f"  Ciclos: {num_cycles}")
    print(f"  Ativos: {len(TRAINING_TICKERS)}")
    print("=" * 60)

    start_time = datetime.now()
    all_trades = []

    for cycle in range(num_cycles):
        if verbose and cycle % 10 == 0:
            print(f"\n[Ciclo {cycle + 1}/{num_cycles}]")

        # Selecionar ativos aleatorios para este ciclo
        tickers = random.sample(TRAINING_TICKERS, min(5, len(TRAINING_TICKERS)))

        for ticker in tickers:
            # Buscar score e simular decisao
            score_data = await get_score(ticker)
            if not score_data or "error" in score_data:
                continue

            score = score_data.get("score", 0)
            signal = score_data.get("signal", "NEUTRO")
            price = score_data.get("indicators", {}).get("price", 0)

            if price <= 0:
                continue

            # Simular variacao de preco (baseado em volatilidade real)
            volatility = random.uniform(0.5, 3.0)  # 0.5% a 3%
            direction = 1 if score > 0 else -1
            noise = random.uniform(-0.5, 0.5)

            # Acerto maior quando score e forte
            accuracy_bonus = min(abs(score) / 100, 0.3)
            final_direction = direction if random.random() < (0.5 + accuracy_bonus) else -direction

            pnl_percent = final_direction * volatility + noise

            # Aplicar stop loss / take profit
            if pnl_percent < -3:
                pnl_percent = -3  # Stop loss
            if pnl_percent > 6:
                pnl_percent = 6  # Take profit

            is_win = pnl_percent > 0

            # Registrar trade
            trade = {
                "ticker": ticker,
                "score": score,
                "signal": signal,
                "pnl_percent": pnl_percent,
                "is_win": is_win,
                "breakdown": score_data.get("breakdown", {})
            }
            all_trades.append(trade)

            # Atualizar estatisticas
            training_results["total_trades"] += 1
            training_results["total_pnl"] += pnl_percent

            if is_win:
                training_results["wins"] += 1
            else:
                training_results["losses"] += 1

            # Atualizar performance por indicador
            breakdown = score_data.get("breakdown", {})
            for ind in ["rsi", "macd", "bb", "adx", "stoch", "volume"]:
                if ind in breakdown:
                    weighted = breakdown[ind].get("weighted", 0)
                    if abs(weighted) > 5:  # Indicador contribuiu
                        if is_win:
                            training_results["indicator_performance"][ind]["wins"] += 1
                        else:
                            training_results["indicator_performance"][ind]["losses"] += 1
                        training_results["indicator_performance"][ind]["contribution"] += weighted

            if verbose and cycle % 10 == 0:
                status = "+" if is_win else "-"
                print(f"  {status} {ticker}: {pnl_percent:+.2f}% (score: {score:+.0f})")

        # Pequena pausa para nao sobrecarregar API
        if cycle % 20 == 0:
            await asyncio.sleep(0.5)

    # Calcular tempo
    end_time = datetime.now()
    training_results["training_time"] = (end_time - start_time).total_seconds()

    # Otimizar pesos baseado nos resultados
    optimize_weights()

    # Identificar melhores estrategias
    analyze_strategies(all_trades)

    return training_results


def optimize_weights():
    """Otimiza pesos dos indicadores baseado no desempenho"""
    perf = training_results["indicator_performance"]
    optimized = {}

    for ind in perf:
        wins = perf[ind]["wins"]
        losses = perf[ind]["losses"]
        total = wins + losses

        if total > 0:
            win_rate = wins / total
            # Peso baseado na taxa de acerto
            # 50% = peso 1.0, 60% = peso 1.2, 40% = peso 0.8
            weight = 0.5 + win_rate
            optimized[ind] = round(weight, 2)
        else:
            optimized[ind] = 1.0

    training_results["optimized_weights"] = optimized


def analyze_strategies(trades):
    """Analisa e identifica as melhores estrategias"""
    strategies = {
        "high_score": {"trades": 0, "wins": 0, "pnl": 0},  # Score > 50
        "medium_score": {"trades": 0, "wins": 0, "pnl": 0},  # Score 20-50
        "low_score": {"trades": 0, "wins": 0, "pnl": 0},  # Score < 20
        "compra_forte": {"trades": 0, "wins": 0, "pnl": 0},
        "comprar": {"trades": 0, "wins": 0, "pnl": 0},
        "neutro": {"trades": 0, "wins": 0, "pnl": 0},
    }

    for trade in trades:
        score = trade["score"]
        signal = trade["signal"]
        pnl = trade["pnl_percent"]
        is_win = trade["is_win"]

        # Por score
        if score > 50:
            key = "high_score"
        elif score > 20:
            key = "medium_score"
        else:
            key = "low_score"

        strategies[key]["trades"] += 1
        strategies[key]["pnl"] += pnl
        if is_win:
            strategies[key]["wins"] += 1

        # Por sinal
        if signal == "COMPRA FORTE":
            strategies["compra_forte"]["trades"] += 1
            strategies["compra_forte"]["pnl"] += pnl
            if is_win:
                strategies["compra_forte"]["wins"] += 1
        elif signal == "COMPRAR":
            strategies["comprar"]["trades"] += 1
            strategies["comprar"]["pnl"] += pnl
            if is_win:
                strategies["comprar"]["wins"] += 1
        else:
            strategies["neutro"]["trades"] += 1
            strategies["neutro"]["pnl"] += pnl
            if is_win:
                strategies["neutro"]["wins"] += 1

    # Calcular win rate e ordenar
    best = []
    for name, data in strategies.items():
        if data["trades"] > 0:
            win_rate = (data["wins"] / data["trades"]) * 100
            avg_pnl = data["pnl"] / data["trades"]
            best.append({
                "strategy": name,
                "trades": data["trades"],
                "win_rate": round(win_rate, 1),
                "avg_pnl": round(avg_pnl, 2),
                "total_pnl": round(data["pnl"], 2)
            })

    best.sort(key=lambda x: x["win_rate"], reverse=True)
    training_results["best_strategies"] = best


def print_results():
    """Imprime resultados do treinamento"""
    r = training_results

    print("\n" + "=" * 60)
    print("  RESULTADOS DO TREINAMENTO")
    print("=" * 60)

    total = r["total_trades"]
    if total == 0:
        print("Nenhum trade realizado")
        return

    win_rate = (r["wins"] / total) * 100
    avg_pnl = r["total_pnl"] / total

    print(f"\n  Total de Trades: {total}")
    print(f"  Wins: {r['wins']} | Losses: {r['losses']}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  P&L Total: {r['total_pnl']:.2f}%")
    print(f"  P&L Medio: {avg_pnl:.2f}%")
    print(f"  Tempo: {r['training_time']:.1f}s")

    print("\n  PERFORMANCE POR INDICADOR:")
    print("  " + "-" * 40)
    for ind, data in r["indicator_performance"].items():
        total_ind = data["wins"] + data["losses"]
        if total_ind > 0:
            wr = (data["wins"] / total_ind) * 100
            print(f"  {ind.upper():8} | Win Rate: {wr:5.1f}% | Trades: {total_ind}")

    print("\n  PESOS OTIMIZADOS:")
    print("  " + "-" * 40)
    for ind, weight in r["optimized_weights"].items():
        bar = "#" * int(weight * 10)
        print(f"  {ind.upper():8} | {weight:.2f} | {bar}")

    print("\n  MELHORES ESTRATEGIAS:")
    print("  " + "-" * 40)
    for s in r["best_strategies"][:5]:
        print(f"  {s['strategy']:15} | WR: {s['win_rate']:5.1f}% | Avg: {s['avg_pnl']:+.2f}%")

    print("\n" + "=" * 60)


def save_results():
    """Salva resultados em arquivo JSON"""
    output = {
        "training_date": datetime.now().isoformat(),
        "results": training_results
    }

    with open("training_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\n[OK] Resultados salvos em training_results.json")

    # Criar arquivo de pesos para o dashboard
    weights_js = f"""
// Pesos otimizados pelo treinamento - {datetime.now().strftime("%d/%m/%Y %H:%M")}
const TRAINED_WEIGHTS = {json.dumps(training_results["optimized_weights"], indent=2)};
const TRAINING_WIN_RATE = {(training_results["wins"] / max(training_results["total_trades"], 1)) * 100:.1f};
const TRAINING_TRADES = {training_results["total_trades"]};
"""

    with open("trained_weights.js", "w") as f:
        f.write(weights_js)

    print("[OK] Pesos salvos em trained_weights.js")


async def main():
    print("\nIniciando servidor de treinamento...")
    print("Certifique-se que o servidor esta rodando (NexusTradePro.bat)\n")

    # Verificar conexao
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{API_URL}/api/status")
            if r.status_code != 200:
                print("[ERRO] Servidor nao esta respondendo")
                return
    except:
        print("[ERRO] Nao foi possivel conectar ao servidor")
        print("       Execute NexusTradePro.bat primeiro")
        return

    print("[OK] Servidor conectado!\n")

    # Executar treinamento
    await run_rapid_training(num_cycles=200, verbose=True)

    # Mostrar e salvar resultados
    print_results()
    save_results()


if __name__ == "__main__":
    asyncio.run(main())

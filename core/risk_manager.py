# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Risk Manager v1.0
====================================
Sistema de Gerenciamento de Risco Avancado

Recursos:
- Controle de Drawdown Maximo
- Limite de Perda Diaria
- Reducao de Posicao apos Perdas Consecutivas
- Position Sizing Dinamico (Kelly Criterion)
- Trailing Stop Automatico
- Circuit Breaker (para de operar em condicoes extremas)
"""

import os
import json
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional
from enum import Enum

# Arquivo para persistir estado do risk manager (na pasta data/)
RISK_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "risk_state.json")


class RiskStatus(Enum):
    """Status do sistema de risco"""
    OK = "OK"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"


class BlockReason(Enum):
    """Razoes para bloqueio de trading"""
    NONE = "NONE"
    MAX_DRAWDOWN = "MAX_DRAWDOWN_ATINGIDO"
    DAILY_LOSS_LIMIT = "LIMITE_DIARIO_ATINGIDO"
    CONSECUTIVE_LOSSES = "MUITAS_PERDAS_CONSECUTIVAS"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER_ATIVADO"
    VOLATILITY_TOO_HIGH = "VOLATILIDADE_MUITO_ALTA"
    LOW_CONFIDENCE = "CONFIANCA_BAIXA"


@dataclass
class RiskConfig:
    """Configuracao do Risk Manager"""
    # Drawdown
    max_drawdown_percent: float = 20.0          # Drawdown maximo permitido (%)
    warning_drawdown_percent: float = 10.0      # Alerta de drawdown (%)

    # Perdas diarias
    max_daily_loss_percent: float = 5.0         # Perda maxima diaria (%)
    max_daily_trades: int = 20                  # Maximo de trades por dia

    # Perdas consecutivas
    max_consecutive_losses: int = 5             # Maximo de perdas seguidas
    reduction_after_losses: int = 2             # Reduzir apos X perdas

    # Position sizing
    base_position_percent: float = 10.0         # % do capital por posicao (base)
    min_position_percent: float = 2.0           # Posicao minima
    max_position_percent: float = 20.0          # Posicao maxima
    use_kelly_criterion: bool = True            # Usar Kelly para sizing
    kelly_fraction: float = 0.5                 # Fracao de Kelly (mais conservador)

    # Confianca minima
    min_confidence_to_trade: float = 55.0       # Confianca minima do sinal (%)
    min_score_to_trade: float = 25.0            # Score minimo para operar

    # Circuit breaker
    circuit_breaker_loss_percent: float = 8.0   # Loss que ativa circuit breaker
    circuit_breaker_hours: int = 24             # Horas de pausa apos circuit breaker

    # Volatilidade
    max_volatility_atr_percent: float = 5.0     # ATR maximo para operar (% do preco)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DailyStats:
    """Estatisticas do dia"""
    date: str = ""
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0

    def __post_init__(self):
        if not self.date:
            self.date = date.today().isoformat()


@dataclass
class RiskState:
    """Estado persistente do Risk Manager"""
    # Capital
    initial_capital: float = 500.0
    current_capital: float = 500.0
    peak_capital: float = 500.0

    # Drawdown
    current_drawdown: float = 0.0
    max_drawdown_reached: float = 0.0

    # Sequencias
    consecutive_losses: int = 0
    consecutive_wins: int = 0

    # Status
    status: str = "OK"
    block_reason: str = "NONE"
    blocked_until: str = ""

    # Estatisticas
    total_trades: int = 0
    total_wins: int = 0
    total_losses: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0

    # Diario
    daily_stats: Dict = field(default_factory=dict)

    # Historico de trades
    recent_trades: List = field(default_factory=list)

    # Timestamps
    last_trade_time: str = ""
    last_update: str = ""

    def to_dict(self) -> dict:
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "peak_capital": self.peak_capital,
            "current_drawdown": self.current_drawdown,
            "max_drawdown_reached": self.max_drawdown_reached,
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "status": self.status,
            "block_reason": self.block_reason,
            "blocked_until": self.blocked_until,
            "total_trades": self.total_trades,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "total_pnl": self.total_pnl,
            "win_rate": self.win_rate,
            "daily_stats": self.daily_stats,
            "recent_trades": self.recent_trades[-50:],  # Ultimos 50 trades
            "last_trade_time": self.last_trade_time,
            "last_update": self.last_update
        }


class RiskManager:
    """
    Gerenciador de Risco Principal

    Controla:
    - Drawdown maximo
    - Perdas diarias
    - Perdas consecutivas
    - Position sizing dinamico
    - Circuit breaker
    """

    def __init__(self, config: RiskConfig = None, initial_capital: float = 500.0):
        self.config = config or RiskConfig()
        self.state = RiskState(
            initial_capital=initial_capital,
            current_capital=initial_capital,
            peak_capital=initial_capital
        )
        self._load_state()

    def _load_state(self):
        """Carrega estado salvo"""
        try:
            if os.path.exists(RISK_STATE_FILE):
                with open(RISK_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Atualizar estado com dados salvos
                    for key, value in data.items():
                        if hasattr(self.state, key):
                            setattr(self.state, key, value)
        except Exception as e:
            print(f"[RiskManager] Erro ao carregar estado: {e}")

    def _save_state(self):
        """Salva estado atual"""
        try:
            self.state.last_update = datetime.now().isoformat()
            with open(RISK_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[RiskManager] Erro ao salvar estado: {e}")

    def _get_today_stats(self) -> DailyStats:
        """Retorna estatisticas do dia atual"""
        today = date.today().isoformat()
        if today not in self.state.daily_stats:
            self.state.daily_stats[today] = DailyStats(date=today).__dict__
        return DailyStats(**self.state.daily_stats[today])

    def _update_today_stats(self, stats: DailyStats):
        """Atualiza estatisticas do dia"""
        self.state.daily_stats[stats.date] = stats.__dict__

    def update_capital(self, new_capital: float):
        """Atualiza capital atual e recalcula drawdown"""
        self.state.current_capital = new_capital

        # Atualizar pico
        if new_capital > self.state.peak_capital:
            self.state.peak_capital = new_capital

        # Calcular drawdown atual
        if self.state.peak_capital > 0:
            self.state.current_drawdown = (
                (self.state.peak_capital - self.state.current_capital)
                / self.state.peak_capital * 100
            )

        # Atualizar max drawdown
        if self.state.current_drawdown > self.state.max_drawdown_reached:
            self.state.max_drawdown_reached = self.state.current_drawdown

        self._save_state()

    def check_can_trade(
        self,
        order_value: float = 0,
        confidence: float = 100,
        score: float = 100,
        volatility_atr_percent: float = 0
    ) -> Tuple[bool, str, dict]:
        """
        Verifica se pode executar trade

        Returns:
            (can_trade, reason, details)
        """
        details = {
            "status": self.state.status,
            "current_drawdown": round(self.state.current_drawdown, 2),
            "consecutive_losses": self.state.consecutive_losses,
            "position_multiplier": 1.0,
            "warnings": []
        }

        # 1. Verificar se esta bloqueado
        if self.state.status == RiskStatus.BLOCKED.value:
            # Verificar se ja pode desbloquear
            if self.state.blocked_until:
                blocked_time = datetime.fromisoformat(self.state.blocked_until)
                if datetime.now() < blocked_time:
                    return False, self.state.block_reason, details
                else:
                    # Desbloquear
                    self._unblock()

        # 2. Verificar drawdown maximo
        if self.state.current_drawdown >= self.config.max_drawdown_percent:
            self._block(BlockReason.MAX_DRAWDOWN)
            details["status"] = RiskStatus.BLOCKED.value
            return False, BlockReason.MAX_DRAWDOWN.value, details

        # Warning de drawdown
        if self.state.current_drawdown >= self.config.warning_drawdown_percent:
            details["warnings"].append(f"Drawdown em {self.state.current_drawdown:.1f}%")
            details["status"] = RiskStatus.WARNING.value

        # 3. Verificar perda diaria
        today_stats = self._get_today_stats()
        if self.state.current_capital > 0:
            daily_loss_percent = abs(min(0, today_stats.pnl_percent))
            if daily_loss_percent >= self.config.max_daily_loss_percent:
                self._block(BlockReason.DAILY_LOSS_LIMIT)
                details["status"] = RiskStatus.BLOCKED.value
                return False, BlockReason.DAILY_LOSS_LIMIT.value, details

        # 4. Verificar trades diarios
        if today_stats.trades_count >= self.config.max_daily_trades:
            details["warnings"].append("Limite de trades diarios atingido")
            return False, "LIMITE_TRADES_DIARIOS", details

        # 5. Verificar perdas consecutivas
        if self.state.consecutive_losses >= self.config.max_consecutive_losses:
            self._block(BlockReason.CONSECUTIVE_LOSSES)
            details["status"] = RiskStatus.BLOCKED.value
            return False, BlockReason.CONSECUTIVE_LOSSES.value, details

        # 6. Verificar confianca minima
        if confidence < self.config.min_confidence_to_trade:
            details["warnings"].append(f"Confianca baixa: {confidence:.1f}%")
            return False, BlockReason.LOW_CONFIDENCE.value, details

        # 7. Verificar score minimo
        if abs(score) < self.config.min_score_to_trade:
            details["warnings"].append(f"Score baixo: {score:.1f}")
            return False, "SCORE_INSUFICIENTE", details

        # 8. Verificar volatilidade
        if volatility_atr_percent > self.config.max_volatility_atr_percent:
            details["warnings"].append(f"Volatilidade alta: {volatility_atr_percent:.1f}%")
            return False, BlockReason.VOLATILITY_TOO_HIGH.value, details

        # 9. Calcular multiplicador de posicao
        details["position_multiplier"] = self.get_position_multiplier()

        return True, "OK", details

    def get_position_multiplier(self) -> float:
        """
        Retorna multiplicador para tamanho da posicao
        baseado no estado atual de risco
        """
        multiplier = 1.0

        # Reduzir apos perdas consecutivas
        if self.state.consecutive_losses >= self.config.reduction_after_losses:
            # Reduz 25% para cada perda apos o limite
            excess_losses = self.state.consecutive_losses - self.config.reduction_after_losses + 1
            reduction = 0.25 * excess_losses
            multiplier *= max(0.25, 1 - reduction)  # Minimo 25% do tamanho

        # Reduzir se drawdown alto (entre warning e max)
        if self.state.current_drawdown >= self.config.warning_drawdown_percent:
            dd_severity = (
                (self.state.current_drawdown - self.config.warning_drawdown_percent) /
                (self.config.max_drawdown_percent - self.config.warning_drawdown_percent)
            )
            multiplier *= max(0.3, 1 - (dd_severity * 0.5))  # Reduz ate 50%

        # Aumentar apos sequencia de ganhos (max 25% extra)
        if self.state.consecutive_wins >= 3:
            bonus = min(0.25, self.state.consecutive_wins * 0.05)
            multiplier *= (1 + bonus)

        return round(multiplier, 2)

    def calculate_position_size(
        self,
        price: float,
        stop_loss_percent: float = 3.0,
        win_rate: float = 0.60,
        avg_win_loss_ratio: float = 1.5
    ) -> dict:
        """
        Calcula tamanho ideal da posicao

        Metodos:
        1. Fixed Percent: % fixo do capital
        2. Kelly Criterion: Otimo matematico
        3. Risk-Based: Baseado no risco por trade
        """
        capital = self.state.current_capital
        multiplier = self.get_position_multiplier()

        results = {
            "capital": capital,
            "price": price,
            "multiplier": multiplier,
            "methods": {}
        }

        # Metodo 1: Fixed Percent
        fixed_percent = self.config.base_position_percent * multiplier / 100
        fixed_amount = capital * fixed_percent
        fixed_quantity = int(fixed_amount / price) if price > 0 else 0

        results["methods"]["fixed_percent"] = {
            "percent": round(fixed_percent * 100, 2),
            "amount": round(fixed_amount, 2),
            "quantity": fixed_quantity
        }

        # Metodo 2: Kelly Criterion
        if self.config.use_kelly_criterion and win_rate > 0 and avg_win_loss_ratio > 0:
            # Kelly = W - (1-W)/R
            kelly_full = win_rate - ((1 - win_rate) / avg_win_loss_ratio)
            kelly_adjusted = max(0, kelly_full * self.config.kelly_fraction * multiplier)

            # Limitar ao maximo configurado
            kelly_adjusted = min(kelly_adjusted, self.config.max_position_percent / 100)

            kelly_amount = capital * kelly_adjusted
            kelly_quantity = int(kelly_amount / price) if price > 0 else 0

            results["methods"]["kelly"] = {
                "kelly_full": round(kelly_full * 100, 2),
                "kelly_adjusted": round(kelly_adjusted * 100, 2),
                "amount": round(kelly_amount, 2),
                "quantity": kelly_quantity
            }

        # Metodo 3: Risk-Based (quanto perder no stop)
        risk_percent = 2.0 * multiplier / 100  # 2% de risco por trade
        risk_amount = capital * risk_percent
        stop_distance = price * (stop_loss_percent / 100)
        risk_quantity = int(risk_amount / stop_distance) if stop_distance > 0 else 0
        risk_total = risk_quantity * price

        results["methods"]["risk_based"] = {
            "risk_percent": round(risk_percent * 100, 2),
            "risk_amount": round(risk_amount, 2),
            "stop_distance": round(stop_distance, 2),
            "quantity": risk_quantity,
            "total_amount": round(risk_total, 2)
        }

        # Recomendacao: o mais conservador
        quantities = [
            fixed_quantity,
            results["methods"].get("kelly", {}).get("quantity", fixed_quantity),
            risk_quantity
        ]
        recommended_qty = min(q for q in quantities if q > 0) if any(q > 0 for q in quantities) else 0

        # Garantir limites
        max_amount = capital * (self.config.max_position_percent / 100)
        min_amount = capital * (self.config.min_position_percent / 100)

        recommended_amount = recommended_qty * price
        if recommended_amount > max_amount:
            recommended_qty = int(max_amount / price)
        elif recommended_amount < min_amount and recommended_qty > 0:
            recommended_qty = max(1, int(min_amount / price))

        results["recommended"] = {
            "quantity": recommended_qty,
            "amount": round(recommended_qty * price, 2),
            "percent_of_capital": round((recommended_qty * price / capital) * 100, 2) if capital > 0 else 0
        }

        return results

    def register_trade(
        self,
        ticker: str,
        action: str,
        quantity: int,
        entry_price: float,
        exit_price: float = 0,
        pnl: float = 0,
        is_win: bool = None
    ):
        """Registra um trade executado"""

        # Se ainda nao fechou, apenas registra entrada
        if exit_price == 0:
            trade = {
                "ticker": ticker,
                "action": action,
                "quantity": quantity,
                "entry_price": entry_price,
                "exit_price": 0,
                "pnl": 0,
                "pnl_percent": 0,
                "is_win": None,
                "timestamp": datetime.now().isoformat(),
                "status": "OPEN"
            }
        else:
            # Trade fechado
            if pnl == 0 and entry_price > 0:
                if action.upper() == "BUY":
                    pnl = (exit_price - entry_price) * quantity
                else:
                    pnl = (entry_price - exit_price) * quantity

            pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price * quantity > 0 else 0

            if is_win is None:
                is_win = pnl > 0

            trade = {
                "ticker": ticker,
                "action": action,
                "quantity": quantity,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_percent, 2),
                "is_win": is_win,
                "timestamp": datetime.now().isoformat(),
                "status": "CLOSED"
            }

            # Atualizar estatisticas
            self._update_stats(trade)

        # Adicionar ao historico
        self.state.recent_trades.append(trade)
        if len(self.state.recent_trades) > 100:
            self.state.recent_trades = self.state.recent_trades[-100:]

        self.state.last_trade_time = datetime.now().isoformat()
        self._save_state()

        return trade

    def _update_stats(self, trade: dict):
        """Atualiza estatisticas apos trade fechado"""
        is_win = trade.get("is_win", False)
        pnl = trade.get("pnl", 0)
        pnl_percent = trade.get("pnl_percent", 0)

        # Estatisticas gerais
        self.state.total_trades += 1
        self.state.total_pnl += pnl

        if is_win:
            self.state.total_wins += 1
            self.state.consecutive_wins += 1
            self.state.consecutive_losses = 0
        else:
            self.state.total_losses += 1
            self.state.consecutive_losses += 1
            self.state.consecutive_wins = 0

        # Win rate
        if self.state.total_trades > 0:
            self.state.win_rate = (self.state.total_wins / self.state.total_trades) * 100

        # Atualizar capital
        new_capital = self.state.current_capital + pnl
        self.update_capital(new_capital)

        # Estatisticas diarias
        today_stats = self._get_today_stats()
        today_stats.trades_count += 1
        today_stats.pnl += pnl

        if self.state.current_capital > 0:
            today_stats.pnl_percent = (today_stats.pnl / self.state.initial_capital) * 100

        if is_win:
            today_stats.wins += 1
            today_stats.largest_win = max(today_stats.largest_win, pnl)
        else:
            today_stats.losses += 1
            today_stats.largest_loss = min(today_stats.largest_loss, pnl)

        self._update_today_stats(today_stats)

        # Verificar circuit breaker
        if today_stats.pnl_percent <= -self.config.circuit_breaker_loss_percent:
            self._activate_circuit_breaker()

    def _block(self, reason: BlockReason):
        """Bloqueia trading"""
        self.state.status = RiskStatus.BLOCKED.value
        self.state.block_reason = reason.value
        print(f"[RiskManager] BLOQUEADO: {reason.value}")
        self._save_state()

    def _unblock(self):
        """Desbloqueia trading"""
        self.state.status = RiskStatus.OK.value
        self.state.block_reason = BlockReason.NONE.value
        self.state.blocked_until = ""
        print("[RiskManager] Desbloqueado")
        self._save_state()

    def _activate_circuit_breaker(self):
        """Ativa circuit breaker"""
        from datetime import timedelta

        self.state.status = RiskStatus.CIRCUIT_BREAKER.value
        self.state.block_reason = BlockReason.CIRCUIT_BREAKER.value

        unblock_time = datetime.now() + timedelta(hours=self.config.circuit_breaker_hours)
        self.state.blocked_until = unblock_time.isoformat()

        print(f"[RiskManager] CIRCUIT BREAKER ATIVADO! Bloqueado ate {unblock_time}")
        self._save_state()

    def reset_daily_stats(self):
        """Reseta estatisticas diarias (chamar no inicio do dia)"""
        today = date.today().isoformat()
        self.state.daily_stats[today] = DailyStats(date=today).__dict__

        # Desbloquear se era limite diario
        if self.state.block_reason == BlockReason.DAILY_LOSS_LIMIT.value:
            self._unblock()

        self._save_state()

    def reset_all(self, initial_capital: float = None):
        """Reseta completamente o risk manager"""
        capital = initial_capital or self.state.initial_capital
        self.state = RiskState(
            initial_capital=capital,
            current_capital=capital,
            peak_capital=capital
        )
        self._save_state()
        print(f"[RiskManager] Reset completo. Capital: R$ {capital:.2f}")

    def get_status(self) -> dict:
        """Retorna status completo do risk manager"""
        today_stats = self._get_today_stats()

        return {
            "status": self.state.status,
            "block_reason": self.state.block_reason,
            "blocked_until": self.state.blocked_until,
            "capital": {
                "initial": round(self.state.initial_capital, 2),
                "current": round(self.state.current_capital, 2),
                "peak": round(self.state.peak_capital, 2),
                "pnl": round(self.state.current_capital - self.state.initial_capital, 2),
                "pnl_percent": round(
                    ((self.state.current_capital - self.state.initial_capital) / self.state.initial_capital) * 100
                    if self.state.initial_capital > 0 else 0, 2
                )
            },
            "drawdown": {
                "current": round(self.state.current_drawdown, 2),
                "max_reached": round(self.state.max_drawdown_reached, 2),
                "limit": self.config.max_drawdown_percent,
                "warning_level": self.config.warning_drawdown_percent
            },
            "sequences": {
                "consecutive_losses": self.state.consecutive_losses,
                "consecutive_wins": self.state.consecutive_wins,
                "max_consecutive_losses_allowed": self.config.max_consecutive_losses
            },
            "position_multiplier": self.get_position_multiplier(),
            "stats": {
                "total_trades": self.state.total_trades,
                "wins": self.state.total_wins,
                "losses": self.state.total_losses,
                "win_rate": round(self.state.win_rate, 2),
                "total_pnl": round(self.state.total_pnl, 2)
            },
            "today": {
                "trades": today_stats.trades_count,
                "wins": today_stats.wins,
                "losses": today_stats.losses,
                "pnl": round(today_stats.pnl, 2),
                "pnl_percent": round(today_stats.pnl_percent, 2),
                "largest_win": round(today_stats.largest_win, 2),
                "largest_loss": round(today_stats.largest_loss, 2)
            },
            "config": self.config.to_dict(),
            "last_update": self.state.last_update
        }

    def force_unblock(self):
        """Forca desbloqueio (usar com cuidado!)"""
        self._unblock()
        self.state.consecutive_losses = 0
        self._save_state()
        print("[RiskManager] Desbloqueio forcado!")


# Instancia global
risk_manager = RiskManager()


# === Funcoes de conveniencia ===

def can_trade(order_value: float = 0, confidence: float = 100, score: float = 100, volatility: float = 0) -> Tuple[bool, str, dict]:
    """Verifica se pode operar"""
    return risk_manager.check_can_trade(order_value, confidence, score, volatility)

def get_position_size(price: float, stop_loss_percent: float = 3.0) -> dict:
    """Calcula tamanho da posicao"""
    return risk_manager.calculate_position_size(price, stop_loss_percent)

def register_trade(ticker: str, action: str, quantity: int, entry_price: float, exit_price: float = 0, pnl: float = 0):
    """Registra trade"""
    return risk_manager.register_trade(ticker, action, quantity, entry_price, exit_price, pnl)

def get_status() -> dict:
    """Retorna status"""
    return risk_manager.get_status()

def update_capital(new_capital: float):
    """Atualiza capital"""
    risk_manager.update_capital(new_capital)

def reset(initial_capital: float = None):
    """Reset completo"""
    risk_manager.reset_all(initial_capital)

def force_unblock():
    """Forca desbloqueio"""
    risk_manager.force_unblock()


if __name__ == "__main__":
    print("=" * 60)
    print("  NEXUS TRADE PRO - Risk Manager v1.0")
    print("=" * 60)

    # Teste basico
    rm = RiskManager(initial_capital=500.0)

    print("\n[1] Status inicial:")
    status = rm.get_status()
    print(f"  Capital: R$ {status['capital']['current']:.2f}")
    print(f"  Drawdown: {status['drawdown']['current']:.2f}%")
    print(f"  Status: {status['status']}")

    print("\n[2] Verificando se pode operar:")
    can, reason, details = rm.check_can_trade(confidence=70, score=35)
    print(f"  Pode operar: {can}")
    print(f"  Razao: {reason}")
    print(f"  Multiplicador: {details['position_multiplier']}")

    print("\n[3] Calculando position size para PETR4 @ R$ 38.50:")
    size = rm.calculate_position_size(38.50, stop_loss_percent=3.0)
    print(f"  Recomendado: {size['recommended']['quantity']} acoes")
    print(f"  Valor: R$ {size['recommended']['amount']:.2f}")
    print(f"  % do capital: {size['recommended']['percent_of_capital']:.1f}%")

    print("\n[4] Simulando trades:")
    # Trade ganhador
    rm.register_trade("PETR4", "BUY", 10, 38.50, 40.00)
    print("  Trade 1: PETR4 +3.9% -> WIN")

    # Trade perdedor
    rm.register_trade("VALE3", "BUY", 5, 62.00, 60.00)
    print("  Trade 2: VALE3 -3.2% -> LOSS")

    status = rm.get_status()
    print(f"\n  Capital atual: R$ {status['capital']['current']:.2f}")
    print(f"  Drawdown: {status['drawdown']['current']:.2f}%")
    print(f"  Win Rate: {status['stats']['win_rate']:.1f}%")

    print("\n" + "=" * 60)

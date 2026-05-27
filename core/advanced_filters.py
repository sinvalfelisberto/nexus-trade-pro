# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Advanced Filters v1.0
========================================
Filtros avancados para selecao de trades

Filtros:
1. Liquidez: Volume minimo para operar
2. Regime de Mercado: Bull/Bear/Neutro
3. Horario: Melhores horarios para operar
4. Volatilidade: Filtro de ATR
5. Correlacao: Evitar ativos correlacionados
6. Momentum: Forca do movimento
"""

import math
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class MarketRegime(Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRO"
    HIGH_VOLATILITY = "ALTA_VOLATILIDADE"
    LOW_VOLATILITY = "BAIXA_VOLATILIDADE"


class FilterResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


@dataclass
class FilterOutput:
    """Resultado de um filtro"""
    name: str
    result: FilterResult
    value: float
    threshold: float
    message: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "result": self.result.value,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message
        }


@dataclass
class FilterConfig:
    """Configuracao dos filtros"""
    # Liquidez
    min_volume: int = 1_000_000          # Volume minimo diario
    min_volume_avg_ratio: float = 0.8     # Volume atual vs media

    # Regime
    regime_lookback: int = 20             # Dias para detectar regime
    bull_threshold: float = 5.0           # % de alta para BULL
    bear_threshold: float = -5.0          # % de queda para BEAR
    volatility_high_threshold: float = 3.0  # ATR% alto
    volatility_low_threshold: float = 0.5   # ATR% baixo

    # Horario (mercado BR: 10:00 - 17:00)
    market_open: time = time(10, 0)
    market_close: time = time(17, 0)
    best_hours_start: time = time(10, 30)  # Apos abertura volatil
    best_hours_end: time = time(16, 30)    # Antes do fechamento
    avoid_lunch_start: time = time(12, 0)  # Horario de almoco
    avoid_lunch_end: time = time(14, 0)

    # Momentum
    min_momentum: float = 1.0              # % minimo de momentum
    max_momentum: float = 10.0             # % maximo (evitar overextended)

    # Correlacao
    max_correlation: float = 0.7           # Correlacao maxima entre ativos

    # Score minimo
    min_confidence: float = 55.0           # Confianca minima
    min_score: float = 25.0                # Score minimo


class LiquidityFilter:
    """Filtro de liquidez"""

    def __init__(self, config: FilterConfig):
        self.config = config

    def check(self, current_volume: int, avg_volume: float) -> FilterOutput:
        """
        Verifica se o ativo tem liquidez suficiente

        Args:
            current_volume: Volume do dia atual
            avg_volume: Volume medio (20 dias)
        """
        # Volume absoluto
        if current_volume < self.config.min_volume:
            return FilterOutput(
                name="LIQUIDEZ",
                result=FilterResult.FAIL,
                value=current_volume,
                threshold=self.config.min_volume,
                message=f"Volume muito baixo: {current_volume:,} < {self.config.min_volume:,}"
            )

        # Volume relativo
        if avg_volume > 0:
            ratio = current_volume / avg_volume
            if ratio < self.config.min_volume_avg_ratio:
                return FilterOutput(
                    name="LIQUIDEZ",
                    result=FilterResult.WARNING,
                    value=ratio,
                    threshold=self.config.min_volume_avg_ratio,
                    message=f"Volume abaixo da media: {ratio:.1%} da media"
                )

        return FilterOutput(
            name="LIQUIDEZ",
            result=FilterResult.PASS,
            value=current_volume,
            threshold=self.config.min_volume,
            message=f"Volume OK: {current_volume:,}"
        )


class RegimeFilter:
    """Filtro de regime de mercado"""

    def __init__(self, config: FilterConfig):
        self.config = config

    def detect_regime(self, prices: List[float]) -> Tuple[MarketRegime, float]:
        """
        Detecta o regime de mercado atual

        Returns:
            (regime, strength)
        """
        if len(prices) < self.config.regime_lookback:
            return MarketRegime.NEUTRAL, 0

        recent = prices[-self.config.regime_lookback:]

        # Calcular retorno do periodo
        returns_pct = (recent[-1] - recent[0]) / recent[0] * 100

        # Calcular volatilidade
        daily_returns = [(recent[i] - recent[i-1]) / recent[i-1] * 100
                        for i in range(1, len(recent))]
        volatility = math.sqrt(sum(r**2 for r in daily_returns) / len(daily_returns))

        # Determinar regime
        if volatility > self.config.volatility_high_threshold:
            regime = MarketRegime.HIGH_VOLATILITY
            strength = volatility
        elif volatility < self.config.volatility_low_threshold:
            regime = MarketRegime.LOW_VOLATILITY
            strength = volatility
        elif returns_pct >= self.config.bull_threshold:
            regime = MarketRegime.BULL
            strength = returns_pct
        elif returns_pct <= self.config.bear_threshold:
            regime = MarketRegime.BEAR
            strength = abs(returns_pct)
        else:
            regime = MarketRegime.NEUTRAL
            strength = abs(returns_pct)

        return regime, round(strength, 2)

    def check(self, prices: List[float], intended_direction: str = "LONG") -> FilterOutput:
        """
        Verifica se o regime e favoravel para a direcao pretendida

        Args:
            prices: Lista de precos
            intended_direction: "LONG" ou "SHORT"
        """
        regime, strength = self.detect_regime(prices)

        # Regras de regime
        if intended_direction == "LONG":
            if regime == MarketRegime.BEAR:
                return FilterOutput(
                    name="REGIME",
                    result=FilterResult.WARNING,
                    value=strength,
                    threshold=self.config.bear_threshold,
                    message=f"Mercado BEAR - cautela para compras"
                )
            elif regime == MarketRegime.BULL:
                return FilterOutput(
                    name="REGIME",
                    result=FilterResult.PASS,
                    value=strength,
                    threshold=self.config.bull_threshold,
                    message=f"Mercado BULL - favoravel para compras (+{strength:.1f}%)"
                )
        else:  # SHORT
            if regime == MarketRegime.BULL:
                return FilterOutput(
                    name="REGIME",
                    result=FilterResult.WARNING,
                    value=strength,
                    threshold=self.config.bull_threshold,
                    message=f"Mercado BULL - cautela para vendas"
                )
            elif regime == MarketRegime.BEAR:
                return FilterOutput(
                    name="REGIME",
                    result=FilterResult.PASS,
                    value=strength,
                    threshold=self.config.bear_threshold,
                    message=f"Mercado BEAR - favoravel para vendas ({strength:.1f}%)"
                )

        if regime == MarketRegime.HIGH_VOLATILITY:
            return FilterOutput(
                name="REGIME",
                result=FilterResult.WARNING,
                value=strength,
                threshold=self.config.volatility_high_threshold,
                message=f"Alta volatilidade ({strength:.1f}%) - reduzir posicao"
            )

        return FilterOutput(
            name="REGIME",
            result=FilterResult.PASS,
            value=strength,
            threshold=0,
            message=f"Regime {regime.value} - neutro"
        )

    def get_position_multiplier(self, prices: List[float], direction: str = "LONG") -> float:
        """
        Retorna multiplicador de posicao baseado no regime

        Returns:
            Multiplicador (0.5 a 1.5)
        """
        regime, strength = self.detect_regime(prices)

        if direction == "LONG":
            if regime == MarketRegime.BULL:
                return min(1.3, 1.0 + strength / 20)  # Ate +30%
            elif regime == MarketRegime.BEAR:
                return max(0.5, 1.0 - strength / 20)  # Ate -50%
        else:
            if regime == MarketRegime.BEAR:
                return min(1.3, 1.0 + strength / 20)
            elif regime == MarketRegime.BULL:
                return max(0.5, 1.0 - strength / 20)

        if regime == MarketRegime.HIGH_VOLATILITY:
            return 0.7  # Reduzir em alta volatilidade

        return 1.0


class TimeFilter:
    """Filtro de horario"""

    def __init__(self, config: FilterConfig):
        self.config = config

        # Estatisticas de performance por hora (baseado em estudos)
        # Valores representam performance relativa (1.0 = media)
        self.hour_performance = {
            10: 1.15,  # Abertura - boa volatilidade
            11: 1.20,  # Melhor hora
            12: 0.70,  # Almoco - baixa liquidez
            13: 0.75,  # Almoco
            14: 1.05,  # Volta do almoco
            15: 1.10,  # Boa hora
            16: 1.15,  # Pre-fechamento
            17: 0.80,  # Fechamento - spreads maiores
        }

    def is_market_open(self, current_time: time = None) -> bool:
        """Verifica se o mercado esta aberto"""
        if current_time is None:
            current_time = datetime.now().time()

        return self.config.market_open <= current_time <= self.config.market_close

    def is_best_time(self, current_time: time = None) -> bool:
        """Verifica se e um bom horario para operar"""
        if current_time is None:
            current_time = datetime.now().time()

        # Fora do mercado
        if not self.is_market_open(current_time):
            return False

        # Horario de almoco
        if self.config.avoid_lunch_start <= current_time <= self.config.avoid_lunch_end:
            return False

        # Melhor horario
        return self.config.best_hours_start <= current_time <= self.config.best_hours_end

    def check(self, current_time: time = None) -> FilterOutput:
        """Verifica se o horario e adequado para operar"""
        if current_time is None:
            current_time = datetime.now().time()

        if not self.is_market_open(current_time):
            return FilterOutput(
                name="HORARIO",
                result=FilterResult.FAIL,
                value=0,
                threshold=0,
                message=f"Mercado fechado (abre {self.config.market_open})"
            )

        if self.config.avoid_lunch_start <= current_time <= self.config.avoid_lunch_end:
            return FilterOutput(
                name="HORARIO",
                result=FilterResult.WARNING,
                value=0.75,
                threshold=1.0,
                message="Horario de almoco - baixa liquidez"
            )

        if self.is_best_time(current_time):
            hour = current_time.hour
            performance = self.hour_performance.get(hour, 1.0)
            return FilterOutput(
                name="HORARIO",
                result=FilterResult.PASS,
                value=performance,
                threshold=1.0,
                message=f"Horario ideal (performance {performance:.0%})"
            )

        return FilterOutput(
            name="HORARIO",
            result=FilterResult.PASS,
            value=1.0,
            threshold=1.0,
            message="Horario OK"
        )

    def get_hour_multiplier(self, current_time: time = None) -> float:
        """Retorna multiplicador baseado no horario"""
        if current_time is None:
            current_time = datetime.now().time()

        if not self.is_market_open(current_time):
            return 0

        hour = current_time.hour
        return self.hour_performance.get(hour, 1.0)


class MomentumFilter:
    """Filtro de momentum"""

    def __init__(self, config: FilterConfig):
        self.config = config

    def calculate_momentum(self, prices: List[float], period: int = 10) -> float:
        """Calcula momentum (% de variacao)"""
        if len(prices) < period:
            return 0

        return (prices[-1] - prices[-period]) / prices[-period] * 100

    def check(self, prices: List[float], direction: str = "LONG") -> FilterOutput:
        """
        Verifica se o momentum e adequado

        Evita:
        - Momentum muito baixo (sem forca)
        - Momentum muito alto (overextended)
        """
        momentum = self.calculate_momentum(prices)
        abs_momentum = abs(momentum)

        # Momentum muito baixo
        if abs_momentum < self.config.min_momentum:
            return FilterOutput(
                name="MOMENTUM",
                result=FilterResult.WARNING,
                value=abs_momentum,
                threshold=self.config.min_momentum,
                message=f"Momentum baixo: {momentum:.1f}% - sem forca"
            )

        # Momentum muito alto (overextended)
        if abs_momentum > self.config.max_momentum:
            return FilterOutput(
                name="MOMENTUM",
                result=FilterResult.WARNING,
                value=abs_momentum,
                threshold=self.config.max_momentum,
                message=f"Momentum muito alto: {momentum:.1f}% - risco de correcao"
            )

        # Verificar direcao
        if direction == "LONG" and momentum < 0:
            return FilterOutput(
                name="MOMENTUM",
                result=FilterResult.WARNING,
                value=momentum,
                threshold=0,
                message=f"Momentum negativo ({momentum:.1f}%) para compra"
            )
        elif direction == "SHORT" and momentum > 0:
            return FilterOutput(
                name="MOMENTUM",
                result=FilterResult.WARNING,
                value=momentum,
                threshold=0,
                message=f"Momentum positivo ({momentum:.1f}%) para venda"
            )

        return FilterOutput(
            name="MOMENTUM",
            result=FilterResult.PASS,
            value=momentum,
            threshold=self.config.min_momentum,
            message=f"Momentum OK: {momentum:.1f}%"
        )


class VolatilityFilter:
    """Filtro de volatilidade (ATR)"""

    def __init__(self, config: FilterConfig):
        self.config = config

    def calculate_atr_percent(self, prices: List[float], period: int = 14) -> float:
        """Calcula ATR como percentual do preco"""
        if len(prices) < period + 1:
            return 0

        tr_list = []
        for i in range(1, len(prices)):
            high = prices[i] * 1.01  # Simular high
            low = prices[i] * 0.99   # Simular low
            prev_close = prices[i-1]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_list.append(tr)

        atr = sum(tr_list[-period:]) / period
        return (atr / prices[-1]) * 100 if prices[-1] > 0 else 0

    def check(self, prices: List[float]) -> FilterOutput:
        """Verifica se a volatilidade esta em range aceitavel"""
        atr_pct = self.calculate_atr_percent(prices)

        if atr_pct > self.config.volatility_high_threshold:
            return FilterOutput(
                name="VOLATILIDADE",
                result=FilterResult.WARNING,
                value=atr_pct,
                threshold=self.config.volatility_high_threshold,
                message=f"Volatilidade alta: {atr_pct:.2f}% - reduzir posicao"
            )

        if atr_pct < self.config.volatility_low_threshold:
            return FilterOutput(
                name="VOLATILIDADE",
                result=FilterResult.WARNING,
                value=atr_pct,
                threshold=self.config.volatility_low_threshold,
                message=f"Volatilidade muito baixa: {atr_pct:.2f}% - pouco movimento"
            )

        return FilterOutput(
            name="VOLATILIDADE",
            result=FilterResult.PASS,
            value=atr_pct,
            threshold=self.config.volatility_high_threshold,
            message=f"Volatilidade OK: {atr_pct:.2f}%"
        )


class AdvancedFilterManager:
    """
    Gerenciador de filtros avancados

    Combina todos os filtros e retorna decisao final
    """

    def __init__(self, config: FilterConfig = None):
        self.config = config or FilterConfig()

        self.liquidity = LiquidityFilter(self.config)
        self.regime = RegimeFilter(self.config)
        self.time = TimeFilter(self.config)
        self.momentum = MomentumFilter(self.config)
        self.volatility = VolatilityFilter(self.config)

    def run_all_filters(
        self,
        prices: List[float],
        current_volume: int,
        avg_volume: float,
        direction: str = "LONG",
        current_time: time = None
    ) -> Dict:
        """
        Executa todos os filtros

        Returns:
            {
                "can_trade": bool,
                "filters": [...],
                "warnings": [...],
                "multiplier": float,
                "summary": str
            }
        """
        results = []
        warnings = []
        can_trade = True

        # 1. Liquidez
        liq = self.liquidity.check(current_volume, avg_volume)
        results.append(liq.to_dict())
        if liq.result == FilterResult.FAIL:
            can_trade = False
        elif liq.result == FilterResult.WARNING:
            warnings.append(liq.message)

        # 2. Regime
        reg = self.regime.check(prices, direction)
        results.append(reg.to_dict())
        if reg.result == FilterResult.FAIL:
            can_trade = False
        elif reg.result == FilterResult.WARNING:
            warnings.append(reg.message)

        # 3. Horario
        tim = self.time.check(current_time)
        results.append(tim.to_dict())
        if tim.result == FilterResult.FAIL:
            can_trade = False
        elif tim.result == FilterResult.WARNING:
            warnings.append(tim.message)

        # 4. Momentum
        mom = self.momentum.check(prices, direction)
        results.append(mom.to_dict())
        if mom.result == FilterResult.WARNING:
            warnings.append(mom.message)

        # 5. Volatilidade
        vol = self.volatility.check(prices)
        results.append(vol.to_dict())
        if vol.result == FilterResult.WARNING:
            warnings.append(vol.message)

        # Calcular multiplicador combinado
        regime_mult = self.regime.get_position_multiplier(prices, direction)
        time_mult = self.time.get_hour_multiplier(current_time)
        combined_mult = regime_mult * time_mult

        # Reduzir por warnings
        warning_penalty = 1.0 - (len(warnings) * 0.1)  # -10% por warning
        final_mult = max(0.3, combined_mult * warning_penalty)

        # Resumo
        passed = sum(1 for r in results if r["result"] == "PASS")
        total = len(results)

        if can_trade:
            if len(warnings) == 0:
                summary = f"APROVADO ({passed}/{total} filtros OK)"
            else:
                summary = f"APROVADO COM RESSALVAS ({len(warnings)} warnings)"
        else:
            failed = [r["name"] for r in results if r["result"] == "FAIL"]
            summary = f"BLOQUEADO - Filtros falharam: {', '.join(failed)}"

        return {
            "can_trade": can_trade,
            "filters": results,
            "warnings": warnings,
            "multiplier": round(final_mult, 2),
            "regime": self.regime.detect_regime(prices)[0].value,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }

    def quick_check(
        self,
        prices: List[float],
        volume: int = 5_000_000,
        direction: str = "LONG"
    ) -> Tuple[bool, float, str]:
        """
        Verificacao rapida

        Returns:
            (can_trade, multiplier, summary)
        """
        result = self.run_all_filters(
            prices=prices,
            current_volume=volume,
            avg_volume=volume,
            direction=direction
        )
        return result["can_trade"], result["multiplier"], result["summary"]


# Instancia global
filter_manager = AdvancedFilterManager()


# Funcoes de conveniencia
def check_filters(
    prices: List[float],
    volume: int,
    avg_volume: float,
    direction: str = "LONG"
) -> dict:
    """Executa todos os filtros"""
    return filter_manager.run_all_filters(prices, volume, avg_volume, direction)

def quick_filter_check(prices: List[float], volume: int = 5_000_000, direction: str = "LONG"):
    """Verificacao rapida de filtros"""
    return filter_manager.quick_check(prices, volume, direction)

def detect_regime(prices: List[float]) -> dict:
    """Detecta regime de mercado"""
    regime, strength = filter_manager.regime.detect_regime(prices)
    return {"regime": regime.value, "strength": strength}

def is_good_time_to_trade() -> dict:
    """Verifica se e um bom horario"""
    result = filter_manager.time.check()
    return {
        "is_good": result.result == FilterResult.PASS,
        "market_open": filter_manager.time.is_market_open(),
        "message": result.message
    }


if __name__ == "__main__":
    import random

    print("=" * 60)
    print("  TESTE ADVANCED FILTERS")
    print("=" * 60)

    # Gerar dados de teste (tendencia de alta)
    prices = [40.0]
    for _ in range(30):
        change = random.uniform(-0.02, 0.025)
        prices.append(round(prices[-1] * (1 + change), 2))

    print(f"\nPreco inicial: R$ {prices[0]:.2f}")
    print(f"Preco atual: R$ {prices[-1]:.2f}")
    print(f"Variacao: {((prices[-1] - prices[0]) / prices[0] * 100):.1f}%")

    # Testar filtros
    print("\n[1] Testando todos os filtros (LONG)...")
    result = check_filters(
        prices=prices,
        volume=10_000_000,
        avg_volume=8_000_000,
        direction="LONG"
    )

    print(f"\nPode operar: {result['can_trade']}")
    print(f"Regime: {result['regime']}")
    print(f"Multiplicador: {result['multiplier']}")
    print(f"Resumo: {result['summary']}")

    print("\n[Filtros]")
    for f in result["filters"]:
        status = "OK" if f["result"] == "PASS" else "AVISO" if f["result"] == "WARNING" else "FALHA"
        print(f"  {f['name']}: {status} - {f['message']}")

    if result["warnings"]:
        print("\n[Avisos]")
        for w in result["warnings"]:
            print(f"  - {w}")

    # Verificar horario
    print("\n[2] Verificando horario...")
    time_check = is_good_time_to_trade()
    print(f"  Mercado aberto: {time_check['market_open']}")
    print(f"  Bom horario: {time_check['is_good']}")
    print(f"  Mensagem: {time_check['message']}")

    print("\n" + "=" * 60)

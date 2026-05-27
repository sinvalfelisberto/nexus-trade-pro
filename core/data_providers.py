# -*- coding: utf-8 -*-
"""
NEXUS TRADE PRO - Data Providers v1.0
======================================
Multiplas fontes de dados para cotacoes e historico

Provedores:
- Yahoo Finance (yfinance) - GRATUITO, SEM LIMITES
- brapi.dev - 15.000 req/mes
- Fallback simulado - Quando offline

Prioridade: Yahoo Finance > brapi.dev > Simulado
"""

import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

# Cache simples
_data_cache = {}
def get_cache(key: str, ttl: int = 60):
    if key in _data_cache:
        ts, val = _data_cache[key]
        if (datetime.now() - ts).seconds < ttl:
            return val
    return None

def set_cache(key: str, val):
    _data_cache[key] = (datetime.now(), val)


class DataSource(Enum):
    YAHOO = "YAHOO"
    BRAPI = "BRAPI"
    SIMULATED = "SIMULATED"
    CACHE = "CACHE"


@dataclass
class Quote:
    """Cotacao de um ativo"""
    ticker: str
    price: float
    change: float
    change_percent: float
    volume: int
    high: float
    low: float
    open: float
    previous_close: float
    source: DataSource
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "price": self.price,
            "change": self.change,
            "changePercent": self.change_percent,
            "volume": self.volume,
            "high": self.high,
            "low": self.low,
            "open": self.open,
            "previousClose": self.previous_close,
            "source": self.source.value,
            "timestamp": self.timestamp
        }


@dataclass
class HistoricalData:
    """Dados historicos"""
    ticker: str
    data: List[Dict]
    source: DataSource
    period: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "data": self.data,
            "source": self.source.value,
            "period": self.period,
            "count": len(self.data)
        }


class DataProvider(ABC):
    """Interface base para provedores de dados"""

    @abstractmethod
    async def get_quote(self, ticker: str) -> Optional[Quote]:
        pass

    @abstractmethod
    async def get_history(self, ticker: str, days: int) -> Optional[HistoricalData]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class YahooFinanceProvider(DataProvider):
    """
    Provedor Yahoo Finance via yfinance
    GRATUITO e SEM LIMITES!
    """

    def __init__(self):
        self._yf = None
        self._available = False
        self._init_yfinance()

    def _init_yfinance(self):
        """Inicializa yfinance se disponivel"""
        try:
            import yfinance as yf
            self._yf = yf
            self._available = True
            print("[DataProvider] Yahoo Finance: OK")
        except ImportError:
            print("[DataProvider] Yahoo Finance: NAO INSTALADO (pip install yfinance)")
            self._available = False

    def _convert_ticker(self, ticker: str) -> str:
        """Converte ticker BR para formato Yahoo (adiciona .SA)"""
        ticker = ticker.upper().strip()
        # Ja tem sufixo?
        if ticker.endswith(".SA") or ticker.endswith(".SAO"):
            return ticker
        # ETFs e FIIs
        if ticker.endswith("11"):
            return f"{ticker}.SA"
        # Acoes
        return f"{ticker}.SA"

    def is_available(self) -> bool:
        return self._available

    async def get_quote(self, ticker: str) -> Optional[Quote]:
        if not self._available:
            return None

        try:
            yahoo_ticker = self._convert_ticker(ticker)
            stock = self._yf.Ticker(yahoo_ticker)

            # Tentar fast_info primeiro (mais rapido)
            try:
                info = stock.fast_info
                price = info.last_price
                prev_close = info.previous_close
                change = price - prev_close if prev_close else 0
                change_pct = (change / prev_close * 100) if prev_close else 0

                return Quote(
                    ticker=ticker.upper(),
                    price=round(price, 2),
                    change=round(change, 2),
                    change_percent=round(change_pct, 2),
                    volume=int(info.last_volume or 0),
                    high=round(info.day_high or price, 2),
                    low=round(info.day_low or price, 2),
                    open=round(info.open or price, 2),
                    previous_close=round(prev_close or price, 2),
                    source=DataSource.YAHOO,
                    timestamp=datetime.now().isoformat()
                )
            except:
                # Fallback para history
                hist = stock.history(period="1d")
                if hist.empty:
                    return None

                last = hist.iloc[-1]
                price = float(last['Close'])
                prev = float(hist.iloc[0]['Open']) if len(hist) > 0 else price

                return Quote(
                    ticker=ticker.upper(),
                    price=round(price, 2),
                    change=round(price - prev, 2),
                    change_percent=round((price - prev) / prev * 100 if prev else 0, 2),
                    volume=int(last['Volume']),
                    high=round(float(last['High']), 2),
                    low=round(float(last['Low']), 2),
                    open=round(float(last['Open']), 2),
                    previous_close=round(prev, 2),
                    source=DataSource.YAHOO,
                    timestamp=datetime.now().isoformat()
                )

        except Exception as e:
            print(f"[Yahoo] Erro ao buscar {ticker}: {e}")
            return None

    async def get_history(self, ticker: str, days: int) -> Optional[HistoricalData]:
        if not self._available:
            return None

        try:
            yahoo_ticker = self._convert_ticker(ticker)
            stock = self._yf.Ticker(yahoo_ticker)

            # Mapear dias para periodo
            if days <= 5:
                period = "5d"
            elif days <= 30:
                period = "1mo"
            elif days <= 90:
                period = "3mo"
            elif days <= 180:
                period = "6mo"
            elif days <= 365:
                period = "1y"
            else:
                period = "2y"

            hist = stock.history(period=period)

            if hist.empty:
                return None

            data = []
            for idx, row in hist.iterrows():
                data.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(float(row['Open']), 2),
                    "high": round(float(row['High']), 2),
                    "low": round(float(row['Low']), 2),
                    "close": round(float(row['Close']), 2),
                    "volume": int(row['Volume'])
                })

            return HistoricalData(
                ticker=ticker.upper(),
                data=data[-days:],
                source=DataSource.YAHOO,
                period=period
            )

        except Exception as e:
            print(f"[Yahoo] Erro ao buscar historico {ticker}: {e}")
            return None


class BrapiProvider(DataProvider):
    """
    Provedor brapi.dev
    15.000 requisicoes/mes
    """

    def __init__(self, token: str = ""):
        self._token = token or os.getenv("BRAPI_TOKEN", "")
        self._available = bool(self._token)
        if self._available:
            print("[DataProvider] brapi.dev: OK")
        else:
            print("[DataProvider] brapi.dev: SEM TOKEN")

    def is_available(self) -> bool:
        return self._available

    async def get_quote(self, ticker: str) -> Optional[Quote]:
        if not self._available:
            return None

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"https://brapi.dev/api/quote/{ticker}",
                    params={"token": self._token}
                )
                data = r.json()

                if "results" in data and data["results"]:
                    result = data["results"][0]
                    return Quote(
                        ticker=ticker.upper(),
                        price=result.get("regularMarketPrice", 0),
                        change=result.get("regularMarketChange", 0),
                        change_percent=result.get("regularMarketChangePercent", 0),
                        volume=result.get("regularMarketVolume", 0),
                        high=result.get("regularMarketDayHigh", 0),
                        low=result.get("regularMarketDayLow", 0),
                        open=result.get("regularMarketOpen", 0),
                        previous_close=result.get("regularMarketPreviousClose", 0),
                        source=DataSource.BRAPI,
                        timestamp=datetime.now().isoformat()
                    )
        except Exception as e:
            print(f"[brapi] Erro ao buscar {ticker}: {e}")
        return None

    async def get_history(self, ticker: str, days: int) -> Optional[HistoricalData]:
        if not self._available:
            return None

        try:
            import httpx

            # Mapear dias para range
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

            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    f"https://brapi.dev/api/quote/{ticker}",
                    params={"token": self._token, "range": range_param, "interval": "1d"}
                )
                data = r.json()

                if "results" in data and data["results"]:
                    hist = data["results"][0].get("historicalDataPrice", [])
                    if hist:
                        return HistoricalData(
                            ticker=ticker.upper(),
                            data=hist[-days:],
                            source=DataSource.BRAPI,
                            period=range_param
                        )
        except Exception as e:
            print(f"[brapi] Erro ao buscar historico {ticker}: {e}")
        return None


class SimulatedProvider(DataProvider):
    """
    Provedor simulado para quando APIs estao offline
    Dados baseados em precos reais com variacao aleatoria
    """

    # Precos base reais (atualizados)
    BASE_PRICES = {
        "PETR4": 38.50, "PETR3": 35.80, "VALE3": 62.00, "ITUB4": 32.00,
        "BBDC4": 13.50, "BBAS3": 28.00, "WEGE3": 52.00, "ABEV3": 12.50,
        "B3SA3": 12.00, "RENT3": 45.00, "MGLU3": 2.50, "PRIO3": 45.00,
        "ELET3": 42.00, "ELET6": 45.00, "SUZB3": 58.00, "CMIG4": 12.00,
        "CPLE6": 10.50, "ENEV3": 14.00, "AZUL4": 5.50, "GOLL4": 1.80,
        "CVCB3": 2.20, "IRBR3": 1.50, "COGN3": 1.80, "LWSA3": 5.00,
        "LREN3": 18.00, "PETZ3": 4.50, "HAPV3": 3.80, "RDOR3": 28.00,
        "TOTS3": 30.00, "VIVT3": 52.00, "TIMS3": 16.00, "CSNA3": 12.00,
        "GGBR4": 18.00, "USIM5": 7.50, "JBSS3": 35.00, "BRFS3": 22.00,
        "BOVA11": 128.00, "IVVB11": 280.00, "SMAL11": 95.00,
        "HGLG11": 160.00, "MXRF11": 10.50, "KNCR11": 100.00,
    }

    def __init__(self):
        self._prices = self.BASE_PRICES.copy()
        print("[DataProvider] Simulado: OK (fallback)")

    def is_available(self) -> bool:
        return True  # Sempre disponivel

    def _get_base_price(self, ticker: str) -> float:
        ticker = ticker.upper()
        if ticker in self._prices:
            return self._prices[ticker]
        # Gerar preco aleatorio para ticker desconhecido
        return random.uniform(5, 100)

    def _add_variation(self, price: float, max_pct: float = 2.0) -> float:
        """Adiciona variacao aleatoria"""
        variation = random.uniform(-max_pct, max_pct) / 100
        return round(price * (1 + variation), 2)

    async def get_quote(self, ticker: str) -> Optional[Quote]:
        base = self._get_base_price(ticker)
        price = self._add_variation(base, 1.5)
        prev = self._add_variation(base, 0.5)
        change = price - prev

        return Quote(
            ticker=ticker.upper(),
            price=price,
            change=round(change, 2),
            change_percent=round((change / prev) * 100 if prev else 0, 2),
            volume=random.randint(1000000, 50000000),
            high=round(price * 1.02, 2),
            low=round(price * 0.98, 2),
            open=prev,
            previous_close=prev,
            source=DataSource.SIMULATED,
            timestamp=datetime.now().isoformat()
        )

    async def get_history(self, ticker: str, days: int) -> Optional[HistoricalData]:
        base = self._get_base_price(ticker)
        data = []

        current_price = base
        for i in range(days):
            date = datetime.now() - timedelta(days=days - i - 1)

            # Variacao diaria
            daily_change = random.uniform(-0.03, 0.035)
            current_price *= (1 + daily_change)
            current_price = max(current_price, base * 0.5)  # Limite inferior

            high = current_price * random.uniform(1.01, 1.03)
            low = current_price * random.uniform(0.97, 0.99)
            open_price = current_price * random.uniform(0.99, 1.01)

            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(current_price, 2),
                "volume": random.randint(1000000, 30000000)
            })

        return HistoricalData(
            ticker=ticker.upper(),
            data=data,
            source=DataSource.SIMULATED,
            period=f"{days}d"
        )


class DataManager:
    """
    Gerenciador de dados com fallback automatico

    Prioridade:
    1. Cache (se disponivel e valido)
    2. Yahoo Finance (gratuito, sem limites)
    3. brapi.dev (15k req/mes)
    4. Simulado (sempre disponivel)
    """

    def __init__(self, brapi_token: str = ""):
        self.yahoo = YahooFinanceProvider()
        self.brapi = BrapiProvider(brapi_token)
        self.simulated = SimulatedProvider()

        # Estatisticas
        self.stats = {
            "yahoo_calls": 0,
            "yahoo_errors": 0,
            "brapi_calls": 0,
            "brapi_errors": 0,
            "simulated_calls": 0,
            "cache_hits": 0
        }

    async def get_quote(self, ticker: str, cache_ttl: int = 60) -> dict:
        """
        Busca cotacao com fallback automatico
        """
        ticker = ticker.upper()
        cache_key = f"quote_{ticker}"

        # Tentar cache
        cached = get_cache(cache_key, cache_ttl)
        if cached:
            self.stats["cache_hits"] += 1
            cached["from_cache"] = True
            return cached

        # Tentar Yahoo Finance
        if self.yahoo.is_available():
            self.stats["yahoo_calls"] += 1
            quote = await self.yahoo.get_quote(ticker)
            if quote:
                result = quote.to_dict()
                set_cache(cache_key, result)
                return result
            self.stats["yahoo_errors"] += 1

        # Tentar brapi.dev
        if self.brapi.is_available():
            self.stats["brapi_calls"] += 1
            quote = await self.brapi.get_quote(ticker)
            if quote:
                result = quote.to_dict()
                set_cache(cache_key, result)
                return result
            self.stats["brapi_errors"] += 1

        # Fallback simulado
        self.stats["simulated_calls"] += 1
        quote = await self.simulated.get_quote(ticker)
        result = quote.to_dict()
        result["warning"] = "Dados simulados - APIs indisponiveis"
        return result

    async def get_history(self, ticker: str, days: int = 30, cache_ttl: int = 300) -> dict:
        """
        Busca historico com fallback automatico
        """
        ticker = ticker.upper()
        cache_key = f"hist_{ticker}_{days}"

        # Tentar cache
        cached = get_cache(cache_key, cache_ttl)
        if cached:
            self.stats["cache_hits"] += 1
            cached["from_cache"] = True
            return cached

        # Tentar Yahoo Finance
        if self.yahoo.is_available():
            self.stats["yahoo_calls"] += 1
            hist = await self.yahoo.get_history(ticker, days)
            if hist:
                result = hist.to_dict()
                set_cache(cache_key, result)
                return result
            self.stats["yahoo_errors"] += 1

        # Tentar brapi.dev
        if self.brapi.is_available():
            self.stats["brapi_calls"] += 1
            hist = await self.brapi.get_history(ticker, days)
            if hist:
                result = hist.to_dict()
                set_cache(cache_key, result)
                return result
            self.stats["brapi_errors"] += 1

        # Fallback simulado
        self.stats["simulated_calls"] += 1
        hist = await self.simulated.get_history(ticker, days)
        result = hist.to_dict()
        result["warning"] = "Dados simulados - APIs indisponiveis"
        return result

    async def get_quotes_batch(self, tickers: List[str]) -> dict:
        """Busca cotacoes de multiplos ativos"""
        results = {}
        for ticker in tickers:
            results[ticker.upper()] = await self.get_quote(ticker)
        return {"quotes": results, "count": len(results)}

    def get_stats(self) -> dict:
        """Retorna estatisticas de uso"""
        total_calls = (
            self.stats["yahoo_calls"] +
            self.stats["brapi_calls"] +
            self.stats["simulated_calls"]
        )
        return {
            "providers": {
                "yahoo": {
                    "available": self.yahoo.is_available(),
                    "calls": self.stats["yahoo_calls"],
                    "errors": self.stats["yahoo_errors"],
                    "success_rate": round(
                        (self.stats["yahoo_calls"] - self.stats["yahoo_errors"]) /
                        max(self.stats["yahoo_calls"], 1) * 100, 1
                    )
                },
                "brapi": {
                    "available": self.brapi.is_available(),
                    "calls": self.stats["brapi_calls"],
                    "errors": self.stats["brapi_errors"],
                    "success_rate": round(
                        (self.stats["brapi_calls"] - self.stats["brapi_errors"]) /
                        max(self.stats["brapi_calls"], 1) * 100, 1
                    )
                },
                "simulated": {
                    "available": True,
                    "calls": self.stats["simulated_calls"]
                }
            },
            "cache_hits": self.stats["cache_hits"],
            "total_calls": total_calls,
            "cache_hit_rate": round(
                self.stats["cache_hits"] / max(total_calls + self.stats["cache_hits"], 1) * 100, 1
            )
        }


# Instancia global
data_manager = DataManager()


# Funcoes de conveniencia
async def get_quote(ticker: str) -> dict:
    return await data_manager.get_quote(ticker)

async def get_history(ticker: str, days: int = 30) -> dict:
    return await data_manager.get_history(ticker, days)

async def get_quotes_batch(tickers: List[str]) -> dict:
    return await data_manager.get_quotes_batch(tickers)

def get_provider_stats() -> dict:
    return data_manager.get_stats()


if __name__ == "__main__":
    import asyncio

    async def test():
        print("=" * 60)
        print("  TESTE DOS DATA PROVIDERS")
        print("=" * 60)

        dm = DataManager()

        # Testar cotacao
        print("\n[1] Testando cotacao PETR4...")
        quote = await dm.get_quote("PETR4")
        print(f"  Preco: R$ {quote['price']}")
        print(f"  Fonte: {quote['source']}")

        # Testar historico
        print("\n[2] Testando historico VALE3 (30 dias)...")
        hist = await dm.get_history("VALE3", 30)
        print(f"  Pontos: {hist['count']}")
        print(f"  Fonte: {hist['source']}")

        # Testar batch
        print("\n[3] Testando batch...")
        batch = await dm.get_quotes_batch(["ITUB4", "BBDC4", "WEGE3"])
        for ticker, data in batch["quotes"].items():
            print(f"  {ticker}: R$ {data['price']} ({data['source']})")

        # Estatisticas
        print("\n[4] Estatisticas:")
        stats = dm.get_stats()
        for provider, info in stats["providers"].items():
            status = "OK" if info.get("available") else "OFF"
            print(f"  {provider}: {status} - {info.get('calls', 0)} chamadas")

        print("\n" + "=" * 60)

    asyncio.run(test())

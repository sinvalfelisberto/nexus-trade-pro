"""
NEXUS TRADE PRO — Configuracao centralizada via .env

Todos os modulos leem configuracao por aqui, garantindo que:
- o .env da raiz do projeto e sempre o usado, independente do diretorio atual;
- os valores do .env tem prioridade sobre variaveis ja definidas no sistema;
- alteracoes no .env sao detectadas (pela data de modificacao) e recarregadas
  na proxima leitura, sem reiniciar o processo.

Uso:
    import env_config as cfg
    token = cfg.get_str("BRAPI_TOKEN")
    port = cfg.get_int("SERVER_PORT", 8000)
"""
import os
from dotenv import dotenv_values

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))

_mtime = None
_loaded_keys = set()


def reload_if_changed() -> bool:
    """Recarrega o .env se ele mudou desde a ultima leitura. Retorna True se recarregou."""
    global _mtime, _loaded_keys
    try:
        mtime = os.path.getmtime(ENV_PATH)
    except OSError:
        return False
    if mtime == _mtime:
        return False

    values = {k: v for k, v in dotenv_values(ENV_PATH).items() if v is not None}
    # Chaves removidas do .env deixam de valer
    for key in _loaded_keys - values.keys():
        os.environ.pop(key, None)
    os.environ.update(values)
    _loaded_keys = set(values)
    if _mtime is not None:
        print(f"[config] .env recarregado ({len(values)} variaveis)")
    _mtime = mtime
    return True


def get_str(key: str, default: str = "") -> str:
    reload_if_changed()
    value = os.environ.get(key, "").strip()
    return value if value else default


def get_float(key: str, default: float) -> float:
    try:
        return float(get_str(key) or default)
    except ValueError:
        print(f"[config] {key} invalido no .env, usando {default}")
        return default


def get_int(key: str, default: int) -> int:
    try:
        return int(float(get_str(key) or default))
    except ValueError:
        print(f"[config] {key} invalido no .env, usando {default}")
        return default


def get_bool(key: str, default: bool = False) -> bool:
    value = get_str(key)
    if not value:
        return default
    return value.lower() in ("1", "true", "yes", "sim", "on")


def server_url() -> str:
    """URL local do servidor HTTP, montada a partir de SERVER_PORT"""
    return f"http://localhost:{get_int('SERVER_PORT', 8000)}"


def public_settings() -> dict:
    """Configuracoes nao sensiveis expostas ao dashboard (nunca inclua tokens/senhas aqui)"""
    return {
        "trading_mode": get_str("TRADING_MODE", "PAPER"),
        "initial_capital": get_float("INITIAL_CAPITAL", 500.0),
        "max_order_value": get_float("MAX_ORDER_VALUE", 300.0),
        "daily_loss_limit": get_float("DAILY_LOSS_LIMIT", 150.0),
        "risk_per_trade": get_float("RISK_PER_TRADE", 1.0),
        "max_positions": get_int("MAX_POSITIONS", 3),
        "stop_loss_percent": get_float("STOP_LOSS_PERCENT", 4.0),
        "take_profit_percent": get_float("TAKE_PROFIT_PERCENT", 8.0),
        "min_confidence": get_int("MIN_CONFIDENCE", 55),
        "trading_start": get_str("TRADING_START", "10:00"),
        "trading_end": get_str("TRADING_END", "16:30"),
    }


reload_if_changed()

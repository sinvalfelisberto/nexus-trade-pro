#!/usr/bin/env bash
# =============================================================
# NEXUS TRADE PRO - Atualizacao diaria das cotacoes (historico B3)
# =============================================================
# Procura no banco (DB_OLD_* do .env) os pregoes que faltam ou estao
# incompletos e importa dos arquivos oficiais da B3 (COTAHIST).
#
# Uso:
#   scripts/atualizar_cotacoes.sh             # atualiza
#   scripts/atualizar_cotacoes.sh --verificar # so lista o que falta
#
# Agendamento diario (cron), ex.: todo dia as 07:00:
#   0 7 * * * /caminho/do/projeto/scripts/atualizar_cotacoes.sh
#
# Log: logs/atualizar_cotacoes.log
# =============================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

# Usa o venv do projeto, se existir
if [ -x "$ROOT/venv/bin/python3" ]; then
    PYTHON="$ROOT/venv/bin/python3"
else
    PYTHON="$(command -v python3)"
fi

MODE="--atualizar"
[ "${1:-}" = "--verificar" ] && MODE="--verificar"

mkdir -p "$ROOT/logs"
LOG="$ROOT/logs/atualizar_cotacoes.log"

{
    echo "===== $(date '+%d/%m/%Y %H:%M:%S') ($MODE) ====="
    "$PYTHON" -u "$ROOT/core/b3_history.py" "$MODE" 2>&1 | tr '\r' '\n' | grep -v 'linhas\.\.\.$'
    STATUS=${PIPESTATUS[0]}
    echo "===== fim (codigo $STATUS) ====="
    echo
    exit "$STATUS"
} 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"

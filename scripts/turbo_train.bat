@echo off
chcp 65001 >nul
cls
echo ══════════════════════════════════════════════════════════════════════
echo   NEXUS TRADE PRO - TURBO TRAINING v3.0
echo ══════════════════════════════════════════════════════════════════════
echo.
echo   Algoritmos de Otimizacao:
echo   [1] Genetic Algorithm (exploracao global)
echo   [2] Simulated Annealing (refinamento)
echo   [3] Particle Swarm Optimization (exploracao adicional)
echo.
echo   Multi-Objetivo: Win Rate + Profit Factor + Sharpe Ratio
echo.
echo ══════════════════════════════════════════════════════════════════════
echo.

:: Ir para a pasta raiz do projeto
cd /d "%~dp0\.."

REM Verificar se servidor está rodando
curl -s http://localhost:8000/api/status >nul 2>&1
if errorlevel 1 (
    echo [!] Servidor nao esta rodando. Iniciando...
    echo.
    start "NexusTrade Server" cmd /c "python core\server_fastmcp.py http"
    echo Aguardando servidor iniciar...
    timeout /t 5 /nobreak >nul
)

echo [*] Iniciando TURBO TRAINING...
echo.

python training\train_turbo.py

echo.
echo ══════════════════════════════════════════════════════════════════════
echo   Treinamento TURBO concluido!
echo.
echo   Para aplicar os novos pesos, reinicie o servidor.
echo ══════════════════════════════════════════════════════════════════════
echo.
pause

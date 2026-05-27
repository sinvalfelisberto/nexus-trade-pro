@echo off
chcp 65001 >nul
cls
echo ═══════════════════════════════════════════════════════════════════
echo   NEXUS TRADE PRO - Sistema de Treinamento Avancado v2.0
echo ═══════════════════════════════════════════════════════════════════
echo.
echo   Recursos:
echo   - Gradient Descent com Momentum
echo   - Ensemble de Estrategias
echo   - Walk-Forward Optimization
echo   - Regime Detection (Bull/Bear/Neutro)
echo   - Early Stopping
echo.
echo ═══════════════════════════════════════════════════════════════════
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

echo [*] Iniciando treinamento avancado...
echo.

python training\train_bot_advanced.py

echo.
echo ═══════════════════════════════════════════════════════════════════
echo   Treinamento concluido!
echo
echo   Arquivos gerados em data\:
echo   - training_results.json (resultados completos)
echo   - trained_weights.js (pesos para o dashboard)
echo.
echo   Reinicie o servidor para aplicar os novos pesos.
echo ═══════════════════════════════════════════════════════════════════
echo.
pause

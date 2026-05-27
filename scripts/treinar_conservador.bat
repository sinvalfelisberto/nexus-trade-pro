@echo off
echo ============================================
echo   NEXUS TRADE PRO - TREINAMENTO CONSERVADOR
echo ============================================
echo.
echo Este treinamento usa:
echo   - Walk-Forward Validation (70/15/15)
echo   - Penalizacao de overfitting
echo   - Metricas realistas
echo   - Modelo simplificado (4 indicadores)
echo.

:: Ir para a pasta raiz do projeto
cd /d "%~dp0\.."

python training\train_conservative.py
echo.
echo Treinamento concluido!
pause

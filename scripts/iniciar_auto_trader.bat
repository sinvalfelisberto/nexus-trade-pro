@echo off
title NEXUS AUTO TRADER v3.5
color 0B

echo ============================================================
echo   NEXUS TRADE PRO - AUTO TRADER v3.5
echo ============================================================
echo.
echo   Este bot executa ciclos automaticos de:
echo   1. Scan do mercado (15 ativos mais liquidos)
echo   2. Analise de indicadores (Stoch, ADX, MACD)
echo   3. Geracao de sinais de compra/venda
echo   4. Execucao de trades (simulado ou real)
echo   5. Monitoramento de posicoes (stop/take)
echo.
echo ============================================================
echo   MODOS DISPONIVEIS:
echo ============================================================
echo.
echo   1. FORWARD TEST (Simulacao)
echo      - RECOMENDADO para comecar
echo      - Registra trades sem usar dinheiro real
echo      - Meta: 100+ trades com win rate maior que 50%%
echo.
echo   2. LIVE (Operacao Real)
echo      - APENAS apos validacao do forward test
echo      - Requer MT5 configurado no .env
echo      - Comece com apenas R$500-1000
echo.
echo   3. VERIFICAR STATUS
echo      - Mostra estatisticas do forward test
echo.

:: Ir para a pasta raiz do projeto (um nivel acima de scripts)
cd /d "%~dp0\.."

set /p MODO="Escolha o modo (1, 2 ou 3): "

if "%MODO%"=="1" (
    echo.
    echo ============================================================
    echo   INICIANDO FORWARD TEST
    echo ============================================================
    echo.
    echo   Horario de operacao: 10:00-16:30 (exceto 12:00-13:30)
    echo   Ciclo de scan: a cada 60 segundos
    echo   Posicoes maximas: 3 simultaneas
    echo.
    echo   Pressione Ctrl+C para parar a qualquer momento.
    echo.
    python core\auto_trader.py
) else if "%MODO%"=="2" (
    echo.
    echo ============================================================
    echo   ATENCAO: MODO LIVE
    echo ============================================================
    echo.
    echo   Isso ativara operacoes com DINHEIRO REAL!
    echo.
    echo   Checklist obrigatorio:
    echo   [ ] Forward test completou 100+ trades
    echo   [ ] Win rate maior que 50%%
    echo   [ ] Max drawdown menor que 15%%
    echo   [ ] MT5 configurado e testado
    echo.
    set /p CONFIRM="Confirmar modo LIVE? (s/N): "
    if /i "!CONFIRM!"=="s" (
        python core\auto_trader.py --live
    ) else (
        echo Cancelado.
    )
) else if "%MODO%"=="3" (
    echo.
    echo ============================================================
    echo   STATUS DO FORWARD TEST
    echo ============================================================
    echo.
    if exist data\forward_test_log.json (
        python -c "import json; d=json.load(open('data/forward_test_log.json')); s=d.get('stats',{}); print(f'Trades: {s.get(\"total\",0)}'); print(f'Wins: {s.get(\"wins\",0)}'); print(f'Losses: {s.get(\"losses\",0)}'); print(f'Win Rate: {s.get(\"win_rate\",0):.1f}%%'); print(f'P&L: R$ {s.get(\"pnl\",0):.2f}')"
    ) else (
        echo Nenhum forward test encontrado.
        echo Execute o modo 1 primeiro para gerar dados.
    )
    echo.
    echo   Risk Manager:
    python -c "import json; d=json.load(open('data/risk_state.json')); print(f'Capital: R$ {d.get(\"current_capital\",0):.2f}'); print(f'Trades: {d.get(\"total_trades\",0)}'); print(f'Win Rate: {d.get(\"win_rate\",0):.1f}%%'); print(f'Status: {d.get(\"status\",\"?\")}')"
) else (
    echo Opcao invalida! Escolha 1, 2 ou 3.
)

echo.
pause

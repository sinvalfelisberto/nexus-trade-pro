@echo off
REM =============================================================
REM NEXUS TRADE PRO - Atualizacao diaria das cotacoes (historico B3)
REM =============================================================
REM Procura no banco (DB_OLD_* do .env) os pregoes que faltam ou estao
REM incompletos e importa dos arquivos oficiais da B3 (COTAHIST), e
REM atualiza os proventos de cada emissor consultado ha mais de 1 dia.
REM
REM Uso:  scripts\atualizar_cotacoes.bat [--verificar]
REM Agendar (Agendador de Tarefas), ex.: todo dia as 07:00:
REM   schtasks /create /tn "NexusAtualizarCotacoes" /sc daily /st 07:00 /tr "C:\caminho\do\projeto\scripts\atualizar_cotacoes.bat"
REM Log: logs\atualizar_cotacoes.log
REM =============================================================
setlocal
cd /d "%~dp0.."

set PYTHON=python
if exist "venv\Scripts\python.exe" set PYTHON=venv\Scripts\python.exe

set MODE=--atualizar
if "%~1"=="--verificar" set MODE=--verificar

if not exist logs mkdir logs
echo ===== %date% %time% (%MODE%) ===== >> logs\atualizar_cotacoes.log
%PYTHON% -u core\b3_history.py %MODE% >> logs\atualizar_cotacoes.log 2>&1
set RC=%errorlevel%
if "%MODE%"=="--atualizar" (
    %PYTHON% -u core\b3_proventos.py --atualizar --dias 1 >> logs\atualizar_cotacoes.log 2>&1
    if errorlevel 1 set RC=1
) else (
    %PYTHON% -u core\b3_proventos.py --status >> logs\atualizar_cotacoes.log 2>&1
)
echo ===== fim (codigo %RC%) ===== >> logs\atualizar_cotacoes.log
echo Atualizacao concluida (codigo %RC%). Log: logs\atualizar_cotacoes.log
exit /b %RC%

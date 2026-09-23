# MELHORIAS URGENTES - NEXUS TRADE PRO

## CRITICAS (Bloqueia funcionamento real)

### 1. DEPENDENCIAS DO SISTEMA
- **Status**: RESOLVIDO (2026-05-04)
- **Problema Original**: yfinance e pandas NAO estavam instaladas
- **Correcao**: incluidas no `requirements.txt` (`pip install -r requirements.txt`)

### 2. PASTA DESORGANIZADA
- **Status**: RESOLVIDO (2026-05-04)
- **Correcao**: Reorganizacao em subpastas (`core/`, `dashboard/`, `training/`, `scripts/`, `docs/`, `data/`)

### 3. FORWARD TEST NUNCA EXECUTADO
- **Status**: PENDENTE
- **Problema**: Sem validacao do sistema antes de operar com dinheiro real
- **Meta**: 100+ trades simulados com win rate > 50%
- **Acao**: `python3 core/auto_trader.py` (ou `scripts\iniciar_auto_trader.bat` opcao 1) - ver [GUIA_INICIO_RAPIDO.md](GUIA_INICIO_RAPIDO.md)

### 4. CONEXAO COM CORRETORA NAO CONFIGURADA
- **Status**: PENDENTE (para operacao REAL)
- **Problema**: Credenciais MT5 vazias no `.env`
- **Solucao**:
  1. Instalar MetaTrader 5 da corretora (Windows)
  2. Criar conta demo primeiro
  3. Preencher MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER no `.env`
  4. Testar com: `python3 training/test_broker_connection.py`

---

## ALTAS (Afeta performance)

### 5. LIMITES DA BRAPI.DEV (PLANO GRATUITO)
- **Status**: MITIGADO (2026-09-22)
- **Limites do plano gratuito**: 15.000 req/mes, 1 ativo por requisicao, 1 requisicao simultanea,
  historico de ate 3 meses, cotacoes com ~30 min de atraso. Sem token so funcionam PETR4, VALE3, ITUB4 e MGLU3.
- **Feito**:
  - Historico dos graficos vem da B3 (arquivos oficiais COTAHIST no MySQL) - 5 anos, sem limite - ver [HISTORICO_B3.md](HISTORICO_B3.md)
  - Requisicoes uma por vez (`BRAPI_MAX_CONCURRENT=1`), erros da brapi exibidos com a mensagem real
  - Token relido do `.env` sem reiniciar o servidor
- **Pendente**: o dashboard consulta ~30 ativos a cada 60 s (cache de 90 s no servidor). Isso da
  ~8 mil requisicoes por pregao e esgota a cota mensal em ~2 dias. Como o plano gratuito ja tem
  ~30 min de atraso, aumentar o cache das cotacoes (ex.: 15 min, configuravel no `.env`) nao perde informacao.

### 6. ATIVOS INEXISTENTES NA WATCHLIST
- **Status**: PENDENTE (2026-09-22)
- **Problema**: 15 dos 90 codigos do dashboard (e de listas no servidor, provedores e scripts de treino)
  nao existem mais na B3 nem na brapi/Yahoo - aparecem como SIM ou com erro.
- **Sucessores confirmados** (brapi + Yahoo): ELET3 → AXIA3, ELET6 → AXIA7, EMBR3 → EMBJ3, VIIA3 → BHIA3,
  SOMA3 → AZZA3, CPLE6 → CPLE3, PETZ3 → AUAU3, AZUL4 → AZUL3 (ELET6 e AZUL4 por deducao - confirmar)
- **Sem sucessor (remover)**: GOLL4, CRFB3, CIEL3, SULA11, BRIT3, NINJ3, IRDM11
- **Dica**: a consulta "Ativos que pararam de negociar" em [HISTORICO_B3.md](HISTORICO_B3.md) lista esses casos pelo banco.

### 7. LIMITE DE API TAVILY
- **Status**: ALTO
- **Problema**: 1.000 req/mes no plano gratuito (noticias)
- **Impacto**: Com a cota esgotada, o dashboard mostra noticias de exemplo (tag EXEMPLO)
- **Solucao**: Aguardar proximo mes ou upgrade

---

## MEDIAS (Melhorias de qualidade)

### 8. RESULTADOS DO TREINAMENTO NAO CHEGAM AO DASHBOARD
- **Status**: PENDENTE (encontrado em 2026-09-22)
- **Problema**: os scripts de `training/` gravam `training_results.json` na raiz do projeto, mas o
  endpoint `/api/training-results` le `core/training_results.json`.
- **Solucao**: unificar o caminho (ex.: `data/training_results.json`) nos scripts e no servidor.

### 9. BOTAO "VOLUME" DO GRAFICO SEM EFEITO
- **Status**: MEDIO
- **Problema**: o botao existe mas as barras de volume nao sao desenhadas; o volume aparece so no painel de valores.

### 10. ALERTAS WHATSAPP NAO IMPLEMENTADOS
- **Status**: MEDIO (`send_alert` e apenas um placeholder)

### 11. TRAILING STOP NAO ATIVO
- **Status**: MEDIO

### 12. SCRIPTS .BAT COM PORTA FIXA
- **Status**: BAIXO
- **Problema**: `treinar_bot.bat` e `turbo_train.bat` verificam o servidor em `localhost:8000`
  fixo; nao leem `SERVER_PORT` do `.env`.

---

## RESOLVIDO EM 2026-09-22

- Exibicao de cotacoes: precos em R$ no padrao brasileiro, grade nao mistura mais preco simulado com real,
  analise mostra erro em vez de R$ 0,00, cache de cotacoes nao serve mais dados de dias anteriores
- Grafico de candles em branco (versoes incompativeis do Chart.js e do plugin financeiro)
- Sincronizacao com o auto trader (campos com nomes errados quebravam portfolio e historico)
- Configuracao centralizada no `.env` (`core/env_config.py`), com prioridade sobre variaveis do sistema
- Historico oficial da B3 no MySQL + script de atualizacao diaria que preenche lacunas
- Proventos da B3 (dividendos, JCP, rendimentos, eventos em acoes) no MySQL, atualizados diariamente

---

## PROXIMOS PASSOS (Ordem de Prioridade)

1. **HOJE**: Iniciar o forward test
   ```
   1. python3 core/server_fastmcp.py http   (servidor + dashboard em http://localhost:8000/dashboard)
   2. python3 core/auto_trader.py           (ou scripts\iniciar_auto_trader.bat, opcao 1)
   ```

2. **SEMANA 1**: Acumular 50+ trades no forward test; corrigir a watchlist (item 6) e o cache da brapi (item 5)

3. **SEMANA 2**: Analisar resultados, ajustar se necessario

4. **SEMANA 3**: Configurar MT5 com conta DEMO

5. **SEMANA 4**: Se win rate > 50%, iniciar com R$500 reais

---

## Checklist Pre-Operacao Real

- [ ] Forward test completou 100+ trades
- [ ] Win rate > 50%
- [ ] Max drawdown < 15%
- [ ] Profit factor > 1.3
- [ ] MT5 configurado e testado
- [ ] Conta demo validada por 1 semana
- [ ] Capital inicial: apenas R$500-1000

---

*Ultima atualizacao: 2026-09-22*

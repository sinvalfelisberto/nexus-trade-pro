# NEXUS TRADE PRO v3.5 — AI Learning Trading Bot

## Novidades da v3.5

### Novos Modulos Implementados
- **Data Providers**: Yahoo Finance (gratuito, sem limites) + brapi.dev + Fallback
- **Multi-Timeframe Analysis**: Analise em 1H, 4H e Diario combinados
- **Advanced Filters**: Filtros de Liquidez, Regime, Horario, Momentum
- **Ensemble Model**: Votacao ponderada de 5 modelos (GA, SA, PSO, Trend, Reversion)
- **Risk Manager**: Controle de drawdown, position sizing dinamico, circuit breaker

### Sistema de Aprendizado de Maquina
- **Analise automatica de trades**: O bot aprende com cada operacao
- **Ajuste de pesos**: A IA otimiza os pesos dos indicadores baseado em performance
- **Deteccao de padroes**: Identifica horarios e condicoes mais lucrativas
- **Historico de aprendizado**: Rastreia evolucao da acuracia ao longo do tempo

### Dashboard Profissional
- **Design moderno**: Interface inspirada em plataformas profissionais
- **Cores e tipografia**: Paleta escura com acentos vibrantes (roxo/azul)
- **Nova aba APRENDIZADO**: Visualize metricas de IA e padroes detectados
- **Metricas avancadas**: Win Rate, Profit Factor, Max Drawdown, Confianca do Modelo

### Saldo Inicial
- **R$ 500,00** de saldo simulado inicial (alterado de R$ 10.000)
- Botao para resetar portfolio a qualquer momento

---

## QUEM E A USUARIA

**Elida**, Indaiatuba/SP. Construindo uma plataforma de trading automatizado focada no mercado brasileiro (B3) com bot de analise tecnica, integracao com APIs reais e sistema de aprendizado de maquina.

---

## Como Iniciar

Passo a passo completo (venv, `.env`, historico da B3, verificacao): [README](../README.md#getting-started-step-by-step).

### 1. Iniciar o Servidor
```bash
# na raiz do projeto, com o venv ativo
python3 core/server_fastmcp.py http
```
O servidor inicia na porta `SERVER_PORT` do `.env` (padrao 8000). Sem o argumento `http` ele sobe
em modo MCP (stdio) e o dashboard fica "offline".

### 2. Abrir a Dashboard
Acesse <http://localhost:8000/dashboard> (o proprio servidor entrega a pagina).

### 3. Ativar o Bot
1. Va para aba **BOT PRO**
2. Configure a estrategia (recomendado: **IA ADAPTATIVA**)
3. Ajuste parametros conforme seu perfil
4. Clique no toggle para LIGAR o bot

---

## Estrategias Disponiveis

| Estrategia | Descricao |
|------------|-----------|
| **IA ADAPTATIVA** | Usa pesos otimizados automaticamente pela IA (RECOMENDADO) |
| COMPOSTA | Combina todos os indicadores com pesos manuais |
| RSI | Foca em sobrecompra/sobrevenda |
| MACD | Segue cruzamentos do MACD |
| EMA 9/21 | Cruzamento de medias moveis |

---

## Sistema de Aprendizado v2.0

### Como Funciona
1. **Coleta Massiva**: Analisa historico de 30+ ativos com multiplos cenarios
2. **Gradient Descent**: Otimiza pesos usando algoritmo de Machine Learning
3. **Ensemble**: Combina 5 estrategias diferentes (Trend, Reversal, Momentum, etc)
4. **Walk-Forward**: Valida em janelas temporais para evitar overfitting
5. **Regime Detection**: Detecta automaticamente Bull/Bear/Neutro
6. **Early Stopping**: Para treinamento quando metricas param de melhorar

### Metricas Avancadas Rastreadas
- **Win Rate** por indicador (RSI, MACD, BB, ADX, Stochastic, Volume)
- **Sharpe Ratio**: Retorno ajustado ao risco (meta: > 1.0)
- **Profit Factor**: Lucros / Perdas (meta: > 1.2)
- **Max Drawdown**: Maior perda consecutiva (meta: < 15%)
- **Performance por Regime**: Bull (melhor), Bear, Neutro (pior)

### Pesos Otimizados TURBO (v3.0)
| Indicador | Peso | Win Rate | Status |
|-----------|------|----------|--------|
| **STOCH** | **2.66** | **66.3%** | DOMINANTE |
| **ADX** | **2.45** | **60.6%** | MUITO ALTO |
| **VOLUME** | **2.05** | **60.1%** | ALTO |
| MACD | 1.19 | 60.1% | MANTIDO |
| NEWS | 1.07 | - | MODERADO |
| BB | 0.09 | 0% | ELIMINADO |
| RSI | 0.06 | 0% | ELIMINADO |

**Descoberta principal**: Stochastic e ADX sao os indicadores que funcionam. RSI e Bollinger Bands foram ELIMINADOS por baixa performance.

### Executar Treinamento Avancado
1. Certifique-se que o servidor esta rodando: `python3 core/server_fastmcp.py http`
2. Execute: `scripts\treinar_bot.bat` (Windows) ou `python3 training/train_bot_advanced.py`
3. Aguarde o treinamento (3-5 minutos)
4. Reinicie o servidor para aplicar novos pesos

### Aplicar Pesos da IA
1. Va para aba **BOT PRO**
2. Clique em **APLICAR PESOS IA**
3. Os sliders serao ajustados automaticamente

### Aba APRENDIZADO
- **Ciclos de Aprendizado**: Quantas vezes a IA otimizou os pesos
- **Taxa de Acerto**: Win rate geral baseado em trades fechados
- **Confianca do Modelo**: Baixa (<20 trades), Media (20-50), Alta (>50)
- **Performance por Indicador**: Grafico de barras mostrando eficacia
- **Padroes Detectados**: Lista de insights descobertos pela IA

---

## Indicadores Tecnicos

### Basicos
- **RSI (14)**: Sobrecomprado (>70) / Sobrevendido (<30)
- **MACD**: Linha + Sinal + Histograma
- **Bollinger Bands**: Superior / Medio / Inferior
- **EMA 9/21**: Cruzamento de tendencias

### Avancados
- **ADX**: Forca da tendencia (>25 = tendencia forte)
- **Stochastic**: Momentum de curto prazo
- **ATR**: Volatilidade para position sizing
- **VWAP**: Preco ponderado por volume
- **OBV**: Volume on-balance (pressao compradora/vendedora)

---

## Parametros Recomendados

> Stop Loss, Take Profit e Max por ordem vem do `.env` (`STOP_LOSS_PERCENT`, `TAKE_PROFIT_PERCENT`,
> `MAX_ORDER_VALUE`) e ficam bloqueados na aba BOT PRO (marca `.env`). Para usar um dos perfis
> abaixo, altere esses valores no `.env` e reinicie o servidor. O padrao atual do `.env.example`
> e 4% / 8% / R$ 300, com 3 posicoes simultaneas (`MAX_POSITIONS`).

### Perfil Conservador
- Confianca minima: 70%
- Stop Loss: 2%
- Take Profit: 4%
- Max por ordem: R$ 50

### Perfil Moderado (Padrao)
- Confianca minima: 55%
- Stop Loss: 3%
- Take Profit: 6%
- Max por ordem: R$ 100

### Perfil Agressivo
- Confianca minima: 40%
- Stop Loss: 5%
- Take Profit: 10%
- Max por ordem: R$ 200

---

## APIs e Fontes de Dados

| Fonte | Funcao | Limite (plano gratuito) |
|-----|--------|--------|
| brapi.dev | Cotacoes atuais | 15.000 req/mes, 1 ativo e 1 requisicao por vez, historico de 3 meses, ~30 min de atraso |
| B3 - Series Historicas (COTAHIST) | Historico diario oficial dos graficos (MySQL) | Sem limite, sem token - ver [HISTORICO_B3.md](HISTORICO_B3.md) |
| Yahoo Finance | Provedor alternativo dos modulos de analise | Nao oficial, sem token |
| Tavily AI | Noticias e sentimento | 1.000 req/mes |

Sem token, a brapi so libera PETR4, VALE3, ITUB4 e MGLU3 - teste o token com outro ativo (ex.: PETR3).

### Sistema de Fallback
Quando a brapi nao retorna a cotacao de um ativo (token invalido, cota esgotada, ativo inexistente),
**so esse ativo** usa dados simulados; os demais continuam com dados reais:
- Sao baseados em precos de referencia fixos
- Tem variacao aleatoria de +/- 1% por ciclo
- Mostram tag **SIM** em amarelo (vs **LIVE** verde para dados reais)

### Como Renovar Token brapi.dev
1. Acesse: https://brapi.dev/dashboard
2. Clique em "Regenerar Token"
3. Atualize o `BRAPI_TOKEN` no `.env` - o servidor rele o token sozinho, sem reiniciar

### Configuracao (arquivo .env)
Todas as configuracoes vem do `.env` (modelo comentado em `.env.example`), que tem prioridade sobre
variaveis do sistema. Principais chaves:
```env
BRAPI_TOKEN=seu_token_brapi
TAVILY_KEY=sua_chave_tavily
DB_OLD_HOST=...            # MySQL do historico da B3 (opcional)
SERVER_PORT=8000
INITIAL_CAPITAL=500
```

### Fallback de Noticias
Quando a API Tavily esta offline, o sistema mostra **noticias de exemplo** para demonstracao:
- Tag **[SIMULADO]** aparece no card de sentimento
- Tag **[EXEMPLO]** aparece em cada noticia
- Permite testar a interface mesmo sem API

---

## Estrutura de Arquivos

```
nexus-trade-pro/
├── core/                    # servidor, config (.env), historico B3, analise, risco, auto trader
├── dashboard/nexus_trade_pro.html
├── training/                # treinamentos e teste de conexao com a corretora
├── scripts/                 # atalhos .bat e atualizar_cotacoes.sh/.bat
├── sql/bolsa_schema.sql     # tabelas do historico da B3
├── docs/                    # este arquivo, guias e pendencias
├── data/                    # estado em tempo de execucao (nao versionado)
├── .env.example             # modelo de configuracao
└── requirements.txt
```

Detalhes de cada arquivo: secao *Project Structure* do [README](../README.md#project-structure).

---

## Dados Armazenados (localStorage)

| Chave | Conteudo |
|-------|----------|
| `ntp_portfolio_v3` | Saldo (R$500), posicoes, trades |
| `ntp_learning` | Dados de aprendizado da IA |
| `ntp_botConfig` | Configuracoes do bot (stop, alvo e max por ordem sempre vem do `.env`) |
| `ntp_favorites` | Ativos favoritos (estrela nos cards; aparecem primeiro no grafico) |

---

## Ativos Monitorados (90 ativos)

> **Atencao:** 15 codigos desta lista nao existem mais na B3 (fusoes, troca de codigo ou saida da
> bolsa) - ver item 6 de [MELHORIAS_URGENTES.md](MELHORIAS_URGENTES.md). Qualquer outro ativo pode
> ser buscado pelo campo de busca da aba MERCADO.

### Blue Chips (10)
PETR4, VALE3, ITUB4, BBDC4, BBAS3, WEGE3, ABEV3, B3SA3, RENT3, SUZB3

### Energia & Commodities (10)
PETR3, PRIO3, ELET3, ELET6, GGBR4, CSNA3, USIM5, CMIN3, CMIG4, CPLE6

### Consumo & Varejo (10)
MGLU3, LREN3, PETZ3, AMER3, VIIA3, CRFB3, PCAR3, ASAI3, GMAT3, SOMA3

### Financeiro (10)
ITSA4, SANB11, BPAC11, CIEL3, BBSE3, IRBR3, SULA11, PSSA3, BRSR6, BMGB4

### Saude (10)
HAPV3, RDOR3, FLRY3, QUAL3, HYPE3, RADL3, DASA3, MATD3, AALR3, ONCO3

### Tecnologia & Telecom (10)
TOTS3, LWSA3, CASH3, MELI34, INTB3, VIVT3, TIMS3, OIBR3, BRIT3, NINJ3

### Industria & Aviacao (10)
EMBR3, AZUL4, GOLL4, CVCB3, RAIZ4, SMTO3, SLCE3, AGRO3, CAML3, TTEN3

### ETFs (10)
BOVA11, IVVB11, SMAL11, DIVO11, HASH11, QBTC11, ETHE11, GOLD11, XFIX11, TECK11

### FIIs (10)
HGLG11, MXRF11, KNCR11, XPML11, VISC11, BTLG11, VGIR11, RECR11, CPTS11, IRDM11

---

## Troubleshooting

### Servidor nao inicia
```bash
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Cotacoes nao carregam ou aparecem como SIM
- Verifique se o servidor esta rodando (`python3 core/server_fastmcp.py http`)
- Teste o token: <http://localhost:8000/api/quote/PETR3> deve trazer um preco
- Mais casos: secao *Troubleshooting* do [README](../README.md#troubleshooting)

### Grafico sem historico longo
- Sem o historico da B3 no MySQL, os graficos usam a brapi (3 meses no plano gratuito)
- Carregue com `python3 core/b3_history.py --carga` - ver [HISTORICO_B3.md](HISTORICO_B3.md)

### Bot nao opera
- Verifique se ha saldo disponivel (minimo R$ 50)
- Confira se o servidor esta ONLINE (indicador verde no header)

### Resetar tudo
- Portfolio: Aba Portfolio > RESETAR PORTFOLIO
- Aprendizado: Aba Aprendizado > RESETAR APRENDIZADO

---

---

## Risk Manager v1.0 (NOVO!)

### O que e
Sistema de gerenciamento de risco que **protege seu capital** contra perdas excessivas.

### Recursos
| Recurso | Descricao | Configuracao Padrao |
|---------|-----------|---------------------|
| **Controle de Drawdown** | Para de operar se perder X% do pico | 20% |
| **Limite Diario** | Maximo de perda por dia | 5% |
| **Perdas Consecutivas** | Reduz posicao apos sequencia de perdas | Apos 2 perdas |
| **Circuit Breaker** | Pausa total apos perda extrema | 8% de loss |
| **Position Sizing Dinamico** | Ajusta tamanho baseado no risco | Kelly Criterion |
| **Filtro de Confianca** | So opera se sinal for forte | Min 55% |

### Como Funciona

1. **Antes de cada trade**: O sistema verifica se pode operar
2. **Calcula risco**: Ajusta quantidade baseado no estado atual
3. **Bloqueia se necessario**: Para operacoes quando limites sao atingidos
4. **Registra resultados**: Atualiza estatisticas apos cada trade

### Endpoints da API

```bash
# Status completo do Risk Manager
GET /api/risk/status

# Verificar se pode operar
GET /api/risk/can-trade?confidence=70&score=40

# Calcular tamanho de posicao
GET /api/risk/position-size/PETR4?stop_loss_percent=3.0

# Verificar trade especifico
GET /api/risk/check-trade/PETR4?quantity=100

# Registrar trade fechado
POST /api/risk/close-trade?ticker=PETR4&action=BUY&quantity=100&entry_price=38.50&exit_price=40.00

# Resetar Risk Manager
POST /api/risk/reset?initial_capital=500

# Desbloquear (emergencia)
POST /api/risk/unblock
```

### Multiplicador de Posicao

O sistema reduz automaticamente o tamanho das posicoes:

| Situacao | Multiplicador |
|----------|---------------|
| Normal | 1.00 (100%) |
| Apos 2 perdas | 0.75 (75%) |
| Apos 3 perdas | 0.50 (50%) |
| Apos 4+ perdas | 0.25 (25%) |
| Drawdown > 10% | -30% a -50% |
| 3+ ganhos seguidos | +5% a +25% |

### Exemplo de Uso

```python
from risk_manager import risk_manager

# Verificar se pode operar
can, reason, details = risk_manager.check_can_trade(
    order_value=1000,
    confidence=70,
    score=45,
    volatility_atr_percent=2.5
)

if can:
    # Calcular tamanho ideal
    size = risk_manager.calculate_position_size(
        price=38.50,
        stop_loss_percent=3.0
    )
    print(f"Comprar {size['recommended']['quantity']} acoes")
else:
    print(f"Bloqueado: {reason}")
```

---

## Changelog

### v3.6 (22/09/2026)
- **Historico oficial da B3** (arquivos COTAHIST) em MySQL: 5 anos, ~1,45 mi de linhas, tabelas `bolsa_*`
  - `core/b3_history.py` (carga, atualizacao, verificacao) - reutilizavel em outros projetos
  - `scripts/atualizar_cotacoes.sh/.bat`: procura e preenche pregoes faltando ou incompletos, registra feriados
  - Servidor atualiza sozinho ao subir e a cada `B3_UPDATE_HOURS` horas
- **Graficos**: candles corrigidos (Chart.js 4 + plugin financeiro 0.2), velas diarias/semanais/mensais/anuais,
  painel de valores e tooltips em R$, selecao do ativo por lista com favoritos primeiro, fonte dos dados exibida
- **Aba MERCADO**: favoritos (estrela), campo de busca por ticker/setor, busca de ativos fora da lista,
  grade so usa simulado para o ativo sem cotacao real
- **Configuracao centralizada no `.env`** (`core/env_config.py`): prioridade sobre o sistema, token relido
  sem reiniciar, porta/host configuraveis, endpoint `/api/config` para o dashboard
- **Correcoes**: formato de moeda pt-BR, cache que servia cotacao de dias anteriores, sincronizacao com o
  auto trader, analise exibindo R$ 0,00 em erro, requisicoes simultaneas recusadas pela brapi

### v3.4 (30/04/2026)
- **RISK MANAGER v1.0** - Sistema completo de controle de risco
  - Controle de drawdown maximo (20%)
  - Limite de perda diaria (5%)
  - Reducao automatica apos perdas consecutivas
  - Circuit breaker para perdas extremas
  - Position sizing dinamico (Kelly Criterion)
  - Filtro de confianca e score minimo
  - 8 novos endpoints de API
- Servidor atualizado para v3.1
- Integracao automatica com endpoints de trading

### v3.3 TURBO (30/04/2026)
- **Sistema TURBO TRAINING v3.0** - Aprendizado ULTRA-ACELERADO
  - Genetic Algorithm (exploracao global de solucoes)
  - Simulated Annealing (refinamento e escape de minimos locais)
  - Particle Swarm Optimization (exploracao paralela)
  - Multi-Objetivo: Win Rate (45%) + Profit Factor (35%) + Sharpe (20%)
- **RESULTADOS EXTRAORDINARIOS** (1848 trades):
  - Win Rate: **60.1%** (era 44.8% - melhoria de +15.3%)
  - Profit Factor: **2.28** (era 1.35 - melhoria de +69%)
  - Sharpe Ratio: **5.18** (era 1.42 - melhoria de +265%)
- **Novos pesos TURBO otimizados**:
  - STOCH: **2.66** (DOMINANTE - 66.3% win rate!)
  - ADX: **2.45** (MUITO ALTO - 60.6% win rate)
  - VOLUME: **2.05** (ALTO - 60.1% win rate)
  - MACD: 1.19 (mantido)
  - NEWS: 1.07 (moderado)
  - BB: **0.09** (ELIMINADO)
  - RSI: **0.06** (ELIMINADO - pior indicador)
- **Descoberta principal**: STOCH e o melhor indicador, RSI e BB nao funcionam
- Novo arquivo `train_turbo_sim.py` com treinamento TURBO
- Novo arquivo `turbo_train.bat` para execucao facil

### v3.1 (26/04/2026)
- **70+ ativos monitorados** (era 20)
- **Sistema de fallback para cotacoes** com dados simulados quando API offline
- **Sistema de fallback para noticias** com exemplos quando Tavily offline
- Dados organizados por setor (Blue Chips, Energia, Varejo, etc)
- Variacao realista nos dados simulados (+/- 1% por ciclo)
- Tags visuais: [LIVE] verde = real, [SIM] amarelo = simulado, [EXEMPLO] = noticias demo
- Noticias de exemplo para PETR4, VALE3, IBOV e queries gerais

### v3.0
- Sistema de aprendizado de maquina
- Nova aba de Aprendizado
- Dashboard profissional redesenhado
- Saldo inicial R$ 500
- Estrategia IA ADAPTATIVA
- Deteccao automatica de padroes

### v2.0
- Indicadores avancados (ADX, Stochastic, ATR, VWAP, OBV)
- Trailing Stop
- Analise de sentimento
- Position sizing

### v1.0
- Dashboard inicial
- Indicadores basicos
- Bot simples

---

*Sistema: Nexus Trade Pro v3.6*
*Desenvolvido com: FastMCP + brapi.dev + B3 (COTAHIST) + Tavily AI + Machine Learning*

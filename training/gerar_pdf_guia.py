# -*- coding: utf-8 -*-
from fpdf import FPDF
from datetime import datetime

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)

# Pagina 1 - Capa
pdf.add_page()
pdf.set_font('Helvetica', 'B', 28)
pdf.set_text_color(0, 100, 200)
pdf.ln(50)
pdf.cell(0, 15, 'NEXUS TRADE PRO', align='C', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', 'B', 18)
pdf.set_text_color(50, 50, 50)
pdf.cell(0, 10, 'Guia de Operacoes Reais', align='C', new_x='LMARGIN', new_y='NEXT')
pdf.ln(10)
pdf.set_font('Helvetica', '', 12)
pdf.set_text_color(100, 100, 100)
pdf.cell(0, 8, 'Passo a passo para operar com dinheiro real na B3', align='C', new_x='LMARGIN', new_y='NEXT')
pdf.ln(30)
pdf.set_font('Helvetica', 'I', 10)
pdf.cell(0, 8, f'Versao 2.0 - {datetime.now().strftime("%d/%m/%Y")}', align='C', new_x='LMARGIN', new_y='NEXT')

# Pagina 2 - Aviso
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(200, 0, 0)
pdf.cell(0, 10, '1. AVISO IMPORTANTE', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Helvetica', '', 11)
pdf.set_text_color(0, 0, 0)
pdf.multi_cell(0, 6, """
ATENCAO: Investir em renda variavel envolve riscos significativos. Voce pode perder parte ou todo o capital investido. Este sistema e uma ferramenta de apoio a decisao, NAO uma recomendacao de investimento.

Antes de operar com dinheiro real:
- Entenda completamente os riscos envolvidos
- Tenha reserva de emergencia (6-12 meses de despesas)
- Invista apenas o que pode perder
- Estude analise tecnica e fundamentalista
- Comece com valores pequenos
""")

# Pagina 3 - Status do Sistema
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(0, 100, 200)
pdf.cell(0, 10, '2. STATUS ATUAL DO SISTEMA', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Helvetica', '', 11)
pdf.set_text_color(0, 0, 0)
pdf.multi_cell(0, 6, """
O Nexus Trade Pro possui:

* Cotacoes em tempo real via brapi.dev
* Indicadores: RSI, MACD, Bollinger, ADX, Stochastic, ATR, VWAP, OBV
* Sistema de score com sinais COMPRA/VENDA/NEUTRO
* Noticias em tempo real via Google News
* Analise de sentimento de mercado
* Position sizing e trailing stop
* Scanner de mercado multi-ativos

MODO ATUAL: SIMULACAO
O sistema ainda NAO executa ordens reais. Para operar com dinheiro real, e necessario integrar com uma corretora.
""")

# Pagina 4 - Requisitos
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(0, 100, 200)
pdf.cell(0, 10, '3. REQUISITOS PARA OPERAR', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Helvetica', 'B', 12)
pdf.set_text_color(0, 0, 0)
pdf.cell(0, 8, '3.1 Documentacao Pessoal:', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', '', 11)
pdf.multi_cell(0, 6, """
- CPF regularizado na Receita Federal
- RG ou CNH
- Comprovante de residencia (ultimos 3 meses)
- Conta bancaria em seu nome
""")

pdf.set_font('Helvetica', 'B', 12)
pdf.cell(0, 8, '3.2 Conta em Corretora com API:', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', '', 11)
pdf.multi_cell(0, 6, """
Corretoras recomendadas:
- BTG Pactual Digital (API robusta, corretagem zero)
- XP Investimentos (maior corretora do Brasil)
- Clear Corretora (taxa zero, API via XP)
- Modal Mais (API propria)
- MetaTrader 5 (compativel com varias corretoras)
""")

# Pagina 5 - Abrindo Conta
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(0, 100, 200)
pdf.cell(0, 10, '4. PASSO A PASSO: ABRINDO CONTA', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Helvetica', 'B', 12)
pdf.set_text_color(0, 0, 0)
pdf.cell(0, 8, 'Recomendado: BTG Pactual Digital', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', '', 11)
pdf.multi_cell(0, 6, """
Passo 1: Acesse https://www.btgpactualdigital.com

Passo 2: Clique em "Abrir Conta" e preencha:
   - Nome completo
   - CPF
   - Data de nascimento
   - Email e telefone

Passo 3: Envie documentos:
   - Foto do documento (frente e verso)
   - Selfie com documento
   - Comprovante de residencia

Passo 4: Aguarde aprovacao (1-3 dias uteis)

Passo 5: Transfira dinheiro via TED/PIX
""")

# Pagina 6 - Configurando API
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(0, 100, 200)
pdf.cell(0, 10, '5. CONFIGURANDO A API', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Helvetica', 'B', 12)
pdf.set_text_color(0, 0, 0)
pdf.cell(0, 8, '5.1 Obtendo Credenciais (BTG):', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', '', 11)
pdf.multi_cell(0, 6, """
1. Acesse sua conta no BTG
2. Va em Configuracoes > API de Integracao
3. Clique em "Gerar Nova Chave de API"
4. Copie o Client ID e Client Secret
5. GUARDE EM LOCAL SEGURO!
""")

pdf.set_font('Helvetica', 'B', 12)
pdf.cell(0, 8, '5.2 Configurando no .env:', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Courier', '', 10)
pdf.set_fill_color(240, 240, 240)
pdf.multi_cell(0, 5, """
# Credenciais da Corretora
BROKER_NAME=BTG
BROKER_CLIENT_ID=seu_client_id
BROKER_CLIENT_SECRET=seu_secret
BROKER_ACCOUNT=sua_conta

# Modo de operacao
TRADING_MODE=REAL
MAX_ORDER_VALUE=1000
DAILY_LOSS_LIMIT=500
""", fill=True)

# Pagina 7 - Seguranca
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(200, 0, 0)
pdf.cell(0, 10, '6. SEGURANCA E RISCO', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Helvetica', '', 11)
pdf.set_text_color(0, 0, 0)
pdf.multi_cell(0, 6, """
REGRAS OBRIGATORIAS:

1. Limite de perda diaria: Defina valor maximo de perda/dia
2. Limite por operacao: Nunca arrisque mais de 2% do capital
3. Stop Loss: SEMPRE defina antes de entrar
4. Take Profit: Defina alvos realistas
5. Horario: Opere apenas das 10h as 17h
6. Liquidez: Evite ativos com baixo volume

CONFIGURACOES DE RISCO NO .env:
""")
pdf.set_font('Courier', '', 10)
pdf.multi_cell(0, 5, """
RISK_PER_TRADE=2.0
DAILY_LOSS_LIMIT=5.0
MAX_POSITIONS=5
MIN_SCORE_BUY=60
MIN_SCORE_SELL=-60
STOP_LOSS_PERCENT=3.0
TAKE_PROFIT_PERCENT=6.0
""", fill=True)

# Pagina 8 - Ativando Modo Real
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(0, 100, 200)
pdf.cell(0, 10, '7. ATIVANDO MODO REAL', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Helvetica', '', 11)
pdf.set_text_color(0, 0, 0)
pdf.multi_cell(0, 6, """
PASSO 1: Verificar configuracoes
- Credenciais da corretora corretas
- Saldo disponivel na corretora
- Limites de risco configurados

PASSO 2: Testar conexao
Execute: python test_broker_connection.py

PASSO 3: Operacoes manuais primeiro
Faca pelo menos 5 operacoes manuais usando os sinais do sistema.

PASSO 4: Ativar bot em modo real
- No dashboard, clique em "MODO REAL"
- Digite "CONFIRMO" para ativar
- O indicador mudara de SIMULADO para REAL
- O bot comecara a executar ordens reais

MONITORE CONSTANTEMENTE!
""")

# Pagina 9 - Checklist
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(0, 100, 200)
pdf.cell(0, 10, '8. CHECKLIST ANTES DE OPERAR', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Helvetica', '', 11)
pdf.set_text_color(0, 0, 0)
pdf.multi_cell(0, 7, """
[ ] Conta na corretora aberta e aprovada
[ ] Saldo transferido para a corretora
[ ] Credenciais de API configuradas no .env
[ ] Teste de conexao com corretora OK
[ ] Limites de risco configurados
[ ] Stop loss padrao definido
[ ] Entendo que posso perder dinheiro
[ ] NAO estou usando dinheiro de emergencia
[ ] Fiz pelo menos 10 operacoes simuladas
[ ] Li toda a documentacao
[ ] Tenho tempo para monitorar
[ ] Conheco horarios de pregao da B3

Se NAO marcou TODOS os itens, continue em simulacao!
""")

# Pagina 10 - Corretoras
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(0, 100, 200)
pdf.cell(0, 10, '9. APIS POR CORRETORA', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Helvetica', 'B', 11)
pdf.set_text_color(0, 0, 0)
pdf.cell(0, 7, 'BTG PACTUAL DIGITAL', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', '', 10)
pdf.multi_cell(0, 5, "Site: btgpactualdigital.com | Taxa: Zero | API: Robusta")
pdf.ln(3)

pdf.set_font('Helvetica', 'B', 11)
pdf.cell(0, 7, 'XP INVESTIMENTOS', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', '', 10)
pdf.multi_cell(0, 5, "Site: xpi.com.br | Taxa: Variavel | API: Via XP Pro")
pdf.ln(3)

pdf.set_font('Helvetica', 'B', 11)
pdf.cell(0, 7, 'CLEAR CORRETORA', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', '', 10)
pdf.multi_cell(0, 5, "Site: clear.com.br | Taxa: Zero | API: Via XP")
pdf.ln(3)

pdf.set_font('Helvetica', 'B', 11)
pdf.cell(0, 7, 'METATRADER 5 (RECOMENDADO)', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', '', 10)
pdf.multi_cell(0, 5, """
Site: metatrader5.com
API: Python nativo (pip install MetaTrader5)
Corretoras: Rico, Modal, XP
Vantagem: API bem documentada, facil integracao
""")

# Pagina 11 - Arquivos
pdf.add_page()
pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(0, 100, 200)
pdf.cell(0, 10, '10. ARQUIVOS DO SISTEMA', new_x='LMARGIN', new_y='NEXT')
pdf.ln(5)
pdf.set_font('Courier', '', 10)
pdf.set_text_color(0, 0, 0)
pdf.multi_cell(0, 5, """
nexustrade/
  |-- NexusTradePro.bat      # Launcher (duplo clique)
  |-- server_fastmcp.py      # Servidor principal
  |-- nexus_trade_pro.html   # Dashboard
  |-- .env                   # Configuracoes (EDITAR!)
  |-- requirements.txt       # Dependencias
  |-- broker_integration.py  # Integracao corretoras
  |-- GUIA_OPERACOES_REAIS.pdf  # Este guia
""")

pdf.ln(10)
pdf.set_font('Helvetica', 'B', 12)
pdf.set_text_color(0, 150, 0)
pdf.multi_cell(0, 7, """
PROXIMAS IMPLEMENTACOES:
- Integracao completa com BTG e MetaTrader 5
- Alertas via WhatsApp
- Backtesting de estrategias
- Machine Learning
""")

pdf.ln(10)
pdf.set_font('Helvetica', 'B', 14)
pdf.set_text_color(0, 100, 200)
pdf.cell(0, 10, 'Boas operacoes! Gerenciamento de risco e fundamental.', align='C')

# Salvar
pdf.output('C:/Users/elida/Desktop/nexustrade/GUIA_OPERACOES_REAIS.pdf')
print("PDF gerado: GUIA_OPERACOES_REAIS.pdf")

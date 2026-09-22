# NEXUS TRADE PRO - Guia de Inicio Rapido

Roteiro para sair do zero ate operar com saldo real, com seguranca: **forward test → conta demo → saldo real**.

> **Instalacao e execucao do projeto** (venv, `.env`, servidor, dashboard, historico da B3):
> siga o passo a passo do [README](../README.md#getting-started-step-by-step). Este guia comeca
> depois disso, com o servidor rodando e o dashboard aberto em <http://localhost:8000/dashboard>.

Todos os comandos abaixo sao executados **na raiz do projeto**, com o ambiente virtual ativo
(`source venv/bin/activate` no Linux/macOS, `venv\Scripts\activate` no Windows).

---

## Contexto

O bot chegou a ter backtest com 60% de win rate, mas **nenhum trade real ou simulado registrado**
(`data/risk_state.json` com 0 trades). Por isso foram criados o auto trader com forward test e o
treinamento conservador, e o `.env` passou a usar parametros **mais conservadores**:

```
RISK_PER_TRADE=1.0       (era 2.0%)
STOP_LOSS_PERCENT=4.0    (era 3.0%)
TAKE_PROFIT_PERCENT=8.0  (ratio 1:2)
MAX_ORDER_VALUE=300      (era R$ 1000)
MAX_POSITIONS=3          (era 5)
```

Esses valores vem sempre do `.env`: o servidor, o auto trader e o dashboard (campos marcados com
`.env` na aba BOT PRO) leem de la. Para mudar, edite o `.env` e reinicie o servidor.

### Arquivos envolvidos

| Arquivo | Funcao |
|---------|--------|
| `core/auto_trader.py` | Trading automatico com ciclos de scan/trade (forward test ou live) |
| `training/train_conservative.py` | Treinamento com walk-forward validation (anti-overfitting) |
| `training/test_broker_connection.py` | Teste da conexao com o MetaTrader 5 |
| `scripts/iniciar_auto_trader.bat` | Atalho Windows para o auto trader (menu com as 3 opcoes) |
| `scripts/treinar_conservador.bat` | Atalho Windows para o treinamento conservador |

---

## Passo a Passo

### 1. Retreinar com o modelo conservador

```bash
python3 training/train_conservative.py      # Linux/macOS
scripts\treinar_conservador.bat             # Windows
```

Isso usa:
- Walk-forward validation (70% treino, 15% validacao, 15% teste)
- Penalizacao de overfitting
- Modelo simplificado (4 indicadores: Stoch, ADX, MACD, Volume)

Gera `training_results.json` e `trained_weights.js` na raiz do projeto.

### 2. Iniciar o forward test (semanas 1-2)

```bash
python3 core/auto_trader.py                 # Linux/macOS
scripts\iniciar_auto_trader.bat             # Windows -> opcao 1 (Forward Test)
```

O bot vai:
- Escanear o mercado a cada 60 segundos (15 ativos mais liquidos, horario 10:00-16:30 exceto almoco)
- Gerar sinais de compra/venda
- Registrar trades **simulados** em `data/forward_test_log.json`
- Atualizar `data/risk_state.json` com as estatisticas

Os trades aparecem no dashboard (aba HISTORICO/PORTFOLIO), que sincroniza com o auto trader a cada 10 s.

**Meta**: acumular 100+ trades simulados e validar win rate > 50%. Pare com `Ctrl+C`.

### 3. Analisar os resultados

```bash
python3 -c "import json; print(json.load(open('data/forward_test_log.json'))['stats'])"
```

No Windows, `scripts\iniciar_auto_trader.bat` opcao **3** mostra o mesmo resumo.

Criterios para ir para o saldo real:
- [ ] 100+ trades
- [ ] Win rate > 50%
- [ ] Max drawdown < 15%
- [ ] Profit factor > 1.3

### 4. Configurar a corretora (semana 3)

1. Instale o MetaTrader 5 da sua corretora (Clear, Rico, Modal etc.) - o pacote `MetaTrader5` do Python so existe para Windows
2. Abra uma **conta demo** primeiro
3. Preencha no `.env`:
   ```
   MT5_ACCOUNT=seu_login
   MT5_PASSWORD=sua_senha
   MT5_SERVER=servidor_da_corretora
   ```
4. Teste a conexao:
   ```bash
   python3 training/test_broker_connection.py
   ```

### 5. Iniciar com saldo real (semana 4)

Somente quando todos os criterios do passo 3 estiverem OK e a conta demo validada:

```bash
python3 core/auto_trader.py --live          # pede confirmacao antes de operar
scripts\iniciar_auto_trader.bat             # Windows -> opcao 2 (Live)
```

**Comece com R$ 500-1000 apenas!**

---

## Arquivos Importantes

| Arquivo | O que contem |
|---------|--------------|
| `.env` | Credenciais e todas as configuracoes (nunca versionado) |
| `data/risk_state.json` | Estado do risk manager (capital, trades, drawdown) |
| `data/forward_test_log.json` | Log de sinais e trades do forward test |
| `training_results.json` | Resultados do ultimo treinamento (raiz do projeto) |
| `trained_weights.js` | Pesos otimizados dos indicadores (raiz do projeto) |
| `logs/atualizar_cotacoes.log` | Log da atualizacao do historico da B3 |

---

## Dicas de Seguranca

1. **NUNCA** use mais de 1% do capital por trade no inicio
2. **SEMPRE** faca forward test antes de usar dinheiro real
3. **MONITORE** o bot diariamente nas primeiras semanas
4. **PARE** se tiver 5+ perdas consecutivas
5. **COMECE** com 3-5 ativos apenas (nao 90)

---

## Em Caso de Problemas

### Bot nao inicia
- Ative o ambiente virtual e rode `pip install -r requirements.txt`
- Confira se o comando foi executado na raiz do projeto

### Erro de conexao com MT5
- Verifique se o MT5 esta instalado e aberto (Windows)
- Verifique as credenciais `MT5_*` no `.env`
- Rode o teste: `python3 training/test_broker_connection.py`

### Win rate muito baixo
- Retreine com `python3 training/train_conservative.py`
- Aumente o `MIN_SCORE_BUY` no `.env`
- Reduza a watchlist para ativos mais liquidos

### Cotacoes com tag SIM ou erro de token
- Veja a secao *Troubleshooting* do [README](../README.md#troubleshooting)

---

## Proximos Passos

1. **Hoje**: rodar o forward test
2. **Semana 1**: acumular 50+ trades simulados
3. **Semana 2**: ajustar parametros se necessario, chegar em 100 trades
4. **Semana 3**: configurar o MT5 com conta demo
5. **Semana 4**: iniciar com saldo real (R$ 500-1000)

Boa sorte!

# NEXUS TRADE PRO - Guia de Inicio Rapido

## Problema Diagnosticado

O bot estava configurado mas **NAO estava executando trades** de verdade. O backtest mostrava 60% win rate, mas o `risk_state.json` tinha 0 trades registrados.

## Solucao Implementada

### Arquivos Novos Criados

| Arquivo | Funcao |
|---------|--------|
| `auto_trader.py` | Sistema de trading automatico com ciclos de scan/trade |
| `train_conservative.py` | Treinamento com walk-forward validation (anti-overfitting) |
| `iniciar_auto_trader.bat` | Atalho para iniciar o bot |
| `treinar_conservador.bat` | Atalho para treinar com metricas realistas |

### Configuracoes Ajustadas

O `.env` foi atualizado com parametros **mais conservadores**:

```
RISK_PER_TRADE=1.0%    (era 2.0%)
STOP_LOSS=4.0%         (era 3.0%)
TAKE_PROFIT=8.0%       (ratio 1:2)
MAX_ORDER_VALUE=R$300  (era R$1000)
MAX_POSITIONS=3        (era 5)
```

---

## Passo a Passo para Comecar

### 1. Instalar Dependencias (apenas uma vez)

```bash
cd D:\Users\elida\Desktop\NexusTrade
pip install -r requirements.txt
```

### 2. Retreinar com Modelo Conservador

Execute o treinamento conservador para obter pesos mais realistas:

```bash
treinar_conservador.bat
```

Isso usa:
- Walk-forward validation (70% treino, 15% validacao, 15% teste)
- Penalizacao de overfitting
- Modelo simplificado (4 indicadores: Stoch, ADX, MACD, Volume)

### 3. Iniciar Forward Testing (SEMANA 1-2)

```bash
iniciar_auto_trader.bat
```

Escolha opcao **1** (Forward Test).

O bot vai:
- Escanear o mercado a cada 60 segundos
- Gerar sinais de compra/venda
- Registrar trades **simulados** no `forward_test_log.json`
- Atualizar o `risk_state.json` com estatisticas

**Meta**: Acumular 100+ trades simulados e validar win rate > 50%

### 4. Analisar Resultados

Apos alguns dias, verifique:

```bash
python -c "import json; print(json.load(open('forward_test_log.json'))['stats'])"
```

Criterios para ir pro saldo real:
- [x] 100+ trades
- [x] Win rate > 50%
- [x] Max drawdown < 15%
- [x] Profit factor > 1.3

### 5. Configurar Corretora (SEMANA 3)

Quando estiver pronto, configure o MetaTrader 5:

1. Instale o MT5 da sua corretora (Clear, Rico, Modal, etc)
2. Abra conta demo primeiro
3. Preencha no `.env`:
   ```
   MT5_ACCOUNT=seu_login
   MT5_PASSWORD=sua_senha
   MT5_SERVER=servidor_da_corretora
   ```
4. Teste a conexao:
   ```bash
   python test_broker_connection.py
   ```

### 6. Iniciar com Saldo Real (SEMANA 4)

Quando todos os criterios estiverem OK:

```bash
iniciar_auto_trader.bat
```

Escolha opcao **2** (Live).

**Comece com R$500-1000 apenas!**

---

## Arquivos Importantes

| Arquivo | O que contem |
|---------|--------------|
| `.env` | Credenciais e configuracoes |
| `risk_state.json` | Estado do risk manager (capital, trades, drawdown) |
| `forward_test_log.json` | Log de sinais e trades do forward testing |
| `training_results.json` | Resultados do ultimo treinamento |
| `trained_weights.js` | Pesos otimizados dos indicadores |

---

## Dicas de Seguranca

1. **NUNCA** use mais de 1% do capital por trade no inicio
2. **SEMPRE** faca forward test antes de usar dinheiro real
3. **MONITORE** o bot diariamente nas primeiras semanas
4. **PARE** se tiver 5+ perdas consecutivas
5. **COMECE** com 3-5 ativos apenas (nao 70+)

---

## Em Caso de Problemas

### Bot nao inicia
```bash
pip install yfinance pandas
```

### Erro de conexao com MT5
- Verifique se o MT5 esta instalado
- Verifique credenciais no `.env`
- Rode o teste: `python test_broker_connection.py`

### Win rate muito baixo
- Re-treine com `treinar_conservador.bat`
- Aumente o `MIN_SCORE_BUY` no `.env`
- Reduza a watchlist para ativos mais liquidos

---

## Proximos Passos

1. **Hoje**: Rodar forward test
2. **Semana 1**: Acumular 50+ trades simulados
3. **Semana 2**: Ajustar parametros se necessario, chegar em 100 trades
4. **Semana 3**: Configurar MT5 com conta demo
5. **Semana 4**: Iniciar com saldo real (R$500-1000)

Boa sorte!

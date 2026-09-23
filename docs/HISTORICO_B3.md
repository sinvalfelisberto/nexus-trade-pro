# Histórico oficial da B3 no MySQL

Importadores de dados oficiais da B3 para um banco MySQL: **cotações diárias** (Séries Históricas,
arquivos COTAHIST) e **proventos** (dividendos, JCP, rendimentos de FII e eventos em ações).
É o que alimenta os gráficos do Nexus Trade Pro, e pode ser reutilizado em outros projetos.

- Fonte oficial e gratuita: `https://bvmf.bmfbovespa.com.br/InstDados/SerHist/`
- Sem token, sem cadastro, sem limite de requisições
- Cotações diárias (abertura, máxima, mínima, média, fechamento, negócios, quantidade, volume)

Arquivos:

| Arquivo | Para quê |
|---|---|
| `core/b3_history.py` | Cotações: importador (CLI) e funções de consulta |
| `core/b3_proventos.py` | Proventos: importador (CLI) |
| `sql/bolsa_schema.sql` | DDL das tabelas e da view (gerado pelos `--sql` dos dois importadores) |
| `scripts/atualizar_cotacoes.sh` / `.bat` | Atualização diária de cotações e proventos (Linux / Windows), com log em `logs/` |

## Tabelas

Criadas automaticamente na primeira execução (o prefixo `bolsa_` separa essas tabelas das
demais do banco):

**`bolsa_cotacoes_diarias`** — uma linha por ativo por pregão. Chave: `(ticker, data)`.

| Coluna | Conteúdo |
|---|---|
| `ticker` | Código de negociação (PETR4, HGLG11, MELI34...) |
| `data` | Data do pregão |
| `codbdi` | `02` ação, `12` FII, `14` ETF/certificado, `34` BDR |
| `nome`, `especificacao` | Nome resumido da empresa e tipo do papel (ON, PN, CI, DRN...) |
| `abertura`, `maxima`, `minima`, `medio`, `fechamento` | Preços em R$ por unidade (já divididos pelo fator de cotação) |
| `negocios` | Número de negócios |
| `quantidade` | Quantidade de títulos negociados |
| `volume` | Volume financeiro em R$ |

**`bolsa_arquivos_importados`** — controle dos arquivos já importados (evita reimportar) e dos
dias sem pregão (`tipo = 'D'`, `registros = 0`).

**`bolsa_ativos`** — cadastro `ticker` × `isin` × `emissor` (ex.: PETR4 × BRPETRACNPR6 × PETR),
com o primeiro e o último pregão vistos. Extraído dos mesmos arquivos COTAHIST e atualizado a cada
importação. É o que liga os proventos (que a B3 informa por ISIN) aos tickers.

**`bolsa_proventos`** — dividendos, JCP e rendimentos (valor bruto por ação/cota), com data de
aprovação, data-com, data de pagamento e período de referência. Ver [Proventos](#proventos).

**`bolsa_eventos_acoes`** — desdobramentos, grupamentos e bonificações, com o fator informado pela B3.

**`bolsa_proventos_emissores`** — quando cada emissor foi consultado e se houve erro.

**`bolsa_vw_proventos`** (view) — `bolsa_proventos` com a coluna `ticker` (via `bolsa_ativos`).

## Configuração (`.env`)

```ini
DB_OLD_HOST=seu-host-mysql
DB_OLD_PORT=3306
DB_OLD_NAME=seu_banco
DB_OLD_USER=seu_usuario
DB_OLD_PASS=sua_senha

B3_HISTORY_YEARS=5          # anos mantidos no banco
B3_CODBDI=02,12,14,34       # tipos de papel importados
B3_UPDATE_HOURS=6           # intervalo da atualização automática do servidor
```

O usuário do banco precisa de permissão para `CREATE TABLE`, `INSERT`, `UPDATE`, `DELETE` e `SELECT`.

## Comandos

Na raiz do projeto:

```bash
python3 core/b3_history.py --carga       # carga inicial (últimos B3_HISTORY_YEARS anos)
python3 core/b3_history.py --atualizar   # procura e importa os pregões que faltam
python3 core/b3_history.py --verificar   # só lista o que falta, sem importar
python3 core/b3_history.py --status      # linhas, ativos, período e tamanho no banco
python3 core/b3_history.py --ativos      # reconstrói o cadastro ticker x ISIN (bolsa_ativos)
python3 core/b3_history.py --sql         # imprime o DDL (não conecta no banco)
```

- **Carga inicial:** baixa um arquivo anual por ano (~90 MB cada) e grava só o mercado à vista.
  Referência (5 anos, CODBDI 02/12/14/34): ~6 minutos, 1,45 milhão de linhas, 2.561 ativos, ~280 MB.
  Pode ser repetida sem duplicar dados (`INSERT ... ON DUPLICATE KEY UPDATE`).
- **Atualização:** verifica **todo o período** mantido, não só depois da última data:
  - dias úteis sem nenhuma cotação (buracos no meio do histórico ou pregões novos);
  - dias incompletos (menos de 60% dos ativos dos pregões vizinhos, ex.: importação interrompida).

  Baixa só o necessário: o arquivo diário (~0,5 MB) de cada dia, ou o mensal quando faltam mais
  de 5 dias num mês já fechado. Dia útil sem arquivo há mais de 4 dias é registrado como feriado
  (em `bolsa_arquivos_importados`, com `registros = 0`) e não é consultado de novo; o do dia
  atual fica pendente até a B3 publicar. Também remove o que ficou mais antigo que `B3_HISTORY_YEARS`.
  Na primeira execução após a carga, os feriados do período são confirmados uma vez (~10 s).
- **Atualização diária agendada** (roda mesmo com o servidor desligado):

  ```bash
  # Linux (cron): todo dia às 07:00 - crontab -e e adicione:
  0 7 * * * /caminho/do/projeto/scripts/atualizar_cotacoes.sh

  # Windows (Agendador de Tarefas):
  schtasks /create /tn "NexusAtualizarCotacoes" /sc daily /st 07:00 /tr "C:\caminho\do\projeto\scripts\atualizar_cotacoes.bat"
  ```

  O arquivo do pregão sai por volta das 23h30; rodar de manhã pega o dia anterior.
- **No Nexus Trade Pro**, o servidor (`python3 core/server_fastmcp.py http`) roda a atualização
  sozinho ao subir e a cada `B3_UPDATE_HOURS` horas. A vela do pregão em andamento vem da brapi.

## Proventos

Fonte: API pública de empresas listadas da B3, a mesma do site B3 > Empresas listadas
(`sistemaswebb3-listados.b3.com.br`), sem token.

```bash
python3 core/b3_proventos.py --atualizar                   # todos os emissores (ações, FIIs, BDRs) da base
python3 core/b3_proventos.py --atualizar --emissores PETR,VALE,HGLG
python3 core/b3_proventos.py --atualizar --dias 1          # só os consultados há mais de 1 dia
python3 core/b3_proventos.py --status
python3 core/b3_proventos.py --sql
```

- **Pré-requisito:** `bolsa_ativos` preenchida. Numa base carregada antes da existência dessa tabela,
  rode uma vez `python3 core/b3_history.py --ativos` (~1 min, só lê os arquivos anuais).
- **Emissores consultados:** os de ações (`02`), FIIs (`12`) e BDRs (`34`) negociados no último ano,
  cerca de 1.570 (pausa de 0,2 s entre consultas, para não sobrecarregar a B3).
- **Janela de ~12 meses:** a B3 devolve basicamente os proventos em dinheiro dos últimos ~12 meses
  (na primeira carga, 99% dos registros; só 84 de 62 emissores eram mais antigos). Por isso
  `bolsa_proventos` é **acumulativa**: o que sai da janela continua na base. Dentro da janela, a base
  acompanha a B3 (proventos que ela deixa de listar, como cancelamentos, são removidos). Para montar
  histórico, mantenha a atualização rodando; proventos anteriores à primeira carga não estão
  disponíveis nessa API. Os eventos em ações vêm com o histórico completo.
- **Tipos (`tipo`):** `DIVIDENDO`, `JRS CAP PROPRIO` (JCP), `RENDIMENTO` (FIIs), e também
  `AMORTIZACAO RF` e `REST CAP DIN` (amortização e restituição de capital: devolução do capital
  investido, não rendimento; exclua-os ao calcular dividend yield).
- **Primeira carga (referência):** 1.569 emissores em ~12 min, 7.476 proventos de 1.133 emissores
  (1.220 tickers), 1.300 eventos em ações, ~3 MB.
- **Sem ticker na view:** recibos e direitos de subscrição (ex.: ISINs `BRHGLGR...` do HGLG11) não
  entram nas cotações importadas; seus proventos aparecem com `ticker = NULL`.
- **Atualização diária:** `scripts/atualizar_cotacoes.sh` e o servidor já atualizam os proventos
  (cada emissor no máximo uma vez por dia).

```sql
-- Proventos da PETR4 nos últimos 12 meses
SELECT tipo, valor, data_com, data_pagamento, referente
FROM bolsa_vw_proventos WHERE ticker = 'PETR4' ORDER BY data_com DESC;

-- Próximos pagamentos
SELECT ticker, tipo, valor, data_pagamento FROM bolsa_vw_proventos
WHERE data_pagamento >= CURDATE() ORDER BY data_pagamento, ticker;

-- Dividend yield dos últimos 12 meses (soma dos proventos / último fechamento).
-- Valores extremos (centenas de %) costumam ser fundos em liquidação ou papéis com grupamento
-- no período (preços nominais) - confira bolsa_eventos_acoes antes de tirar conclusões.
SELECT p.ticker, ROUND(SUM(p.valor), 4) AS proventos_12m, c.fechamento,
       ROUND(100 * SUM(p.valor) / c.fechamento, 2) AS dy_pct
FROM bolsa_vw_proventos p
JOIN bolsa_cotacoes_diarias c ON c.ticker = p.ticker
     AND c.data = (SELECT MAX(data) FROM bolsa_cotacoes_diarias)
WHERE p.data_com >= CURDATE() - INTERVAL 12 MONTH
  AND p.tipo IN ('DIVIDENDO', 'JRS CAP PROPRIO', 'RENDIMENTO')   -- sem amortizacao/restituicao
GROUP BY p.ticker, c.fechamento ORDER BY dy_pct DESC LIMIT 20;
```

## Reutilizando em outro projeto

O `b3_history.py` e o `b3_proventos.py` funcionam sozinhos, fora do Nexus Trade Pro
(o de proventos precisa do `b3_history.py` na mesma pasta):

```bash
pip install httpx pymysql python-dotenv
cp core/b3_history.py core/b3_proventos.py /caminho/do/outro/projeto/
cd /caminho/do/outro/projeto
# crie um .env com as variáveis DB_OLD_* (e, se quiser, as B3_*) no diretório atual
python3 b3_history.py --carga
python3 b3_proventos.py --atualizar
```

Sem o `env_config.py` do Nexus Trade Pro ao lado, ele lê o `.env` do diretório atual
(ou as variáveis de ambiente). Para usar como biblioteca:

```python
from datetime import date
import b3_history

candles = b3_history.get_daily("PETR4", since=date(2025, 1, 1))  # velas diárias
mensal = b3_history.aggregate(candles, "1mo")                     # 1wk, 1mo ou 1y
```

Para trocar o prefixo das tabelas, altere as constantes `TABLE_*` no início de cada arquivo
(e `VIEW_CASH` no de proventos).

## Consultas úteis

```sql
-- Últimos 10 pregões da PETR4
SELECT data, abertura, maxima, minima, fechamento, quantidade
FROM bolsa_cotacoes_diarias WHERE ticker = 'PETR4' ORDER BY data DESC LIMIT 10;

-- Maiores volumes financeiros do último pregão
SELECT ticker, fechamento, volume FROM bolsa_cotacoes_diarias
WHERE data = (SELECT MAX(data) FROM bolsa_cotacoes_diarias)
ORDER BY volume DESC LIMIT 20;

-- Fechamento mensal de um ativo
SELECT DATE_FORMAT(data, '%Y-%m') AS mes,
       SUBSTRING_INDEX(GROUP_CONCAT(fechamento ORDER BY data DESC), ',', 1) AS fechamento
FROM bolsa_cotacoes_diarias WHERE ticker = 'VALE3' GROUP BY mes ORDER BY mes;

-- Ativos que pararam de negociar (código antigo, fusão, saída da bolsa)
SELECT ticker, MAX(data) AS ultimo_pregao FROM bolsa_cotacoes_diarias
GROUP BY ticker HAVING ultimo_pregao < CURDATE() - INTERVAL 30 DAY ORDER BY ultimo_pregao DESC;
```

## Limitações

- **Preços nominais:** não há ajuste por dividendos, desdobramentos ou grupamentos. Em gráficos
  longos, um desdobramento aparece como uma queda brusca de preço.
- **Sem dados do dia:** a B3 publica o arquivo do pregão por volta das 23h30.
- **Feriados:** não há arquivo; a atualização registra e segue para o próximo dia.
- **Mudança de código:** quando uma empresa troca de ticker (ex.: ELET3 → AXIA3), os dois
  códigos aparecem separados, cada um com seu período.

## Layout COTAHIST (campos usados)

Registro tipo `01` (cotação), posições 1-based do layout oficial da B3:

| Campo | Posição | Uso |
|---|---|---|
| TIPREG | 1–2 | `01` = cotação |
| DATPRE | 3–10 | data (AAAAMMDD) |
| CODBDI | 11–12 | tipo de papel |
| CODNEG | 13–24 | ticker |
| TPMERC | 25–27 | `010` = mercado à vista |
| NOMRES / ESPECI | 28–39 / 40–49 | nome e especificação |
| PREABE, PREMAX, PREMIN, PREMED, PREULT | 57–121 | preços (2 casas decimais implícitas) |
| TOTNEG / QUATOT / VOLTOT | 148–152 / 153–170 / 171–188 | negócios, quantidade, volume |
| FATCOT | 211–217 | fator de cotação (preço por lote de N títulos) |
| CODISI | 231–242 | código ISIN (usado em `bolsa_ativos`) |

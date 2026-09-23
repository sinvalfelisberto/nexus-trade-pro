"""
NEXUS TRADE PRO — Proventos da B3 (dividendos, JCP, rendimentos e eventos em acoes)

Consulta a API publica de empresas listadas da B3 (a mesma do site
https://www.b3.com.br > Empresas listadas) e grava no MySQL do .env (DB_OLD_*),
no mesmo schema e com o mesmo prefixo "bolsa_" do historico de cotacoes:

    bolsa_proventos             dividendos, JCP, rendimentos de FII (valor por acao/cota) - acumulativa:
                                a API da B3 so mostra ~12 meses; o que sai da janela continua na base
    bolsa_eventos_acoes         desdobramentos, grupamentos e bonificacoes (fator)
    bolsa_proventos_emissores   controle: quando cada emissor foi consultado
    bolsa_vw_proventos          view: proventos com o ticker (via bolsa_ativos)

Os proventos vem por ISIN; o ticker e obtido de bolsa_ativos, preenchida a partir
dos arquivos COTAHIST (python3 core/b3_history.py --ativos).

Uso (na raiz do projeto):
    python3 core/b3_proventos.py --atualizar                    # todos os emissores da base
    python3 core/b3_proventos.py --atualizar --emissores PETR,VALE
    python3 core/b3_proventos.py --atualizar --dias 7           # so os consultados ha mais de 7 dias
    python3 core/b3_proventos.py --status
    python3 core/b3_proventos.py --sql

Guia: docs/HISTORICO_B3.md
"""
import os
import sys
import json
import time
import base64
import hashlib
import argparse
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b3_history  # conexao, configuracao e cadastro de ativos

API_URL = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/{}"
TABLE_CASH = "bolsa_proventos"
TABLE_STOCK = "bolsa_eventos_acoes"
TABLE_ISSUERS = "bolsa_proventos_emissores"
VIEW_CASH = "bolsa_vw_proventos"
REQUEST_PAUSE = 0.2  # segundos entre consultas, para nao sobrecarregar o site da B3

DDL = [f"""
CREATE TABLE IF NOT EXISTS {TABLE_CASH} (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    chave           CHAR(40)        NOT NULL COMMENT 'SHA-1 de isin|tipo|aprovacao|data_com|valor|referente|pagamento',
    emissor         VARCHAR(8)      NOT NULL COMMENT 'Codigo do emissor na B3 (ex.: PETR)',
    isin            CHAR(12)        NOT NULL COMMENT 'ISIN do papel que recebe o provento',
    tipo            VARCHAR(30)     NOT NULL COMMENT 'DIVIDENDO, JRS CAP PROPRIO, RENDIMENTO...',
    valor           DECIMAL(24,11)  NOT NULL COMMENT 'Valor bruto por acao/cota em R$',
    data_aprovacao  DATE            NULL,
    data_com        DATE            NULL     COMMENT 'Ultimo dia com direito (lastDatePrior)',
    data_pagamento  DATE            NULL     COMMENT 'NULL quando ainda nao definida',
    referente       VARCHAR(60)     NULL     COMMENT 'Periodo de referencia (ex.: Anual/2026, AGOSTO/2026)',
    observacao      VARCHAR(500)    NULL,
    atualizado_em   DATETIME        NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_chave (chave),
    KEY idx_isin_data_com (isin, data_com),
    KEY idx_emissor (emissor),
    KEY idx_data_pagamento (data_pagamento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Proventos em dinheiro (dividendos, JCP, rendimentos) - API de empresas listadas da B3; acumulativo'
""", f"""
CREATE TABLE IF NOT EXISTS {TABLE_STOCK} (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    emissor         VARCHAR(8)      NOT NULL,
    isin            CHAR(12)        NOT NULL,
    tipo            VARCHAR(30)     NOT NULL COMMENT 'DESDOBRAMENTO, GRUPAMENTO, BONIFICACAO...',
    fator           DECIMAL(24,11)  NOT NULL COMMENT 'Percentual informado pela B3 (100 = 1 nova para cada 1)',
    data_aprovacao  DATE            NULL,
    data_com        DATE            NULL,
    observacao      VARCHAR(500)    NULL,
    atualizado_em   DATETIME        NOT NULL,
    PRIMARY KEY (id),
    KEY idx_isin_data_com (isin, data_com),
    KEY idx_emissor (emissor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Proventos em acoes (desdobramento, grupamento, bonificacao) - API de empresas listadas da B3'
""", f"""
CREATE TABLE IF NOT EXISTS {TABLE_ISSUERS} (
    emissor         VARCHAR(8)      NOT NULL,
    nome            VARCHAR(120)    NULL,
    codigo_cvm      VARCHAR(12)     NULL,
    proventos       INT UNSIGNED    NOT NULL DEFAULT 0,
    eventos         INT UNSIGNED    NOT NULL DEFAULT 0,
    consultado_em   DATETIME        NOT NULL,
    erro            VARCHAR(255)    NULL     COMMENT 'Mensagem da ultima falha (NULL = sucesso)',
    PRIMARY KEY (emissor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Controle da consulta de proventos por emissor'
""", f"""
CREATE OR REPLACE VIEW {VIEW_CASH} AS
SELECT a.ticker, p.emissor, p.isin, p.tipo, p.valor, p.data_aprovacao, p.data_com,
       p.data_pagamento, p.referente, p.observacao
FROM {TABLE_CASH} p
LEFT JOIN {b3_history.TABLE_ASSETS} a ON a.isin = p.isin
"""]


def create_tables(conn):
    b3_history.create_tables(conn)  # bolsa_ativos precisa existir para a view
    with conn.cursor() as c:
        for ddl in DDL:
            c.execute(ddl)
    conn.commit()


# ══════════════════════════════════════════════════════════════
# API DA B3
# ══════════════════════════════════════════════════════════════
def fetch_issuer(client: httpx.Client, emissor: str) -> dict:
    """Consulta os proventos de um emissor. Retorna {} se a B3 nao tiver dados."""
    payload = base64.b64encode(json.dumps({"issuingCompany": emissor, "language": "pt-br"}).encode()).decode()
    for attempt in range(3):
        try:
            r = client.get(API_URL.format(payload))
            if r.status_code == 200:
                body = r.text.strip()
                if not body or body == "null":
                    return {}
                data = r.json()
                return (data[0] if data else {}) if isinstance(data, list) else (data or {})
            if r.status_code in (404, 400):
                return {}
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"B3 nao respondeu para {emissor}")


def parse_date(value):
    """dd/mm/aaaa -> date; vazio e datas-sentinela da B3 (1900, 9999) -> None"""
    try:
        d = datetime.strptime((value or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None
    return None if d.year in (1900, 9999) else d


def parse_number(value):
    try:
        return Decimal((value or "0").strip().replace(".", "").replace(",", "."))
    except InvalidOperation:
        return Decimal(0)


def text(value, size):
    value = (value or "").strip()
    return value[:size] or None


# ══════════════════════════════════════════════════════════════
# GRAVACAO
# ══════════════════════════════════════════════════════════════
def cash_key(row) -> str:
    """Identidade de um provento: mesmos campos = mesmo provento (sem data de pagamento)"""
    isin, tipo, valor, aprovacao, data_com, _pagamento, referente = row[1], row[2], row[3], row[4], row[5], row[6], row[7]
    return f"{isin}|{tipo}|{aprovacao}|{data_com}|{valor.normalize()}|{referente}"


def save_issuer(conn, emissor: str, data: dict) -> tuple:
    """Grava os proventos do emissor.

    A API da B3 so devolve os proventos em dinheiro dos ultimos ~12 meses, por isso a tabela e
    ACUMULATIVA: o que sai da janela da B3 continua na base. Dentro da janela devolvida (data-com
    a partir da mais antiga recebida), a base e sincronizada: proventos que a B3 deixou de listar
    (ex.: cancelados) sao removidos. Os eventos em acoes vem com o historico completo e sao substituidos.
    """
    now = datetime.now()
    cash = [
        (emissor, x.get("isinCode") or x.get("assetIssued"), text(x.get("label"), 30), parse_number(x.get("rate")),
         parse_date(x.get("approvedOn")), parse_date(x.get("lastDatePrior")), parse_date(x.get("paymentDate")),
         text(x.get("relatedTo"), 60), text(x.get("remarks"), 500), now)
        for x in data.get("cashDividends") or [] if (x.get("isinCode") or x.get("assetIssued"))
    ]
    stock = [
        (emissor, x.get("isinCode") or x.get("assetIssued"), text(x.get("label"), 30), parse_number(x.get("factor")),
         parse_date(x.get("approvedOn")), parse_date(x.get("lastDatePrior")), text(x.get("remarks"), 500), now)
        for x in data.get("stockDividends") or [] if (x.get("isinCode") or x.get("assetIssued"))
    ]

    # Chave inclui a data de pagamento (parcelas iguais com datas diferentes sao proventos distintos)
    keyed = [(hashlib.sha1(f"{cash_key(r)}|{r[6]}".encode()).hexdigest(),) + r for r in cash]
    with conn.cursor() as c:
        if keyed:
            window_start = min((r[5] for r in cash if r[5]), default=None)
            keys = [k[0] for k in keyed]
            if window_start:
                placeholders = ",".join(["%s"] * len(keys))
                c.execute(f"""DELETE FROM {TABLE_CASH} WHERE emissor=%s AND data_com >= %s
                              AND chave NOT IN ({placeholders})""", [emissor, window_start] + keys)
            c.executemany(
                f"""INSERT INTO {TABLE_CASH} (chave, emissor, isin, tipo, valor, data_aprovacao, data_com,
                                               data_pagamento, referente, observacao, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE observacao=VALUES(observacao), atualizado_em=VALUES(atualizado_em)""",
                keyed)
        c.execute(f"DELETE FROM {TABLE_STOCK} WHERE emissor=%s", (emissor,))
        if stock:
            c.executemany(
                f"""INSERT INTO {TABLE_STOCK} (emissor, isin, tipo, fator, data_aprovacao, data_com, observacao,
                                                atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", stock)
        c.execute(
            f"""INSERT INTO {TABLE_ISSUERS} (emissor, nome, codigo_cvm, proventos, eventos, consultado_em, erro)
                VALUES (%s, %s, %s, %s, %s, %s, NULL)
                ON DUPLICATE KEY UPDATE nome=VALUES(nome), codigo_cvm=VALUES(codigo_cvm), proventos=VALUES(proventos),
                                        eventos=VALUES(eventos), consultado_em=VALUES(consultado_em), erro=NULL""",
            (emissor, text(data.get("tradingName"), 120), text(data.get("codeCVM"), 12), len(cash), len(stock), now))
    conn.commit()
    return len(cash), len(stock)


def save_error(conn, emissor: str, message: str):
    with conn.cursor() as c:
        c.execute(
            f"""INSERT INTO {TABLE_ISSUERS} (emissor, consultado_em, erro) VALUES (%s, NOW(), %s)
                ON DUPLICATE KEY UPDATE consultado_em=VALUES(consultado_em), erro=VALUES(erro)""",
            (emissor, message[:255]))
    conn.commit()


# ══════════════════════════════════════════════════════════════
# ATUALIZACAO
# ══════════════════════════════════════════════════════════════
def issuers_from_db(conn, max_age_days: int = None) -> list:
    """Emissores de acoes, FIIs e BDRs negociados no ultimo ano (bolsa_ativos).
    max_age_days: pula os que foram consultados com sucesso ha menos desse numero de dias."""
    with conn.cursor() as c:
        c.execute(
            f"""SELECT DISTINCT emissor FROM {b3_history.TABLE_ASSETS}
                WHERE codbdi IN ('02', '12', '34') AND ultimo_pregao >= %s ORDER BY emissor""",
            (date.today() - timedelta(days=365),))
        issuers = [r[0] for r in c.fetchall()]
        if max_age_days:
            c.execute(f"SELECT emissor FROM {TABLE_ISSUERS} WHERE erro IS NULL AND consultado_em >= %s",
                      (datetime.now() - timedelta(days=max_age_days),))
            recent = {r[0] for r in c.fetchall()}
            issuers = [e for e in issuers if e not in recent]
    return issuers


def update(conn, issuers: list = None, max_age_days: int = None) -> dict:
    create_tables(conn)
    if issuers is None:
        issuers = issuers_from_db(conn, max_age_days)
        if not issuers:
            with conn.cursor() as c:
                c.execute(f"SELECT COUNT(*) FROM {b3_history.TABLE_ASSETS}")
                empty = c.fetchone()[0] == 0
            print("[Proventos] Cadastro de ativos vazio - rode: python3 core/b3_history.py --ativos" if empty
                  else "[Proventos] Nenhum emissor pendente")
            return {"emissores": 0}

    t0 = time.time()
    totals = {"emissores": 0, "com_proventos": 0, "proventos": 0, "eventos": 0, "erros": []}
    print(f"[Proventos] Consultando {len(issuers)} emissor(es) na B3...")
    with httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0 (nexus-trade-pro)"}) as client:
        for i, emissor in enumerate(issuers, 1):
            try:
                data = fetch_issuer(client, emissor)
                n_cash, n_stock = save_issuer(conn, emissor, data)
                totals["proventos"] += n_cash
                totals["eventos"] += n_stock
                totals["com_proventos"] += bool(n_cash)
            except Exception as e:
                totals["erros"].append(emissor)
                save_error(conn, emissor, str(e))
            totals["emissores"] += 1
            print(f"\r[Proventos] {i}/{len(issuers)} emissores | {totals['proventos']:,} proventos "
                  f"| {len(totals['erros'])} erro(s)", end="", flush=True)
            time.sleep(REQUEST_PAUSE)
    print(f"\n[Proventos] Concluido em {time.time() - t0:.0f}s")
    if totals["erros"]:
        print(f"[Proventos] Falharam (tentam de novo na proxima execucao): {', '.join(totals['erros'][:20])}")
    return totals


def status(conn) -> dict:
    create_tables(conn)
    with conn.cursor() as c:
        c.execute(f"SELECT COUNT(*), COUNT(DISTINCT emissor), MIN(data_com), MAX(data_com) FROM {TABLE_CASH}")
        rows, issuers, first, last = c.fetchone()
        c.execute(f"SELECT COUNT(*) FROM {TABLE_STOCK}")
        events = c.fetchone()[0]
        c.execute(f"SELECT COUNT(*) FROM {TABLE_CASH} p LEFT JOIN {b3_history.TABLE_ASSETS} a ON a.isin = p.isin "
                  f"WHERE a.ticker IS NULL")
        no_ticker = c.fetchone()[0]
        c.execute(f"SELECT COUNT(*), SUM(erro IS NOT NULL), MAX(consultado_em) FROM {TABLE_ISSUERS}")
        checked, errors, last_run = c.fetchone()
    return {"proventos": rows, "emissores_com_proventos": issuers, "primeira_data_com": first,
            "ultima_data_com": last, "eventos_acoes": events, "proventos_sem_ticker": no_ticker,
            "emissores_consultados": checked, "emissores_com_erro": int(errors or 0), "ultima_consulta": last_run}


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Proventos da B3 (dividendos, JCP, rendimentos) no MySQL do .env")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--atualizar", action="store_true", help="consulta a B3 e grava os proventos")
    group.add_argument("--status", action="store_true", help="resumo do que esta no banco")
    group.add_argument("--sql", action="store_true", help="imprime o DDL (nao conecta no banco)")
    parser.add_argument("--emissores", help="lista de emissores separados por virgula (ex.: PETR,VALE,HGLG)")
    parser.add_argument("--dias", type=int, help="so consulta emissores atualizados ha mais de N dias")
    args = parser.parse_args()

    if args.sql:
        print("-- Gerado por: python3 core/b3_proventos.py --sql")
        print(";\n\n".join(d.strip() for d in DDL) + ";")
        sys.exit(0)

    if not b3_history.is_configured():
        sys.exit("[Proventos] Banco nao configurado: preencha DB_OLD_HOST, DB_OLD_NAME, DB_OLD_USER e DB_OLD_PASS no .env")

    conn = b3_history.connect()
    try:
        if args.atualizar:
            issuers = [e.strip().upper() for e in args.emissores.split(",") if e.strip()] if args.emissores else None
            update(conn, issuers, args.dias)
        print("[Proventos] Status:", status(conn))
    finally:
        conn.close()

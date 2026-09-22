"""
NEXUS TRADE PRO — Historico oficial da B3 (Series Historicas / COTAHIST)

Baixa os arquivos COTAHIST da B3, extrai o mercado a vista e grava no MySQL
configurado no .env (DB_OLD_*), em tabelas com prefixo "bolsa_":

    bolsa_cotacoes_diarias     uma linha por ativo por pregao
    bolsa_arquivos_importados  controle dos arquivos ja importados

Uso (na raiz do projeto):
    python3 core/b3_history.py --carga        # carga inicial (B3_HISTORY_YEARS anos)
    python3 core/b3_history.py --atualizar    # procura e importa os pregoes que faltam
    python3 core/b3_history.py --verificar    # so lista o que falta, sem importar
    python3 core/b3_history.py --status       # resumo do que esta no banco
    python3 core/b3_history.py --sql          # imprime o DDL das tabelas

Guia completo (inclusive para reutilizar em outros projetos): docs/HISTORICO_B3.md

Layout do arquivo: https://www.b3.com.br (Series Historicas - layout COTAHIST)
Precos sao nominais (sem ajuste por proventos/desdobramentos).
"""
import io
import os
import sys
import time
import zipfile
import argparse
import tempfile
from datetime import date, datetime, timedelta

import httpx
import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import env_config as cfg  # Nexus Trade Pro: .env da raiz, recarregado automaticamente
except ImportError:
    # Uso avulso em outros projetos: le o .env do diretorio atual (ou variaveis de ambiente)
    from dotenv import load_dotenv

    load_dotenv(override=True)

    class cfg:
        get_str = staticmethod(lambda k, d="": (os.environ.get(k) or "").strip() or d)
        get_int = staticmethod(lambda k, d: int(os.environ.get(k) or d))

B3_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/{}"
TABLE_QUOTES = "bolsa_cotacoes_diarias"
TABLE_FILES = "bolsa_arquivos_importados"
BATCH_SIZE = 5000


def history_years() -> int:
    return cfg.get_int("B3_HISTORY_YEARS", 5)


def allowed_bdi() -> set:
    # 02 acoes (lote padrao), 12 FII, 14 ETF/certificados, 34 BDR
    return {c.strip() for c in cfg.get_str("B3_CODBDI", "02,12,14,34").split(",") if c.strip()}


def cutoff_date() -> date:
    today = date.today()
    try:
        return today.replace(year=today.year - history_years())
    except ValueError:  # 29/02
        return today.replace(year=today.year - history_years(), day=28)


# ══════════════════════════════════════════════════════════════
# BANCO
# ══════════════════════════════════════════════════════════════
def is_configured() -> bool:
    return bool(cfg.get_str("DB_OLD_HOST") and cfg.get_str("DB_OLD_NAME") and cfg.get_str("DB_OLD_USER"))


def connect():
    return pymysql.connect(
        host=cfg.get_str("DB_OLD_HOST"),
        port=cfg.get_int("DB_OLD_PORT", 3306),
        user=cfg.get_str("DB_OLD_USER"),
        password=cfg.get_str("DB_OLD_PASS"),
        database=cfg.get_str("DB_OLD_NAME"),
        charset="utf8mb4",
        connect_timeout=15,
        autocommit=False,
    )


DDL = [f"""
CREATE TABLE IF NOT EXISTS {TABLE_QUOTES} (
    ticker          VARCHAR(12)     NOT NULL COMMENT 'Codigo de negociacao (CODNEG)',
    data            DATE            NOT NULL COMMENT 'Data do pregao',
    codbdi          CHAR(2)         NOT NULL COMMENT '02 acao, 12 FII, 14 ETF/cert., 34 BDR',
    nome            VARCHAR(12)     NULL     COMMENT 'Nome resumido da empresa (NOMRES)',
    especificacao   VARCHAR(10)     NULL     COMMENT 'ON, PN, CI, DR3... (ESPECI)',
    abertura        DECIMAL(14,4)   NOT NULL,
    maxima          DECIMAL(14,4)   NOT NULL,
    minima          DECIMAL(14,4)   NOT NULL,
    medio           DECIMAL(14,4)   NOT NULL,
    fechamento      DECIMAL(14,4)   NOT NULL,
    negocios        INT UNSIGNED    NOT NULL COMMENT 'Numero de negocios (TOTNEG)',
    quantidade      BIGINT UNSIGNED NOT NULL COMMENT 'Quantidade de titulos negociados (QUATOT)',
    volume          DECIMAL(20,2)   NOT NULL COMMENT 'Volume financeiro em R$ (VOLTOT)',
    PRIMARY KEY (ticker, data),
    KEY idx_data (data)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Cotacoes diarias do mercado a vista - Series Historicas B3 (COTAHIST), precos nominais'
""", f"""
CREATE TABLE IF NOT EXISTS {TABLE_FILES} (
    arquivo         VARCHAR(40)     NOT NULL COMMENT 'Ex.: COTAHIST_A2025.ZIP',
    tipo            CHAR(1)         NOT NULL COMMENT 'A anual, M mensal, D diario',
    registros       INT UNSIGNED    NOT NULL COMMENT 'Linhas gravadas (0 em arquivo D = dia sem pregao)',
    ultimo_pregao   DATE            NULL,
    importado_em    DATETIME        NOT NULL,
    PRIMARY KEY (arquivo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Controle de importacao dos arquivos COTAHIST da B3'
"""]


def create_tables(conn):
    with conn.cursor() as c:
        for ddl in DDL:
            c.execute(ddl)
    conn.commit()


# ══════════════════════════════════════════════════════════════
# ARQUIVOS DA B3
# ══════════════════════════════════════════════════════════════
def download(filename: str):
    """Baixa um arquivo COTAHIST para um arquivo temporario. Retorna o caminho ou None se nao existir."""
    url = B3_URL.format(filename)
    with httpx.stream("GET", url, timeout=httpx.Timeout(30, read=300), follow_redirects=True) as r:
        if r.status_code == 404:
            return None
        r.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(prefix="cotahist_", suffix=".zip", delete=False)
        with tmp:
            for chunk in r.iter_bytes(1024 * 1024):
                tmp.write(chunk)
        return tmp.name


def parse_lines(zip_path: str, since: date = None):
    """Le o COTAHIST e gera tuplas prontas para o INSERT (mercado a vista, CODBDI permitidos)."""
    bdi_ok = allowed_bdi()
    with zipfile.ZipFile(zip_path) as z:
        with z.open(z.namelist()[0]) as raw:
            for line in io.TextIOWrapper(raw, encoding="latin-1"):
                # 01 = registro de cotacao; 010 = mercado a vista
                if line[:2] != "01" or line[24:27] != "010" or line[10:12] not in bdi_ok:
                    continue
                d = date(int(line[2:6]), int(line[6:8]), int(line[8:10]))
                if since and d < since:
                    continue
                fator = int(line[210:217]) or 1  # precos cotados por lote de FATCOT titulos
                price = lambda a, b: int(line[a:b]) / 100 / fator
                yield (
                    line[12:24].strip(), d, line[10:12],
                    line[27:39].strip(), " ".join(line[39:49].split()),
                    price(56, 69), price(69, 82), price(82, 95), price(95, 108), price(108, 121),
                    int(line[147:152]), int(line[152:170]), int(line[170:188]) / 100,
                )


INSERT_SQL = f"""
    INSERT INTO {TABLE_QUOTES}
        (ticker, data, codbdi, nome, especificacao, abertura, maxima, minima, medio, fechamento,
         negocios, quantidade, volume)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        codbdi=VALUES(codbdi), nome=VALUES(nome), especificacao=VALUES(especificacao),
        abertura=VALUES(abertura), maxima=VALUES(maxima), minima=VALUES(minima), medio=VALUES(medio),
        fechamento=VALUES(fechamento), negocios=VALUES(negocios), quantidade=VALUES(quantidade),
        volume=VALUES(volume)
"""


def import_file(conn, filename: str, since: date = None, force: bool = False) -> int:
    """Baixa e importa um arquivo. Retorna o numero de linhas gravadas (-1 se o arquivo nao existe)."""
    if not force:
        with conn.cursor() as c:
            c.execute(f"SELECT 1 FROM {TABLE_FILES} WHERE arquivo=%s", (filename,))
            if c.fetchone():
                print(f"[B3] {filename}: ja importado")
                return 0

    t0 = time.time()
    path = download(filename)
    if path is None:
        return -1
    try:
        total, last, batch = 0, None, []
        with conn.cursor() as c:
            for row in parse_lines(path, since):
                batch.append(row)
                last = max(last, row[1]) if last else row[1]
                if len(batch) >= BATCH_SIZE:
                    c.executemany(INSERT_SQL, batch)
                    conn.commit()
                    total += len(batch)
                    batch = []
                    print(f"\r[B3] {filename}: {total:,} linhas...", end="", flush=True)
            if batch:
                c.executemany(INSERT_SQL, batch)
                total += len(batch)
            c.execute(
                f"""INSERT INTO {TABLE_FILES} (arquivo, tipo, registros, ultimo_pregao, importado_em)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE registros=VALUES(registros), ultimo_pregao=VALUES(ultimo_pregao),
                                            importado_em=VALUES(importado_em)""",
                (filename, filename[9], total, last),
            )
        conn.commit()
        print(f"\r[B3] {filename}: {total:,} linhas em {time.time() - t0:.0f}s")
        return total
    finally:
        os.unlink(path)


# ══════════════════════════════════════════════════════════════
# CARGA E ATUALIZACAO
# ══════════════════════════════════════════════════════════════
def last_date(conn):
    with conn.cursor() as c:
        c.execute(f"SELECT MAX(data) FROM {TABLE_QUOTES}")
        return c.fetchone()[0]


def purge_old(conn) -> int:
    """Remove pregoes mais antigos que B3_HISTORY_YEARS"""
    with conn.cursor() as c:
        n = c.execute(f"DELETE FROM {TABLE_QUOTES} WHERE data < %s", (cutoff_date(),))
    conn.commit()
    if n:
        print(f"[B3] {n:,} linhas anteriores a {cutoff_date()} removidas")
    return n


def initial_load(conn):
    """Carga inicial: arquivos anuais cobrindo os ultimos B3_HISTORY_YEARS anos"""
    create_tables(conn)
    start = cutoff_date()
    print(f"[B3] Carga inicial a partir de {start} (CODBDI {','.join(sorted(allowed_bdi()))})")
    for year in range(start.year, date.today().year + 1):
        # O arquivo do ano corrente muda todo dia: sempre reimportar
        import_file(conn, f"COTAHIST_A{year}.ZIP", since=start, force=(year == date.today().year))
    purge_old(conn)


NO_SESSION_AFTER_DAYS = 4  # dia util sem arquivo ha mais que isso = feriado (a B3 publica na mesma noite)


def mark_no_session(conn, d: date):
    """Registra um dia util sem pregao (feriado), para nao tentar baixar de novo"""
    with conn.cursor() as c:
        c.execute(
            f"""INSERT IGNORE INTO {TABLE_FILES} (arquivo, tipo, registros, ultimo_pregao, importado_em)
                VALUES (%s, 'D', 0, NULL, NOW())""",
            (f"COTAHIST_D{d:%d%m%Y}.ZIP",),
        )
    conn.commit()


def find_gaps(conn):
    """Procura no periodo mantido (B3_HISTORY_YEARS) os pregoes que faltam no banco.

    Retorna (faltando, incompletos):
      faltando   - dias uteis sem nenhuma cotacao e que nao sao feriados conhecidos
      incompletos - dias com bem menos ativos que os pregoes vizinhos (importacao parcial)
    """
    start, today = cutoff_date(), date.today()
    with conn.cursor() as c:
        c.execute(f"SELECT data, COUNT(*) FROM {TABLE_QUOTES} WHERE data >= %s GROUP BY data ORDER BY data", (start,))
        counts = dict(c.fetchall())
        c.execute(f"SELECT arquivo FROM {TABLE_FILES} WHERE tipo = 'D' AND registros = 0")
        no_session = {datetime.strptime(a[10:18], "%d%m%Y").date() for (a,) in c.fetchall()}

    weekdays = (start + timedelta(days=i) for i in range((today - start).days + 1))
    missing = [d for d in weekdays if d.weekday() < 5 and d not in counts and d not in no_session]

    dates = sorted(counts)
    incomplete = []
    for i, d in enumerate(dates):
        neighbors = sorted(counts[x] for x in dates[max(0, i - 10):i] + dates[i + 1:i + 11])
        if neighbors and counts[d] < 0.6 * neighbors[len(neighbors) // 2]:
            incomplete.append(d)
    return missing, incomplete


def update(conn, dry_run: bool = False) -> dict:
    """Procura e importa os pregoes que faltam (ou estao incompletos) no banco.

    - Mes ja fechado com muitos dias faltando: usa o arquivo mensal (M)
    - Demais casos: um arquivo diario (D) por dia
    - Dia util sem arquivo ha mais de NO_SESSION_AFTER_DAYS dias: registrado como feriado
    """
    create_tables(conn)
    if last_date(conn) is None:
        print("[B3] Tabela vazia - rode a carga inicial: python3 core/b3_history.py --carga")
        return {"importadas": 0, "faltando": [], "incompletos": []}

    missing, incomplete = find_gaps(conn)
    fmt = lambda ds: ", ".join(f"{d:%d/%m/%Y}" for d in ds[:15]) + (f" ... (+{len(ds) - 15})" if len(ds) > 15 else "")
    if not missing and not incomplete:
        print(f"[B3] Base completa de {cutoff_date():%d/%m/%Y} a {last_date(conn):%d/%m/%Y}")
        purge_old(conn) if not dry_run else None
        return {"importadas": 0, "faltando": [], "incompletos": []}
    if missing:
        print(f"[B3] {len(missing)} dia(s) util(eis) sem cotacoes: {fmt(missing)}")
    if incomplete:
        print(f"[B3] {len(incomplete)} dia(s) incompleto(s): {fmt(incomplete)}")
    if dry_run:
        return {"importadas": 0, "faltando": missing, "incompletos": incomplete}

    today = date.today()
    total, holidays, pending = 0, [], []
    by_month = {}
    for d in sorted(set(missing) | set(incomplete)):
        by_month.setdefault((d.year, d.month), []).append(d)

    for (year, month), days in by_month.items():
        closed_month = (year, month) < (today.year, today.month)
        if closed_month and len(days) > 5:
            n = import_file(conn, f"COTAHIST_M{month:02d}{year}.ZIP", since=cutoff_date(), force=True)
            if n >= 0:
                total += n
                with conn.cursor() as c:
                    c.execute(f"SELECT DISTINCT data FROM {TABLE_QUOTES} WHERE YEAR(data)=%s AND MONTH(data)=%s", (year, month))
                    present = {r[0] for r in c.fetchall()}
                for d in days:
                    if d not in present:  # mes completo importado e o dia nao veio: sem pregao
                        mark_no_session(conn, d)
                        holidays.append(d)
                continue
        for d in days:
            n = import_file(conn, f"COTAHIST_D{d:%d%m%Y}.ZIP", force=True)
            if n >= 0:
                total += n
            elif (today - d).days > NO_SESSION_AFTER_DAYS:
                mark_no_session(conn, d)
                holidays.append(d)
            else:
                pending.append(d)

    if holidays:
        print(f"[B3] Sem pregao (feriado), registrado para nao repetir: {fmt(holidays)}")
    if pending:
        print(f"[B3] Ainda nao publicado pela B3 (tenta de novo na proxima execucao): {fmt(pending)}")
    purge_old(conn)
    print(f"[B3] {total:,} linhas importadas | ultimo pregao no banco: {last_date(conn):%d/%m/%Y}")
    return {"importadas": total, "faltando": missing, "incompletos": incomplete,
            "feriados": holidays, "pendentes": pending}


def status(conn) -> dict:
    create_tables(conn)
    with conn.cursor() as c:
        c.execute(f"SELECT COUNT(*), COUNT(DISTINCT ticker), MIN(data), MAX(data) FROM {TABLE_QUOTES}")
        rows, tickers, first, last = c.fetchone()
        c.execute("""SELECT ROUND((data_length + index_length) / 1024 / 1024, 1) FROM information_schema.tables
                     WHERE table_schema = DATABASE() AND table_name = %s""", (TABLE_QUOTES,))
        size = c.fetchone()
    return {"linhas": rows, "ativos": tickers, "primeiro_pregao": first, "ultimo_pregao": last,
            "tamanho_mb": float(size[0]) if size and size[0] is not None else 0}


# ══════════════════════════════════════════════════════════════
# CONSULTA PARA OS GRAFICOS
# ══════════════════════════════════════════════════════════════
def get_daily(ticker: str, since: date = None) -> list:
    """Velas diarias no formato usado pelo dashboard (date em epoch segundos, volume em quantidade)."""
    conn = connect()
    try:
        with conn.cursor() as c:
            c.execute(
                f"""SELECT data, abertura, maxima, minima, fechamento, quantidade
                    FROM {TABLE_QUOTES} WHERE ticker=%s AND data >= %s ORDER BY data""",
                (ticker.upper(), since or date(1900, 1, 1)),
            )
            return [
                {"date": int(datetime(d.year, d.month, d.day).timestamp()),
                 "open": float(o), "high": float(h), "low": float(l), "close": float(cl), "volume": int(v)}
                for d, o, h, l, cl, v in c.fetchall()
            ]
    finally:
        conn.close()


def aggregate(candles: list, interval: str) -> list:
    """Agrupa velas diarias em semanais (1wk), mensais (1mo) ou anuais (1y)."""
    if interval == "1d":
        return candles
    key = {
        "1wk": lambda d: d.isocalendar()[:2],
        "1mo": lambda d: (d.year, d.month),
        "1y": lambda d: d.year,
    }[interval]
    groups = {}
    for c in candles:
        k = key(datetime.fromtimestamp(c["date"]))
        g = groups.get(k)
        if g is None:
            groups[k] = dict(c)
        else:
            g["high"] = max(g["high"], c["high"])
            g["low"] = min(g["low"], c["low"])
            g["close"] = c["close"]
            g["volume"] += c["volume"]
    return list(groups.values())


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Historico da B3 (COTAHIST) no MySQL do .env")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--carga", action="store_true", help="carga inicial dos ultimos B3_HISTORY_YEARS anos")
    group.add_argument("--atualizar", action="store_true", help="procura e importa os pregoes que faltam ou estao incompletos")
    group.add_argument("--verificar", action="store_true", help="so lista os pregoes que faltam, sem importar")
    group.add_argument("--status", action="store_true", help="mostra o resumo do banco")
    group.add_argument("--sql", action="store_true", help="imprime o DDL das tabelas (nao conecta no banco)")
    args = parser.parse_args()

    if args.sql:
        print("-- Gerado por: python3 core/b3_history.py --sql")
        print(";\n\n".join(d.strip() for d in DDL) + ";")
        sys.exit(0)

    if not is_configured():
        sys.exit("[B3] Banco nao configurado: preencha DB_OLD_HOST, DB_OLD_NAME, DB_OLD_USER e DB_OLD_PASS no .env")

    conn = connect()
    try:
        if args.carga:
            initial_load(conn)
        elif args.atualizar:
            update(conn)
        elif args.verificar:
            update(conn, dry_run=True)
        print("[B3] Status:", status(conn))
    finally:
        conn.close()

-- Gerado por: python3 core/b3_history.py --sql e python3 core/b3_proventos.py --sql
CREATE TABLE IF NOT EXISTS bolsa_cotacoes_diarias (
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
  COMMENT='Cotacoes diarias do mercado a vista - Series Historicas B3 (COTAHIST), precos nominais';

CREATE TABLE IF NOT EXISTS bolsa_arquivos_importados (
    arquivo         VARCHAR(40)     NOT NULL COMMENT 'Ex.: COTAHIST_A2025.ZIP',
    tipo            CHAR(1)         NOT NULL COMMENT 'A anual, M mensal, D diario',
    registros       INT UNSIGNED    NOT NULL COMMENT 'Linhas gravadas (0 em arquivo D = dia sem pregao)',
    ultimo_pregao   DATE            NULL,
    importado_em    DATETIME        NOT NULL,
    PRIMARY KEY (arquivo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Controle de importacao dos arquivos COTAHIST da B3';

CREATE TABLE IF NOT EXISTS bolsa_ativos (
    ticker          VARCHAR(12)     NOT NULL COMMENT 'Codigo de negociacao',
    isin            CHAR(12)        NOT NULL COMMENT 'Codigo ISIN do papel (CODISI) - liga aos proventos',
    emissor         VARCHAR(8)      NOT NULL COMMENT 'Codigo do emissor na B3 (4 primeiras letras, ex.: PETR)',
    codbdi          CHAR(2)         NOT NULL,
    nome            VARCHAR(12)     NULL,
    especificacao   VARCHAR(10)     NULL,
    primeiro_pregao DATE            NOT NULL COMMENT 'Primeiro pregao visto nos arquivos importados',
    ultimo_pregao   DATE            NOT NULL COMMENT 'Ultimo pregao visto nos arquivos importados',
    PRIMARY KEY (ticker),
    KEY idx_isin (isin),
    KEY idx_emissor (emissor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Cadastro dos ativos (ticker x ISIN x emissor) extraido dos arquivos COTAHIST';

CREATE TABLE IF NOT EXISTS bolsa_proventos (
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
  COMMENT='Proventos em dinheiro (dividendos, JCP, rendimentos) - API de empresas listadas da B3; acumulativo';

CREATE TABLE IF NOT EXISTS bolsa_eventos_acoes (
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
  COMMENT='Proventos em acoes (desdobramento, grupamento, bonificacao) - API de empresas listadas da B3';

CREATE TABLE IF NOT EXISTS bolsa_proventos_emissores (
    emissor         VARCHAR(8)      NOT NULL,
    nome            VARCHAR(120)    NULL,
    codigo_cvm      VARCHAR(12)     NULL,
    proventos       INT UNSIGNED    NOT NULL DEFAULT 0,
    eventos         INT UNSIGNED    NOT NULL DEFAULT 0,
    consultado_em   DATETIME        NOT NULL,
    erro            VARCHAR(255)    NULL     COMMENT 'Mensagem da ultima falha (NULL = sucesso)',
    PRIMARY KEY (emissor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Controle da consulta de proventos por emissor';

CREATE OR REPLACE VIEW bolsa_vw_proventos AS
SELECT a.ticker, p.emissor, p.isin, p.tipo, p.valor, p.data_aprovacao, p.data_com,
       p.data_pagamento, p.referente, p.observacao
FROM bolsa_proventos p
LEFT JOIN bolsa_ativos a ON a.isin = p.isin;

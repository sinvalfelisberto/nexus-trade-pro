-- Gerado por: python3 core/b3_history.py --sql
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

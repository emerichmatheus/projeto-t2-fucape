-- =============================================================================
-- Data Warehouse — Star Schema (Kimball) — Steam Reviews
-- DDL idempotente: pode ser executado quantas vezes for preciso.
--
-- GRANULARIDADE DA FATO:
--   Cada linha da fato_review representa UMA review publicada por um usuário
--   da Steam sobre um jogo, na data de criação da review.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS dw;
SET search_path TO dw, public;

-- ------------------------------------------------------------- dim_tempo
-- SK inteira no formato YYYYMMDD ("smart key" de calendário, prática
-- recomendada por Kimball para a dimensão data).
CREATE TABLE IF NOT EXISTS dim_tempo (
    sk_tempo         INTEGER PRIMARY KEY,
    data_completa    DATE        NOT NULL UNIQUE,
    ano              SMALLINT    NOT NULL,
    trimestre        SMALLINT    NOT NULL,
    mes              SMALLINT    NOT NULL,
    nome_mes         VARCHAR(12) NOT NULL,
    ano_mes          CHAR(7)     NOT NULL,
    dia              SMALLINT    NOT NULL,
    dia_semana       SMALLINT    NOT NULL,   -- 1 = segunda ... 7 = domingo
    nome_dia_semana  VARCHAR(15) NOT NULL,
    fim_de_semana    BOOLEAN     NOT NULL
);

-- -------------------------------------------------------------- dim_jogo
CREATE TABLE IF NOT EXISTS dim_jogo (
    sk_jogo          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nk_app_id        INTEGER      NOT NULL UNIQUE,
    nome_jogo        VARCHAR(255) NOT NULL,
    desenvolvedora   VARCHAR(255),
    publisher        VARCHAR(255),
    genero_principal VARCHAR(100),
    generos          VARCHAR(500),
    data_lancamento  DATE,
    gratuito         BOOLEAN,
    atualizado_em    TIMESTAMP    NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------- dim_autor
-- SCD Tipo 1: atributos do autor são sobrescritos com o valor mais recente.
CREATE TABLE IF NOT EXISTS dim_autor (
    sk_autor                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nk_steamid              VARCHAR(32) NOT NULL UNIQUE,
    num_jogos_possuidos     INTEGER,
    faixa_jogos_possuidos   VARCHAR(20) NOT NULL,
    num_reviews             INTEGER,
    faixa_reviews_escritas  VARCHAR(20) NOT NULL,
    atualizado_em           TIMESTAMP   NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------ dim_idioma
CREATE TABLE IF NOT EXISTS dim_idioma (
    sk_idioma      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_idioma  VARCHAR(32)  NOT NULL UNIQUE,
    nome_idioma    VARCHAR(64)  NOT NULL
);

-- ----------------------------------------------------------- fato_review
CREATE TABLE IF NOT EXISTS fato_review (
    sk_fato                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sk_tempo                 INTEGER NOT NULL REFERENCES dim_tempo (sk_tempo),
    sk_jogo                  INTEGER NOT NULL REFERENCES dim_jogo (sk_jogo),
    sk_autor                 INTEGER NOT NULL REFERENCES dim_autor (sk_autor),
    sk_idioma                INTEGER NOT NULL REFERENCES dim_idioma (sk_idioma),
    nk_recommendation_id     VARCHAR(32) NOT NULL UNIQUE,  -- dimensão degenerada
    texto_review             TEXT NOT NULL,
    -- métricas aditivas
    qtd_review               SMALLINT NOT NULL DEFAULT 1,
    recomendou               SMALLINT NOT NULL CHECK (recomendou IN (0, 1)),
    votos_util               INTEGER  NOT NULL DEFAULT 0,
    votos_engracado          INTEGER  NOT NULL DEFAULT 0,
    qtd_comentarios          INTEGER  NOT NULL DEFAULT 0,
    horas_jogadas_na_review  NUMERIC(10, 2),
    -- métrica semi-aditiva (snapshot acumulado do autor)
    horas_jogadas_total      NUMERIC(10, 2),
    -- métrica não-aditiva (usar média)
    score_utilidade          NUMERIC(8, 6),
    -- flags
    compra_steam             BOOLEAN,
    recebeu_gratis           BOOLEAN,
    early_access             BOOLEAN,
    criado_em_ts             TIMESTAMP,
    atualizado_em_ts         TIMESTAMP,
    carregado_em             TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_fato_tempo  ON fato_review (sk_tempo);
CREATE INDEX IF NOT EXISTS ix_fato_jogo   ON fato_review (sk_jogo);
CREATE INDEX IF NOT EXISTS ix_fato_autor  ON fato_review (sk_autor);
CREATE INDEX IF NOT EXISTS ix_fato_idioma ON fato_review (sk_idioma);

-- --------------------------------------------------------- etl_auditoria
CREATE TABLE IF NOT EXISTS etl_auditoria (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dag_id             VARCHAR(100) NOT NULL,
    run_id             VARCHAR(250) NOT NULL,
    ds                 DATE,
    linhas_lidas       INTEGER,
    linhas_inseridas   INTEGER,
    linhas_atualizadas INTEGER,
    inicio             TIMESTAMPTZ,
    fim                TIMESTAMPTZ,
    status             VARCHAR(30) NOT NULL,
    detalhes           JSONB,
    UNIQUE (dag_id, run_id)
);

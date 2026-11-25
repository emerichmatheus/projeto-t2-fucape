"""Carga idempotente no Data Warehouse (PostgreSQL, via psycopg2).

Estratégia:
* dimensões -> ``INSERT ... ON CONFLICT (natural_key) DO UPDATE`` (UPSERT).
  A surrogate key é gerada pelo banco (IDENTITY) e nunca muda.
* fato -> staging temporária + ``INSERT ... SELECT`` com lookup das SKs e
  ``ON CONFLICT (nk_recommendation_id) DO UPDATE``. Rodar duas vezes a mesma
  carga não cria linhas novas, logo não infla as métricas.
* ``RETURNING (xmax = 0)`` diferencia linhas inseridas (true) de atualizadas.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from psycopg2.extras import Json, execute_values

SEARCH_PATH = "SET search_path TO dw, public;"


# ------------------------------------------------------------- staging
def _default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(type(o))


def save_staging(rows: list[dict], path: Path) -> str:
    from ingestion.raw_storage import write_jsonl_atomic
    path = Path(path)
    write_jsonl_atomic(path, (json.loads(json.dumps(r, default=_default)) for r in rows))
    return str(path)


def load_staging(path: Path) -> list[dict]:
    from ingestion.raw_storage import read_jsonl
    rows = []
    for r in read_jsonl(Path(path)):
        r["criado_em"] = datetime.fromisoformat(r["criado_em"])
        r["atualizado_em"] = datetime.fromisoformat(r["atualizado_em"])
        r["data_criacao"] = date.fromisoformat(r["data_criacao"])
        rows.append(r)
    return rows


# --------------------------------------------------------------- utils
def _count(results) -> dict:
    flags = [row[0] for row in results]
    return {"inseridas": sum(1 for f in flags if f), "atualizadas": sum(1 for f in flags if not f)}


def _upsert(conn, table: str, cols: list[str], nk: str, rows: list[dict],
            update_cols: list[str] | None = None) -> dict:
    if not rows:
        return {"inseridas": 0, "atualizadas": 0}
    update_cols = update_cols if update_cols is not None else [c for c in cols if c != nk]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    if "atualizado_em" in _table_columns(conn, table):
        set_clause += ", atualizado_em = now()"
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s "
        f"ON CONFLICT ({nk}) DO UPDATE SET {set_clause} "
        f"RETURNING (xmax = 0)"
    )
    values = [tuple(r[c] for c in cols) for r in rows]
    with conn.cursor() as cur:
        cur.execute(SEARCH_PATH)
        result = execute_values(cur, sql, values, page_size=1000, fetch=True)
    conn.commit()
    return _count(result)


def _table_columns(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'dw' AND table_name = %s", (table,))
        return {r[0] for r in cur.fetchall()}


# ----------------------------------------------------------------- DDL
def create_schema(conn, ddl_path: Path) -> None:
    sql = Path(ddl_path).read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


# ---------------------------------------------------------- dimensões
def upsert_dim_tempo(conn, rows: list[dict]) -> dict:
    cols = ["sk_tempo", "data_completa", "ano", "trimestre", "mes", "nome_mes",
            "ano_mes", "dia", "dia_semana", "nome_dia_semana", "fim_de_semana"]
    return _upsert(conn, "dim_tempo", cols, "sk_tempo", rows)


def upsert_dim_jogo(conn, rows: list[dict]) -> dict:
    cols = ["nk_app_id", "nome_jogo", "desenvolvedora", "publisher",
            "genero_principal", "generos", "data_lancamento", "gratuito"]
    return _upsert(conn, "dim_jogo", cols, "nk_app_id", rows)


def upsert_dim_autor(conn, rows: list[dict]) -> dict:
    cols = ["nk_steamid", "num_jogos_possuidos", "faixa_jogos_possuidos",
            "num_reviews", "faixa_reviews_escritas"]
    return _upsert(conn, "dim_autor", cols, "nk_steamid", rows)


def upsert_dim_idioma(conn, rows: list[dict]) -> dict:
    return _upsert(conn, "dim_idioma", ["codigo_idioma", "nome_idioma"],
                   "codigo_idioma", rows)


# --------------------------------------------------------------- fato
FATO_STAGING_COLS = [
    "recommendation_id", "app_id", "steamid", "idioma", "data_criacao", "texto",
    "recomendou", "votos_util", "votos_engracado", "qtd_comentarios",
    "horas_na_review", "horas_total", "score_utilidade", "compra_steam",
    "recebeu_gratis", "early_access", "criado_em", "atualizado_em",
]

FATO_UPSERT_SQL = """
INSERT INTO fato_review (
    sk_tempo, sk_jogo, sk_autor, sk_idioma, nk_recommendation_id, texto_review,
    qtd_review, recomendou, votos_util, votos_engracado, qtd_comentarios,
    horas_jogadas_na_review, horas_jogadas_total, score_utilidade,
    compra_steam, recebeu_gratis, early_access, criado_em_ts, atualizado_em_ts
)
SELECT t.sk_tempo, j.sk_jogo, a.sk_autor, i.sk_idioma, s.recommendation_id, s.texto,
       1, s.recomendou, s.votos_util, s.votos_engracado, s.qtd_comentarios,
       s.horas_na_review, s.horas_total, s.score_utilidade,
       s.compra_steam, s.recebeu_gratis, s.early_access, s.criado_em, s.atualizado_em
FROM stg_review s
JOIN dim_tempo  t ON t.data_completa = s.data_criacao
JOIN dim_jogo   j ON j.nk_app_id     = s.app_id
JOIN dim_autor  a ON a.nk_steamid    = s.steamid
JOIN dim_idioma i ON i.codigo_idioma = s.idioma
ON CONFLICT (nk_recommendation_id) DO UPDATE SET
    sk_tempo = EXCLUDED.sk_tempo,
    sk_jogo = EXCLUDED.sk_jogo,
    sk_autor = EXCLUDED.sk_autor,
    sk_idioma = EXCLUDED.sk_idioma,
    texto_review = EXCLUDED.texto_review,
    recomendou = EXCLUDED.recomendou,
    votos_util = EXCLUDED.votos_util,
    votos_engracado = EXCLUDED.votos_engracado,
    qtd_comentarios = EXCLUDED.qtd_comentarios,
    horas_jogadas_na_review = EXCLUDED.horas_jogadas_na_review,
    horas_jogadas_total = EXCLUDED.horas_jogadas_total,
    score_utilidade = EXCLUDED.score_utilidade,
    compra_steam = EXCLUDED.compra_steam,
    recebeu_gratis = EXCLUDED.recebeu_gratis,
    early_access = EXCLUDED.early_access,
    criado_em_ts = EXCLUDED.criado_em_ts,
    atualizado_em_ts = EXCLUDED.atualizado_em_ts,
    carregado_em = now()
RETURNING (xmax = 0)
"""


def upsert_fato(conn, rows: list[dict]) -> dict:
    with conn.cursor() as cur:
        cur.execute(SEARCH_PATH)
        cur.execute("""
            CREATE TEMP TABLE stg_review (
                recommendation_id VARCHAR(32), app_id INTEGER, steamid VARCHAR(32),
                idioma VARCHAR(32), data_criacao DATE, texto TEXT, recomendou SMALLINT,
                votos_util INTEGER, votos_engracado INTEGER, qtd_comentarios INTEGER,
                horas_na_review NUMERIC(10,2), horas_total NUMERIC(10,2),
                score_utilidade NUMERIC(8,6), compra_steam BOOLEAN,
                recebeu_gratis BOOLEAN, early_access BOOLEAN,
                criado_em TIMESTAMP, atualizado_em TIMESTAMP
            ) ON COMMIT DROP""")
        execute_values(
            cur,
            f"INSERT INTO stg_review ({', '.join(FATO_STAGING_COLS)}) VALUES %s",
            [tuple(r[c] for c in FATO_STAGING_COLS) for r in rows],
            page_size=1000,
        )
        cur.execute(FATO_UPSERT_SQL)
        result = cur.fetchall()
    conn.commit()
    stats = _count(result)
    stats["sem_dimensao"] = len(rows) - len(result)
    return stats


# ---------------------------------------------------- auditoria/checks
def registrar_auditoria(conn, dag_id: str, run_id: str, ds: str, lidas: int,
                        inseridas: int, atualizadas: int, inicio, status: str,
                        detalhes: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(SEARCH_PATH)
        cur.execute("""
            INSERT INTO etl_auditoria (dag_id, run_id, ds, linhas_lidas, linhas_inseridas,
                                       linhas_atualizadas, inicio, fim, status, detalhes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now(), %s, %s)
            ON CONFLICT (dag_id, run_id) DO UPDATE SET
                ds = EXCLUDED.ds, linhas_lidas = EXCLUDED.linhas_lidas,
                linhas_inseridas = EXCLUDED.linhas_inseridas,
                linhas_atualizadas = EXCLUDED.linhas_atualizadas,
                inicio = EXCLUDED.inicio, fim = now(), status = EXCLUDED.status,
                detalhes = EXCLUDED.detalhes
        """, (dag_id, run_id, ds, lidas, inseridas, atualizadas, inicio, status,
              Json(detalhes, dumps=lambda o: json.dumps(o, default=str))))
    conn.commit()


def atualizar_status_auditoria(conn, dag_id: str, run_id: str, status: str,
                               extra: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(SEARCH_PATH)
        cur.execute("""
            UPDATE etl_auditoria
               SET status = %s, fim = now(),
                   detalhes = COALESCE(detalhes, '{}'::jsonb) || %s::jsonb
             WHERE dag_id = %s AND run_id = %s
        """, (status, json.dumps(extra, default=str), dag_id, run_id))
    conn.commit()


INTEGRITY_CHECKS = {
    "fk_orfa_tempo": "SELECT count(*) FROM fato_review f LEFT JOIN dim_tempo d "
                     "USING (sk_tempo) WHERE d.sk_tempo IS NULL",
    "fk_orfa_jogo": "SELECT count(*) FROM fato_review f LEFT JOIN dim_jogo d "
                    "USING (sk_jogo) WHERE d.sk_jogo IS NULL",
    "fk_orfa_autor": "SELECT count(*) FROM fato_review f LEFT JOIN dim_autor d "
                     "USING (sk_autor) WHERE d.sk_autor IS NULL",
    "fk_orfa_idioma": "SELECT count(*) FROM fato_review f LEFT JOIN dim_idioma d "
                      "USING (sk_idioma) WHERE d.sk_idioma IS NULL",
    "nk_duplicada_fato": "SELECT count(*) FROM (SELECT nk_recommendation_id FROM "
                         "fato_review GROUP BY 1 HAVING count(*) > 1) x",
    "qtd_review_diferente_de_1": "SELECT count(*) FROM fato_review WHERE qtd_review <> 1",
}


def validar_integridade(conn) -> dict:
    out = {}
    with conn.cursor() as cur:
        cur.execute(SEARCH_PATH)
        for nome, sql in INTEGRITY_CHECKS.items():
            cur.execute(sql)
            out[nome] = cur.fetchone()[0]
        cur.execute("SELECT count(*), sum(recomendou), sum(votos_util), "
                    "round(sum(horas_jogadas_na_review), 2) FROM fato_review")
        total, rec, votos, horas = cur.fetchone()
    out["resumo_fato"] = {"linhas": total, "soma_recomendou": rec,
                          "soma_votos_util": votos, "soma_horas_na_review": float(horas or 0)}
    return out

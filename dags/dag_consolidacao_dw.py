"""DAG 2 — Consolidação analítica: Raw -> limpeza -> Star Schema (Kimball).

Disparada pela DAG 1 (TriggerDagRunOperator) com ``conf={"ds": ...}``.
Também pode ser disparada manualmente; sem ``ds`` no conf, usa a partição
raw mais recente.

criar_schema >> ler_e_limpar_raw >> carregar_dim_tempo >> carregar_dim_jogo
  >> carregar_dim_autor >> carregar_dim_idioma >> carregar_fato
  >> registrar_auditoria >> validar_integridade

Idempotência: dimensões e fato usam UPSERT pela chave natural; rodar a mesma
partição duas vezes produz exatamente o mesmo conteúdo no DW.
"""
from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.providers.postgres.hooks.postgres import PostgresHook

import config

DAG_ID = "dag_consolidacao_dw"


def _conn():
    return PostgresHook(postgres_conn_id=config.DW_CONN_ID).get_conn()


def _resolve_ds(dag_run, ds) -> str:
    from ingestion.raw_storage import latest_partition
    conf_ds = (dag_run.conf or {}).get("ds") if dag_run else None
    if conf_ds:
        return conf_ds
    latest = latest_partition(config.RAW_REVIEWS_DIR)
    if latest is None:
        raise AirflowFailException("Nenhuma partição raw disponível. Rode a DAG 1 antes.")
    return latest


@dag(
    dag_id=DAG_ID,
    description="Limpeza, surrogate keys e carga idempotente no Star Schema",
    schedule=None,
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "t2-fucape", "retries": 1},
    tags=["t2", "dw", "kimball", "star-schema"],
)
def dag_consolidacao_dw():

    @task
    def criar_schema() -> None:
        from warehouse.loader import create_schema
        conn = _conn()
        try:
            create_schema(conn, config.DDL_PATH)
        finally:
            conn.close()

    @task
    def ler_e_limpar_raw(dag_run=None, ds=None) -> dict:
        from warehouse.loader import save_staging
        from warehouse.transform import read_and_clean_reviews
        part = _resolve_ds(dag_run, ds)
        rows, stats = read_and_clean_reviews(config.RAW_REVIEWS_DIR, part)
        path = config.STAGING_DIR / f"ingest_date={part}" / "reviews_clean.jsonl"
        save_staging(rows, path)
        datas = [r["data_criacao"] for r in rows]
        return {"ds_raw": part, "staging": str(path), **stats,
                "data_min": min(datas).isoformat(), "data_max": max(datas).isoformat(),
                "app_ids": sorted({r["app_id"] for r in rows})}

    @task
    def carregar_dim_tempo(info: dict) -> dict:
        from datetime import date
        from warehouse.loader import upsert_dim_tempo
        from warehouse.transform import build_dim_tempo
        rows = build_dim_tempo(date.fromisoformat(info["data_min"]),
                               date.fromisoformat(info["data_max"]))
        conn = _conn()
        try:
            return upsert_dim_tempo(conn, rows)
        finally:
            conn.close()

    @task
    def carregar_dim_jogo(info: dict) -> dict:
        import json
        from ingestion.raw_storage import latest_partition, partition_dir
        from warehouse.loader import upsert_dim_jogo
        from warehouse.transform import clean_appdetails
        rows = []
        for app_id in info["app_ids"]:
            # Prioriza a partição do mesmo dia; senão, a mais recente disponível.
            details = None
            for d in (info["ds_raw"], latest_partition(config.RAW_APPDETAILS_DIR)):
                if d is None:
                    continue
                f = partition_dir(config.RAW_APPDETAILS_DIR, d) / f"app_id={app_id}.json"
                if f.exists():
                    details = json.loads(f.read_text(encoding="utf-8"))
                    break
            rows.append(clean_appdetails(app_id, details))
        conn = _conn()
        try:
            return upsert_dim_jogo(conn, rows)
        finally:
            conn.close()

    @task
    def carregar_dim_autor(info: dict) -> dict:
        from warehouse.loader import load_staging, upsert_dim_autor
        from warehouse.transform import build_dim_autor
        conn = _conn()
        try:
            return upsert_dim_autor(conn, build_dim_autor(load_staging(info["staging"])))
        finally:
            conn.close()

    @task
    def carregar_dim_idioma(info: dict) -> dict:
        from warehouse.loader import load_staging, upsert_dim_idioma
        from warehouse.transform import build_dim_idioma
        conn = _conn()
        try:
            return upsert_dim_idioma(conn, build_dim_idioma(load_staging(info["staging"])))
        finally:
            conn.close()

    @task
    def carregar_fato(info: dict) -> dict:
        from warehouse.loader import load_staging, upsert_fato
        conn = _conn()
        try:
            stats = upsert_fato(conn, load_staging(info["staging"]))
        finally:
            conn.close()
        if stats["sem_dimensao"]:
            raise AirflowFailException(
                f"{stats['sem_dimensao']} linhas sem correspondência nas dimensões")
        return stats

    @task
    def registrar_auditoria(info: dict, dims: list[dict], fato: dict,
                            run_id=None, dag_run=None) -> None:
        from warehouse.loader import registrar_auditoria as _reg
        conn = _conn()
        try:
            _reg(conn, DAG_ID, run_id, info["ds_raw"], lidas=info["linhas_lidas"],
                 inseridas=fato["inseridas"], atualizadas=fato["atualizadas"],
                 inicio=dag_run.start_date, status="loaded",
                 detalhes={"limpeza": {k: info[k] for k in
                                       ("invalidas", "duplicadas_removidas", "linhas_limpas")},
                           "dimensoes": dict(zip(
                               ["dim_tempo", "dim_jogo", "dim_autor", "dim_idioma"], dims))})
        finally:
            conn.close()

    @task
    def validar_integridade(run_id=None) -> dict:
        from warehouse.loader import atualizar_status_auditoria, validar_integridade as _val
        conn = _conn()
        try:
            res = _val(conn)
            problemas = {k: v for k, v in res.items() if k != "resumo_fato" and v}
            status = "integrity_failed" if problemas else "success"
            atualizar_status_auditoria(conn, DAG_ID, run_id, status, {"integridade": res})
        finally:
            conn.close()
        if problemas:
            raise AirflowFailException(f"Falha de integridade: {problemas}")
        return res

    schema = criar_schema()
    info = ler_e_limpar_raw()
    d_tempo = carregar_dim_tempo(info)
    d_jogo = carregar_dim_jogo(info)
    d_autor = carregar_dim_autor(info)
    d_idioma = carregar_dim_idioma(info)
    fato = carregar_fato(info)
    audit = registrar_auditoria(info, [d_tempo, d_jogo, d_autor, d_idioma], fato)
    valid = validar_integridade()

    schema >> info >> d_tempo >> d_jogo >> d_autor >> d_idioma >> fato >> audit >> valid


dag_consolidacao_dw()

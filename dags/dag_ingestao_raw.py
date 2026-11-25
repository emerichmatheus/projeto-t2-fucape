"""DAG 1 — Ingestão resiliente das reviews da Steam para a camada Raw/Bronze.

Fluxo:
    coletar_reviews (1 task mapeada por jogo, .expand)  ┐
    coletar_appdetails                                  ├─> registrar_auditoria_ingestao
                                                        ┘      └─> disparar_consolidacao_dw

* Resiliência: cliente HTTP com backoff exponencial + jitter (src/ingestion),
  além de retries=3 com retry_exponential_backoff no nível da task.
* Idempotência: cada execução sobrescreve a partição ``ingest_date={{ ds }}``
  com escrita atômica (arquivo temporário + rename).
* Encadeamento: TriggerDagRunOperator dispara a DAG 2 passando o ``ds``.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

import config

DEFAULT_ARGS = {
    "owner": "t2-fucape",
    "retries": 3,
    "retry_delay": timedelta(seconds=30),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
}


@dag(
    dag_id="dag_ingestao_raw",
    description="Coleta reviews e metadados da Steam (Raw/Bronze, JSONL particionado)",
    schedule="@daily",
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["t2", "ingestao", "raw", "steam"],
)
def dag_ingestao_raw():

    @task(max_active_tis_per_dagrun=2)
    def coletar_reviews(app_id: int, ds=None) -> dict:
        from ingestion.pipeline import ingest_reviews
        return ingest_reviews(app_id, ds)

    @task
    def coletar_appdetails(ds=None) -> dict:
        from ingestion.pipeline import ingest_appdetails
        return ingest_appdetails(config.STEAM_APP_IDS, ds)

    @task
    def registrar_auditoria_ingestao(metas: list[dict], details: dict, ds=None,
                                     run_id=None, dag_run=None) -> dict:
        from warehouse.loader import create_schema, registrar_auditoria
        metas = list(metas)
        total = sum(m["reviews_written"] for m in metas)
        conn = PostgresHook(postgres_conn_id=config.DW_CONN_ID).get_conn()
        try:
            create_schema(conn, config.DDL_PATH)
            registrar_auditoria(
                conn, "dag_ingestao_raw", run_id, ds, lidas=total, inseridas=total,
                atualizadas=0, inicio=dag_run.start_date, status="success",
                detalhes={"por_jogo": {m["app_id"]: m["reviews_written"] for m in metas},
                          "retries_http": sum(m["retries"] for m in metas)
                          + details.get("retries", 0),
                          "appdetails_falhas": details.get("failed", [])},
            )
        finally:
            conn.close()
        return {"reviews_gravadas": total}

    metas = coletar_reviews.expand(app_id=config.STEAM_APP_IDS)
    details = coletar_appdetails()
    auditoria = registrar_auditoria_ingestao(metas, details)

    disparar = TriggerDagRunOperator(
        task_id="disparar_consolidacao_dw",
        trigger_dag_id="dag_consolidacao_dw",
        conf={"ds": "{{ ds }}", "origem_run_id": "{{ run_id }}"},
        wait_for_completion=False,
    )
    auditoria >> disparar


dag_ingestao_raw()

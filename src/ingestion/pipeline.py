"""Funções de ingestão chamadas pela DAG 1 (independentes do Airflow)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import config
from ingestion.raw_storage import partition_dir, write_json_atomic, write_jsonl_atomic
from ingestion.steam_client import SteamClient

log = logging.getLogger(__name__)


def build_client() -> SteamClient:
    return SteamClient(
        polite_pause=config.STEAM_POLITE_PAUSE,
        simulate_429_rate=config.STEAM_SIMULATE_429_RATE,
    )


def ingest_reviews(app_id: int, ingest_date: str, max_pages: int | None = None) -> dict:
    """Coleta as reviews de um jogo e grava a partição raw do dia."""
    client = build_client()
    ingested_at = datetime.now(timezone.utc).isoformat()
    by_id: dict[str, dict] = {}
    summary: dict = {}
    pages = 0
    for page in client.iter_review_pages(
        app_id, config.STEAM_LANGUAGE, max_pages or config.STEAM_MAX_PAGES
    ):
        pages += 1
        if page.get("_page") == 1:
            summary = page.get("query_summary", {})
        for review in page["reviews"]:
            review["app_id"] = app_id
            review["_ingested_at"] = ingested_at
            # Deduplicação dentro da execução pela chave natural.
            by_id[str(review["recommendationid"])] = review

    out_dir = partition_dir(config.RAW_REVIEWS_DIR, ingest_date)
    n = write_jsonl_atomic(out_dir / f"app_id={app_id}.jsonl", by_id.values())
    meta = {
        "app_id": app_id, "ingest_date": ingest_date, "ingested_at": ingested_at,
        "pages": pages, "reviews_written": n, "retries": client.retry_count,
        "query_summary": summary,
    }
    write_json_atomic(out_dir / f"_meta_app_id={app_id}.json", meta)
    log.info("app_id=%s: %d reviews únicas gravadas em %d páginas (%d retries).",
             app_id, n, pages, client.retry_count)
    return meta


def ingest_appdetails(app_ids: list[int], ingest_date: str) -> dict:
    """Coleta os metadados dos jogos (um arquivo JSON por jogo)."""
    client = build_client()
    out_dir = partition_dir(config.RAW_APPDETAILS_DIR, ingest_date)
    ok, failed = [], []
    for app_id in app_ids:
        details = client.get_app_details(app_id)
        if details is None:
            failed.append(app_id)
            continue
        details["_ingested_at"] = datetime.now(timezone.utc).isoformat()
        write_json_atomic(out_dir / f"app_id={app_id}.json", details)
        ok.append(app_id)
    return {"ok": ok, "failed": failed, "retries": client.retry_count}

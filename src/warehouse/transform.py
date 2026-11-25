"""Limpeza e transformação dos dados brutos (Raw -> registros tipados).

Funções puras, sem dependência de banco, para facilitar testes.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ingestion.raw_storage import partition_dir, read_jsonl

_WS = re.compile(r"\s+")

NOMES_MES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
             "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
NOMES_DIA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
             "Sexta-feira", "Sábado", "Domingo"]

IDIOMAS = {
    "brazilian": "Português (Brasil)", "portuguese": "Português (Portugal)",
    "english": "Inglês", "spanish": "Espanhol", "latam": "Espanhol (América Latina)",
    "french": "Francês", "german": "Alemão", "italian": "Italiano",
    "russian": "Russo", "schinese": "Chinês Simplificado",
    "tchinese": "Chinês Tradicional", "japanese": "Japonês", "koreana": "Coreano",
}

MESES_PT_BR = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
               "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
MESES_EN = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


# ---------------------------------------------------------------- helpers
def _ts(value) -> datetime | None:
    if value in (None, "", 0):
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(tzinfo=None)


def _hours(minutes) -> float | None:
    return None if minutes is None else round(int(minutes) / 60.0, 2)


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_text(text: str | None) -> str:
    return _WS.sub(" ", text or "").strip()


def faixa(valor: int | None, cortes: list[tuple[int, str]], maior: str) -> str:
    if valor is None:
        return "Não informado"
    for limite, rotulo in cortes:
        if valor <= limite:
            return rotulo
    return maior


def faixa_jogos(n: int | None) -> str:
    return faixa(n, [(10, "0-10"), (50, "11-50"), (200, "51-200")], "200+")


def faixa_reviews(n: int | None) -> str:
    return faixa(n, [(1, "1"), (5, "2-5"), (20, "6-20"), (100, "21-100")], "100+")


def parse_release_date(text: str | None) -> date | None:
    """Converte '21 ago. 2012', '26 fev. 2016' ou 'Aug 21, 2012' em date."""
    if not text:
        return None
    t = text.lower().replace(".", " ").replace(",", " ").replace(" de ", " ")
    parts = t.split()
    nums = [p for p in parts if p.isdigit()]
    words = [p[:3] for p in parts if p.isalpha()]
    if len(nums) < 2 or not words:
        return None
    month = MESES_PT_BR.get(words[0]) or MESES_EN.get(words[0])
    day, year = int(nums[0]), int(nums[-1])
    if not month or year < 1970:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


# ---------------------------------------------------------------- reviews
def clean_review(raw: dict) -> dict | None:
    """Desaninha e tipa uma review bruta. Retorna None se for inválida."""
    texto = normalize_text(raw.get("review"))
    rec_id = raw.get("recommendationid")
    author = raw.get("author") or {}
    created = _ts(raw.get("timestamp_created"))
    if not texto or not rec_id or not author.get("steamid") or created is None:
        return None
    num_jogos = author.get("num_games_owned")
    num_reviews = author.get("num_reviews")
    return {
        "recommendation_id": str(rec_id),
        "app_id": int(raw["app_id"]),
        "steamid": str(author["steamid"]),
        "num_jogos_possuidos": None if num_jogos is None else _int(num_jogos),
        "num_reviews": None if num_reviews is None else _int(num_reviews),
        "idioma": raw.get("language") or "desconhecido",
        "texto": texto,
        "criado_em": created,
        "data_criacao": created.date(),
        "atualizado_em": _ts(raw.get("timestamp_updated")) or created,
        "recomendou": 1 if raw.get("voted_up") else 0,
        "votos_util": _int(raw.get("votes_up")),
        "votos_engracado": _int(raw.get("votes_funny")),
        "qtd_comentarios": _int(raw.get("comment_count")),
        "horas_na_review": _hours(author.get("playtime_at_review")),
        "horas_total": _hours(author.get("playtime_forever")),
        "score_utilidade": float(raw.get("weighted_vote_score") or 0),
        "compra_steam": bool(raw.get("steam_purchase")),
        "recebeu_gratis": bool(raw.get("received_for_free")),
        "early_access": bool(raw.get("written_during_early_access")),
    }


def dedupe_latest(rows: list[dict]) -> list[dict]:
    """Mantém uma linha por recommendation_id (a de atualizado_em mais recente)."""
    best: dict[str, dict] = {}
    for r in rows:
        cur = best.get(r["recommendation_id"])
        if cur is None or r["atualizado_em"] >= cur["atualizado_em"]:
            best[r["recommendation_id"]] = r
    return list(best.values())


def read_and_clean_reviews(raw_reviews_dir: Path, ingest_date: str) -> tuple[list[dict], dict]:
    part = partition_dir(raw_reviews_dir, ingest_date)
    files = sorted(part.glob("app_id=*.jsonl"))
    if not files:
        raise FileNotFoundError(f"Nenhum arquivo raw em {part}")
    lidas, invalidas, cleaned = 0, 0, []
    for f in files:
        for raw in read_jsonl(f):
            lidas += 1
            row = clean_review(raw)
            if row is None:
                invalidas += 1
            else:
                cleaned.append(row)
    final = dedupe_latest(cleaned)
    stats = {
        "arquivos": len(files), "linhas_lidas": lidas, "invalidas": invalidas,
        "duplicadas_removidas": len(cleaned) - len(final), "linhas_limpas": len(final),
    }
    return final, stats


# ------------------------------------------------------------- dimensões
def build_dim_tempo(start: date, end: date) -> list[dict]:
    rows, d = [], start
    while d <= end:
        rows.append({
            "sk_tempo": int(d.strftime("%Y%m%d")),
            "data_completa": d,
            "ano": d.year,
            "trimestre": (d.month - 1) // 3 + 1,
            "mes": d.month,
            "nome_mes": NOMES_MES[d.month - 1],
            "ano_mes": d.strftime("%Y-%m"),
            "dia": d.day,
            "dia_semana": d.isoweekday(),
            "nome_dia_semana": NOMES_DIA[d.weekday()],
            "fim_de_semana": d.weekday() >= 5,
        })
        d += timedelta(days=1)
    return rows


def clean_appdetails(app_id: int, details: dict | None) -> dict:
    if not details:
        return {"nk_app_id": app_id, "nome_jogo": f"Desconhecido ({app_id})",
                "desenvolvedora": None, "publisher": None, "genero_principal": None,
                "generos": None, "data_lancamento": None, "gratuito": None}
    genres = [g.get("description") for g in details.get("genres") or [] if g.get("description")]
    devs = details.get("developers") or []
    pubs = details.get("publishers") or []
    return {
        "nk_app_id": app_id,
        "nome_jogo": normalize_text(details.get("name")) or f"App {app_id}",
        "desenvolvedora": ", ".join(devs)[:255] or None,
        "publisher": ", ".join(pubs)[:255] or None,
        "genero_principal": genres[0] if genres else None,
        "generos": ", ".join(genres)[:500] or None,
        "data_lancamento": parse_release_date((details.get("release_date") or {}).get("date")),
        "gratuito": bool(details.get("is_free")),
    }


def build_dim_autor(rows: list[dict]) -> list[dict]:
    autores: dict[str, dict] = {}
    for r in sorted(rows, key=lambda x: x["atualizado_em"]):
        autores[r["steamid"]] = {
            "nk_steamid": r["steamid"],
            "num_jogos_possuidos": r["num_jogos_possuidos"],
            "faixa_jogos_possuidos": faixa_jogos(r["num_jogos_possuidos"]),
            "num_reviews": r["num_reviews"],
            "faixa_reviews_escritas": faixa_reviews(r["num_reviews"]),
        }
    return list(autores.values())


def build_dim_idioma(rows: list[dict]) -> list[dict]:
    codes = sorted({r["idioma"] for r in rows})
    return [{"codigo_idioma": c, "nome_idioma": IDIOMAS.get(c, c.title())} for c in codes]

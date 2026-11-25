from datetime import date

from warehouse.transform import (build_dim_tempo, clean_review, dedupe_latest,
                                 faixa_jogos, parse_release_date)

RAW = {
    "recommendationid": "123", "app_id": 730,
    "author": {"steamid": "765", "num_reviews": 3, "playtime_forever": 600,
               "playtime_at_review": 90},
    "language": "brazilian", "review": "  Jogo   travando  \n muito ",
    "timestamp_created": 1700000000, "timestamp_updated": 1700000500,
    "voted_up": True, "votes_up": 4, "votes_funny": 1, "weighted_vote_score": "0.6",
    "comment_count": 0, "steam_purchase": True, "received_for_free": False,
    "written_during_early_access": False,
}


def test_clean_review_unnests_and_types():
    r = clean_review(RAW)
    assert r["steamid"] == "765" and r["recomendou"] == 1
    assert r["horas_total"] == 10.0 and r["horas_na_review"] == 1.5
    assert r["texto"] == "Jogo travando muito"
    assert r["data_criacao"] == date(2023, 11, 14)
    assert r["score_utilidade"] == 0.6


def test_clean_review_rejects_empty_text():
    assert clean_review({**RAW, "review": "   "}) is None


def test_dedupe_keeps_latest_update():
    a = clean_review(RAW)
    b = clean_review({**RAW, "timestamp_updated": 1700009999, "voted_up": False})
    out = dedupe_latest([a, b])
    assert len(out) == 1 and out[0]["recomendou"] == 0


def test_dim_tempo_calendar():
    rows = build_dim_tempo(date(2026, 11, 28), date(2026, 12, 1))
    assert [r["sk_tempo"] for r in rows] == [20261128, 20261129, 20261130, 20261201]
    assert rows[0]["fim_de_semana"] and rows[0]["nome_dia_semana"] == "Sábado"
    assert rows[-1]["trimestre"] == 4 and rows[-1]["nome_mes"] == "Dezembro"


def test_faixas_and_release_date():
    assert faixa_jogos(None) == "Não informado"
    assert faixa_jogos(10) == "0-10" and faixa_jogos(201) == "200+"
    assert parse_release_date("21 ago. 2012") == date(2012, 8, 21)
    assert parse_release_date("Aug 21, 2012") == date(2012, 8, 21)
    assert parse_release_date("4/nov./2020") == date(2020, 11, 4)
    assert parse_release_date("Em breve") is None

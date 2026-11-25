"""Leitura do corpus (texto_review da fato_review) direto do Data Warehouse."""
from __future__ import annotations

CORPUS_SQL = """
SELECT f.sk_fato, f.nk_recommendation_id, f.texto_review AS texto,
       j.nome_jogo, t.data_completa, f.recomendou, f.votos_util
FROM dw.fato_review f
JOIN dw.dim_jogo  j ON j.sk_jogo  = f.sk_jogo
JOIN dw.dim_tempo t ON t.sk_tempo = f.sk_tempo
ORDER BY f.sk_fato
"""


def load_corpus(engine) -> list[dict]:
    """``engine``: SQLAlchemy Engine conectado ao DW."""
    from sqlalchemy import text
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(CORPUS_SQL))]

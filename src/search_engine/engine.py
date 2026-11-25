"""Fachada do mecanismo de busca: corpus -> índices -> correção -> BM25."""
from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass

from search_engine.baseline import BruteForceCorrector, QueryCorrection
from search_engine.bm25 import BM25Index
from search_engine.optimized import KGramCorrector
from search_engine.preprocess import strip_accents, tokenize

METHODS = ("baseline", "otimizado")


@dataclass
class SearchResult:
    query: str
    method: str
    correction: QueryCorrection
    hits: list[dict]
    ms_correcao: float
    ms_ranking: float

    @property
    def ms_total(self) -> float:
        return self.ms_correcao + self.ms_ranking

    @property
    def suggestion(self) -> str | None:
        return " ".join(self.correction.corrected_terms) if self.correction.changed else None


class SearchEngine:
    """Monta o vocabulário, os dois corretores e o índice BM25 sobre o corpus.

    ``docs``: lista de dicts com ao menos a chave ``texto``.
    O "dicionário" de correção são os termos com frequência >= ``min_freq``
    (termos raros costumam ser os próprios erros de digitação).
    """

    def __init__(self, docs: list[dict], min_freq: int = 5, max_term_len: int = 25,
                 k: int = 3, jaccard_threshold: float = 0.2, max_dist: int = 2) -> None:
        self.docs = docs
        tokenized = [tokenize(d["texto"]) for d in docs]
        self.term_freq = Counter(t for toks in tokenized for t in toks)
        self.dictionary = {
            t: f for t, f in self.term_freq.items()
            if f >= min_freq and len(t) <= max_term_len and not t.isdigit()
        }
        self.bm25 = BM25Index(tokenized)
        self.baseline = BruteForceCorrector(self.dictionary, max_dist=max_dist)
        self.optimized = KGramCorrector(self.dictionary, k=k,
                                        jaccard_threshold=jaccard_threshold,
                                        max_dist=max_dist)

    def corrector(self, method: str):
        return self.baseline if method == "baseline" else self.optimized

    def correct(self, query: str, method: str) -> tuple[QueryCorrection, float]:
        terms = tokenize(query)
        t0 = time.perf_counter()
        corr = self.corrector(method).correct(terms)
        return corr, (time.perf_counter() - t0) * 1000

    def search(self, query: str, method: str = "otimizado", k: int = 10) -> SearchResult:
        corr, ms_corr = self.correct(query, method)
        t0 = time.perf_counter()
        ranked = self.bm25.search(corr.corrected_terms, k=k)
        ms_rank = (time.perf_counter() - t0) * 1000
        hits = [{**self.docs[doc_id], "score": round(score, 4)} for doc_id, score in ranked]
        return SearchResult(query, method, corr, hits, ms_corr, ms_rank)

    def autocomplete(self, prefix: str, limit: int = 8) -> list[tuple[str, int]]:
        prefix = strip_accents(prefix.lower().strip())
        return self.optimized.autocomplete(prefix, limit) if prefix else []


def highlight(text: str, terms: list[str], width: int = 280) -> str:
    """Trecho do texto com os termos da consulta em **negrito** (Markdown)."""
    plain = strip_accents(text.lower())
    pos = min((plain.find(t) for t in terms if plain.find(t) >= 0), default=0)
    start = max(0, pos - width // 3)
    snippet = text[start:start + width]
    snippet_plain = plain[start:start + width]
    spans = []
    for t in terms:
        for m in re.finditer(re.escape(t), snippet_plain):
            spans.append((m.start(), m.end()))
    out, last = [], 0
    for s, e in sorted(spans):
        if s < last:
            continue
        out.append(snippet[last:s].replace("*", ""))
        out.append(f"**{snippet[s:e]}**")
        last = e
    out.append(snippet[last:].replace("*", ""))
    return ("…" if start else "") + "".join(out) + ("…" if start + width < len(text) else "")

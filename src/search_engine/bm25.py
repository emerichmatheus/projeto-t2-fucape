"""Índice invertido + ranqueamento BM25 (Okapi).

score(D, Q) = Σ_t IDF(t) · tf(t,D)·(k1+1) / (tf(t,D) + k1·(1 − b + b·|D|/avgdl))
IDF(t)      = ln(1 + (N − df + 0.5) / (df + 0.5))
"""
from __future__ import annotations

import heapq
import math
from collections import Counter, defaultdict


class BM25Index:
    def __init__(self, tokenized_docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.N = len(tokenized_docs)
        self.doc_len = [len(d) for d in tokenized_docs]
        self.avgdl = (sum(self.doc_len) / self.N) if self.N else 0.0
        postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for doc_id, tokens in enumerate(tokenized_docs):
            for term, tf in Counter(tokens).items():
                postings[term].append((doc_id, tf))
        self.postings = dict(postings)
        self.idf = {
            t: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5))
            for t, p in self.postings.items()
        }

    def score(self, terms: list[str]) -> dict[int, float]:
        scores: dict[int, float] = defaultdict(float)
        k1, b, avgdl, dl = self.k1, self.b, self.avgdl, self.doc_len
        for term in terms:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for doc_id, tf in self.postings[term]:
                norm = k1 * (1 - b + b * dl[doc_id] / avgdl)
                scores[doc_id] += idf * tf * (k1 + 1) / (tf + norm)
        return scores

    def search(self, terms: list[str], k: int = 10) -> list[tuple[int, float]]:
        scores = self.score(terms)
        return heapq.nlargest(k, scores.items(), key=lambda x: x[1])

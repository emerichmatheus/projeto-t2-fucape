"""Índice secundário de k-gramas de caracteres + coeficiente de Jaccard.

Cada termo do vocabulário é decomposto em k-gramas com marcadores ``$`` de
início e fim (ex.: k=2, "bug" -> {$b, bu, ug, g$}). O índice mapeia cada
k-grama para a lista de termos que o contêm. Para uma consulta, somamos
quantos k-gramas cada termo tem em comum (merge das listas de postagem) e
calculamos  J(A, B) = |A ∩ B| / |A ∪ B| = inter / (|A| + |B| - inter).
"""
from __future__ import annotations

from collections import defaultdict


def kgrams(term: str, k: int = 2) -> set[str]:
    padded = f"${term}$"
    if len(padded) < k:
        return {padded}
    return {padded[i:i + k] for i in range(len(padded) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


class KGramIndex:
    def __init__(self, vocabulary, k: int = 2) -> None:
        self.k = k
        self.terms: list[str] = list(vocabulary)
        self.lengths: list[int] = [len(t) for t in self.terms]
        self.gram_counts: list[int] = []
        postings: dict[str, list[int]] = defaultdict(list)
        for tid, term in enumerate(self.terms):
            grams = kgrams(term, k)
            self.gram_counts.append(len(grams))
            for g in grams:
                postings[g].append(tid)
        self.postings = dict(postings)

    def candidates(self, term: str, threshold: float = 0.3,
                   max_len_diff: int | None = 2) -> list[tuple[str, float]]:
        """Termos com Jaccard >= threshold (e diferença de tamanho <= max_len_diff)."""
        q = kgrams(term, self.k)
        qn, qlen = len(q), len(term)
        overlap: dict[int, int] = defaultdict(int)
        for g in q:
            for tid in self.postings.get(g, ()):
                overlap[tid] += 1
        out = []
        lengths, counts, terms = self.lengths, self.gram_counts, self.terms
        for tid, inter in overlap.items():
            if max_len_diff is not None and abs(lengths[tid] - qlen) > max_len_diff:
                continue
            j = inter / (qn + counts[tid] - inter)
            if j >= threshold:
                out.append((terms[tid], j))
        return out

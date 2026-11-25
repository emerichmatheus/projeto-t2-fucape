"""BASELINE (Antes): correção ortográfica por Levenshtein em força-bruta.

Para cada termo da consulta que não está no dicionário, calcula a distância
de edição completa (DP) contra TODO o vocabulário e escolhe o termo mais
próximo. Desempate: maior frequência no corpus. Custo: O(|V| · |q| · |t|).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from search_engine.levenshtein import levenshtein


@dataclass
class Correction:
    original: str
    corrected: str
    distance: int
    comparisons: int        # nº de cálculos de Levenshtein feitos
    candidates: int = 0     # nº de candidatos avaliados (otimizado)

    @property
    def changed(self) -> bool:
        return self.original != self.corrected


@dataclass
class QueryCorrection:
    terms: list[Correction] = field(default_factory=list)

    @property
    def corrected_terms(self) -> list[str]:
        return [c.corrected for c in self.terms]

    @property
    def comparisons(self) -> int:
        return sum(c.comparisons for c in self.terms)

    @property
    def changed(self) -> bool:
        return any(c.changed for c in self.terms)


def pick_best(original: str, scored, freq: dict[str, int], max_dist: int) -> tuple[str, int]:
    """Menor distância; empate -> mais frequente; empate -> ordem alfabética."""
    best_term, best_key = original, None
    for term, dist in scored:
        if dist > max_dist:
            continue
        key = (dist, -freq[term], term)
        if best_key is None or key < best_key:
            best_term, best_key = term, key
    return best_term, (best_key[0] if best_key else max_dist + 1)


class BruteForceCorrector:
    name = "Baseline (Levenshtein força-bruta)"

    def __init__(self, dictionary: dict[str, int], max_dist: int = 2) -> None:
        self.freq = dictionary
        self.vocab = list(dictionary)
        self.max_dist = max_dist

    def correct_term(self, term: str) -> Correction:
        if term in self.freq:
            return Correction(term, term, 0, 0)
        scored = [(t, levenshtein(term, t)) for t in self.vocab]
        best, dist = pick_best(term, scored, self.freq, self.max_dist)
        return Correction(term, best, dist, len(self.vocab), len(self.vocab))

    def correct(self, terms: list[str]) -> QueryCorrection:
        return QueryCorrection([self.correct_term(t) for t in terms])

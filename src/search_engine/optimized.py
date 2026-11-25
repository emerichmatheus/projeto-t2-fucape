"""OTIMIZADO (Depois): correção ortográfica tolerante a falhas em 2 estágios.

Estágio 1 — triagem barata: índice secundário de k-gramas de caracteres.
    Só termos que compartilham k-gramas com a consulta são tocados; ficam
    os que têm Jaccard >= limiar e diferença de comprimento <= max_dist
    (Levenshtein >= |len(a) - len(b)|, logo os demais nunca venceriam).
Estágio 2 — refinamento: Levenshtein (mesma DP, com corte antecipado em
    ``max_dist``) APENAS nos candidatos pré-selecionados.

A Trie serve ao autocompletar da caixa de busca (sugestões em O(|P|)).
"""
from __future__ import annotations

from search_engine.baseline import Correction, QueryCorrection, pick_best
from search_engine.kgram import KGramIndex
from search_engine.levenshtein import levenshtein_bounded
from search_engine.trie import Trie


class KGramCorrector:
    name = "Otimizado (k-gramas + Jaccard + Levenshtein)"

    def __init__(self, dictionary: dict[str, int], k: int = 3,
                 jaccard_threshold: float = 0.2, max_dist: int = 2) -> None:
        self.freq = dictionary
        self.max_dist = max_dist
        self.threshold = jaccard_threshold
        self.vocab_size = len(dictionary)
        self.index = KGramIndex(dictionary.keys(), k=k)
        self.trie = Trie()
        for term, f in dictionary.items():
            self.trie.insert(term, f)
        self.trie.build_top()

    def correct_term(self, term: str) -> Correction:
        if term in self.freq:
            return Correction(term, term, 0, 0)
        cands = self.index.candidates(term, self.threshold, max_len_diff=self.max_dist)
        scored = [(t, levenshtein_bounded(term, t, self.max_dist)) for t, _ in cands]
        best, dist = pick_best(term, scored, self.freq, self.max_dist)
        return Correction(term, best, dist, len(cands), len(cands))

    def correct(self, terms: list[str]) -> QueryCorrection:
        return QueryCorrection([self.correct_term(t) for t in terms])

    def autocomplete(self, prefix: str, limit: int = 8) -> list[tuple[str, int]]:
        return self.trie.autocomplete(prefix, limit)

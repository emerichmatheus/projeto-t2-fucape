import math

import pytest

from search_engine.baseline import BruteForceCorrector
from search_engine.bm25 import BM25Index
from search_engine.engine import SearchEngine
from search_engine.kgram import KGramIndex, jaccard, kgrams
from search_engine.levenshtein import levenshtein, levenshtein_bounded
from search_engine.optimized import KGramCorrector
from search_engine.preprocess import tokenize
from search_engine.trie import Trie


# ------------------------------------------------------------ Levenshtein
@pytest.mark.parametrize("a,b,d", [
    ("", "", 0), ("abc", "", 3), ("", "ab", 2), ("kitten", "sitting", 3),
    ("flaw", "lawn", 2), ("travano", "travando", 1), ("servidro", "servidor", 2),
    ("otimizasao", "otimizacao", 1), ("igual", "igual", 0),
])
def test_levenshtein(a, b, d):
    assert levenshtein(a, b) == d
    assert levenshtein(b, a) == d


def test_levenshtein_bounded_matches_full_inside_limit():
    pairs = [("kitten", "sitting"), ("hackr", "hacker"), ("lag", "lagado"), ("abc", "xyz")]
    for a, b in pairs:
        full = levenshtein(a, b)
        bounded = levenshtein_bounded(a, b, 2)
        assert bounded == (full if full <= 2 else 3)


# ---------------------------------------------------------------- Jaccard
def test_kgrams_with_markers():
    assert kgrams("bug", 2) == {"$b", "bu", "ug", "g$"}
    assert kgrams("bug", 3) == {"$bu", "bug", "ug$"}


def test_jaccard():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert jaccard({"a"}, {"b"}) == 0.0
    assert math.isclose(jaccard({"a", "b", "c"}, {"b", "c", "d"}), 2 / 4)


def test_kgram_index_candidates():
    idx = KGramIndex(["travando", "trava", "servidor", "bug"], k=2)
    cands = dict(idx.candidates("travano", threshold=0.3))
    assert "travando" in cands
    assert "bug" not in cands


# ------------------------------------------------------------------- Trie
def test_trie_autocomplete_by_frequency():
    t = Trie(top_k=3)
    for w, f in [("lag", 50), ("lagando", 10), ("lagado", 5), ("lanterna", 1), ("bug", 99)]:
        t.insert(w, f)
    t.build_top()
    assert [w for w, _ in t.autocomplete("lag")] == ["lag", "lagando", "lagado"]
    assert t.autocomplete("xyz") == []
    assert t.contains("bug") and not t.contains("bu")


# ------------------------------------------------------------------- BM25
def test_bm25_ranks_relevant_doc_first():
    docs = [["jogo", "bom"], ["servidor", "ruim", "servidor", "lag"], ["grafico", "bonito"]]
    idx = BM25Index(docs)
    top = idx.search(["servidor"], k=3)
    assert top[0][0] == 1 and len(top) == 1
    assert idx.idf["servidor"] > 0


def test_bm25_length_normalization():
    docs = [["bug"], ["bug"] + ["outro"] * 20]
    top = BM25Index(docs).search(["bug"], k=2)
    assert top[0][0] == 0


# ------------------------------------------------------------- corretores
DICT = {"travando": 40, "trava": 30, "servidor": 25, "otimizacao": 20,
        "hacker": 15, "multiplayer": 12, "lagando": 9, "grafico": 8}


@pytest.mark.parametrize("wrong,right", [
    ("travano", "travando"), ("servidro", "servidor"), ("otimizasao", "otimizacao"),
    ("hackr", "hacker"), ("multiplayr", "multiplayer"),
])
def test_baseline_and_optimized_agree(wrong, right):
    base = BruteForceCorrector(DICT).correct_term(wrong)
    opt = KGramCorrector(DICT).correct_term(wrong)
    assert base.corrected == opt.corrected == right
    assert opt.comparisons <= base.comparisons == len(DICT)


def test_known_term_is_kept():
    assert KGramCorrector(DICT).correct_term("trava").corrected == "trava"


def test_tokenize_removes_accents_and_stopwords():
    assert tokenize("A otimização está PÉSSIMA, não dá!") == ["otimizacao", "pessima"]


def test_engine_end_to_end():
    docs = [{"texto": t} for t in [
        "o jogo fica travando toda hora", "servidor caindo direto", "otimização horrível",
        "travando muito no multiplayer", "servidor bom", "travando depois da atualização",
        "otimização ruim", "otimização boa", "servidor lento",
    ]]
    eng = SearchEngine(docs, min_freq=2)
    res = eng.search("travano", method="otimizado")
    assert res.suggestion == "travando"
    assert res.hits and "travando" in res.hits[0]["texto"]

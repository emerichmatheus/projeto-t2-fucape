"""Pré-processamento textual comum ao baseline e à versão otimizada."""
from __future__ import annotations

import re
import unicodedata

TOKEN_RE = re.compile(r"[a-z0-9]+")

# Lista própria de stopwords do português (sem depender de download do NLTK).
STOPWORDS = frozenset("""
a ao aos aquela aquelas aquele aqueles aquilo as ate com como da das de dela delas
dele deles depois do dos e ela elas ele eles em entre era eram essa essas esse
esses esta estao estas estava estavam este estes eu foi fomos for foram fosse
ha isso isto ja la lhe lhes mais mas me mesmo meu meus minha minhas muito na nas
nem no nos nossa nossas nosso nossos num numa o os ou para pela pelas pelo pelos
por qual quando que quem se sem ser seu seus so sua suas tambem te tem tinha
tu tua tuas um uma umas uns voce voces vos pra pro pq q eh ta to tô vc vcs
nao sim ai ate entao porque cada ainda bem sobre aqui
""".split())


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    """minúsculas -> sem acento -> tokens [a-z0-9]+ -> sem stopwords -> len >= 2."""
    tokens = TOKEN_RE.findall(strip_accents(text.lower()))
    return [
        t for t in tokens
        if len(t) >= 2 and not (remove_stopwords and t in STOPWORDS)
    ]

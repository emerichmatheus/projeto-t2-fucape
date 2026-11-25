"""Árvore Trie para autocompletar prefixos.

Chegar ao nó do prefixo custa O(|P|). Cada nó guarda as ``top_k`` palavras
mais frequentes da sua subárvore (pré-computadas na construção), então a
sugestão sai em O(|P|) sem percorrer a subárvore na hora da consulta.
"""
from __future__ import annotations

import heapq


class TrieNode:
    __slots__ = ("children", "freq", "top")

    def __init__(self) -> None:
        self.children: dict[str, TrieNode] = {}
        self.freq = 0          # > 0 se uma palavra termina aqui
        self.top: list[tuple[int, str]] = []


class Trie:
    def __init__(self, top_k: int = 8) -> None:
        self.root = TrieNode()
        self.top_k = top_k
        self.size = 0

    def insert(self, word: str, freq: int = 1) -> None:
        node = self.root
        for ch in word:
            node = node.children.setdefault(ch, TrieNode())
        if node.freq == 0:
            self.size += 1
        node.freq += freq

    def contains(self, word: str) -> bool:
        node = self._find(word)
        return node is not None and node.freq > 0

    def _find(self, prefix: str) -> TrieNode | None:
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def build_top(self) -> None:
        """Pós-ordem: guarda em cada nó as top_k palavras da subárvore."""
        def visit(node: TrieNode, prefix: str) -> list[tuple[int, str]]:
            cands = [(node.freq, prefix)] if node.freq else []
            for ch, child in node.children.items():
                cands.extend(visit(child, prefix + ch))
            node.top = heapq.nlargest(self.top_k, cands)
            return node.top
        import sys
        sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
        visit(self.root, "")

    def autocomplete(self, prefix: str, limit: int | None = None) -> list[tuple[str, int]]:
        node = self._find(prefix)
        if node is None:
            return []
        if not node.top and (node.freq or node.children):
            self.build_top()
        return [(w, f) for f, w in node.top[: limit or self.top_k]]

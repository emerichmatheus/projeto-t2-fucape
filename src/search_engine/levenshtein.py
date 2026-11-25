"""Distância de edição de Levenshtein por Programação Dinâmica (implementação própria).

D[i][j] = mínimo entre
    D[i-1][j]   + 1   (remoção)
    D[i][j-1]   + 1   (inserção)
    D[i-1][j-1] + c   (substituição; c = 0 se a[i] == b[j])

Usamos só duas linhas da matriz (memória O(min(|a|, |b|))).
"""
from __future__ import annotations


def levenshtein(a: str, b: str) -> int:
    """Distância completa: preenche toda a matriz |a| x |b|."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def levenshtein_bounded(a: str, b: str, max_dist: int) -> int:
    """Mesma DP, com corte antecipado.

    Se o menor valor de uma linha já passou de ``max_dist``, nenhuma célula
    seguinte pode ficar abaixo disso, então paramos e devolvemos ``max_dist + 1``.
    """
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_dist:
        return max_dist + 1
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v)
            if v < row_min:
                row_min = v
        if row_min > max_dist:
            return max_dist + 1
        prev = cur
    return prev[-1] if prev[-1] <= max_dist else max_dist + 1

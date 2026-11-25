"""Benchmark cronometrado: Baseline (Antes) vs. Otimizado (Depois).

Para cada consulta de teste: 1 aquecimento + N repetições medidas com
``time.perf_counter()``. Reporta média e desvio padrão em ms, Δ%, speedup,
comparações de Levenshtein evitadas, concordância das correções e a memória
das estruturas de cada abordagem (``tracemalloc``).

Uso (dentro do contêiner do painel ou localmente com o DW em localhost:5433):
    python -m search_engine.benchmark [--reps 20]
"""
from __future__ import annotations

import argparse
import csv
import statistics
import time
import tracemalloc
from pathlib import Path

from search_engine.baseline import BruteForceCorrector
from search_engine.engine import SearchEngine
from search_engine.optimized import KGramCorrector
from search_engine.preprocess import tokenize

# Consultas com erros de digitação realistas (troca, omissão, inserção de letra).
QUERIES = [
    "otimizasao", "travano", "servidro", "hackr", "lagadno",
    "graficso ruim", "multiplayr", "atualisacao", "bugado demias", "dificil dmeais",
    "jogabilidadde", "pessimo suprote", "comunidadde toxica", "viciamte", "trapasa",
    "histroia incrivel", "desempneho", "chetaers", "precço alto", "otmizado",
]

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"


def _time_ms(fn, reps: int) -> tuple[float, float]:
    fn()  # aquecimento
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.mean(samples), (statistics.stdev(samples) if reps > 1 else 0.0)


def compare_query(engine: SearchEngine, query: str, reps: int = 20) -> dict:
    terms = tokenize(query)
    base_c = engine.baseline.correct(terms)
    opt_c = engine.optimized.correct(terms)
    b_mean, b_std = _time_ms(lambda: engine.baseline.correct(terms), reps)
    o_mean, o_std = _time_ms(lambda: engine.optimized.correct(terms), reps)
    base_cmp, opt_cmp = base_c.comparisons, opt_c.comparisons
    return {
        "consulta": query,
        "correcao_baseline": " ".join(base_c.corrected_terms),
        "correcao_otimizada": " ".join(opt_c.corrected_terms),
        "concordam": base_c.corrected_terms == opt_c.corrected_terms,
        "baseline_ms": round(b_mean, 3),
        "baseline_std_ms": round(b_std, 3),
        "otimizado_ms": round(o_mean, 3),
        "otimizado_std_ms": round(o_std, 3),
        "delta_pct": round((b_mean - o_mean) / b_mean * 100, 2) if b_mean else 0.0,
        "speedup": round(b_mean / o_mean, 1) if o_mean else 0.0,
        "comparacoes_baseline": base_cmp,
        "comparacoes_otimizado": opt_cmp,
        "comparacoes_evitadas_pct": round((1 - opt_cmp / base_cmp) * 100, 2) if base_cmp else 0.0,
    }


def measure_memory(dictionary: dict[str, int], **kw) -> dict:
    """Pico de memória (MB) para construir as estruturas de cada abordagem."""
    out = {}
    for name, factory in (("baseline", lambda: BruteForceCorrector(dict(dictionary))),
                          ("otimizado", lambda: KGramCorrector(dict(dictionary), **kw))):
        tracemalloc.start()
        obj = factory()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        out[f"memoria_{name}_mb"] = round(peak / 2**20, 2)
        del obj
    return out


def run_benchmark(engine: SearchEngine, queries=QUERIES, reps: int = 20) -> tuple[list[dict], dict]:
    rows = [compare_query(engine, q, reps) for q in queries]
    b = sum(r["baseline_ms"] for r in rows)
    o = sum(r["otimizado_ms"] for r in rows)
    cmp_b = sum(r["comparacoes_baseline"] for r in rows)
    cmp_o = sum(r["comparacoes_otimizado"] for r in rows)
    summary = {
        "documentos": len(engine.docs),
        "vocabulario_total": len(engine.term_freq),
        "dicionario_correcao": len(engine.dictionary),
        "consultas": len(rows),
        "repeticoes": reps,
        "baseline_ms_medio": round(b / len(rows), 3),
        "otimizado_ms_medio": round(o / len(rows), 3),
        "delta_pct_global": round((b - o) / b * 100, 2),
        "speedup_global": round(b / o, 1),
        "comparacoes_evitadas_pct": round((1 - cmp_o / cmp_b) * 100, 2) if cmp_b else 0.0,
        "concordancia_pct": round(100 * sum(r["concordam"] for r in rows) / len(rows), 1),
        **measure_memory(engine.dictionary, k=engine.optimized.index.k,
                         jaccard_threshold=engine.optimized.threshold,
                         max_dist=engine.optimized.max_dist),
    }
    return rows, summary


def save_results(rows: list[dict], summary: dict, out_dir: Path = DOCS_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "benchmark_resultados.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = [
        "# Resultados do benchmark (gerado por `python -m search_engine.benchmark`)",
        "",
        f"Corpus: **{summary['documentos']:,}** reviews · vocabulário total "
        f"**{summary['vocabulario_total']:,}** termos · dicionário de correção "
        f"**{summary['dicionario_correcao']:,}** termos · {summary['repeticoes']} "
        "repetições por consulta (após aquecimento).",
        "",
        "| Consulta | Correção | Baseline (ms) | Otimizado (ms) | Δ% | Speedup | "
        "Comparações evitadas | Concordam |",
        "|---|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['consulta']}` | {r['correcao_otimizada']} | "
            f"{r['baseline_ms']:.2f} ± {r['baseline_std_ms']:.2f} | "
            f"{r['otimizado_ms']:.3f} ± {r['otimizado_std_ms']:.3f} | "
            f"{r['delta_pct']:.2f}% | {r['speedup']:.1f}× | "
            f"{r['comparacoes_evitadas_pct']:.2f}% | {'✅' if r['concordam'] else '❌'} |")
    lines += [
        "",
        "| Métrica global | Valor |",
        "|---|---:|",
        f"| Tempo médio baseline (T_antes) | {summary['baseline_ms_medio']:.2f} ms |",
        f"| Tempo médio otimizado (T_depois) | {summary['otimizado_ms_medio']:.3f} ms |",
        f"| Δ% = (T_antes − T_depois) / T_antes × 100 | {summary['delta_pct_global']:.2f}% |",
        f"| Speedup = T_antes / T_depois | {summary['speedup_global']:.1f}× |",
        f"| Comparações de Levenshtein evitadas | {summary['comparacoes_evitadas_pct']:.2f}% |",
        f"| Concordância das correções | {summary['concordancia_pct']:.1f}% |",
        f"| Memória das estruturas — baseline | {summary['memoria_baseline_mb']:.2f} MB |",
        f"| Memória das estruturas — otimizado (k-gramas + Trie) | "
        f"{summary['memoria_otimizado_mb']:.2f} MB |",
        "",
    ]
    (out_dir / "benchmark_resultados.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    from sqlalchemy import create_engine

    import config
    from search_engine.corpus import load_corpus

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=20)
    args = parser.parse_args()
    docs = load_corpus(create_engine(config.dw_sqlalchemy_url()))
    print(f"Corpus carregado: {len(docs)} reviews. Construindo índices...")
    engine = SearchEngine(docs)
    rows, summary = run_benchmark(engine, reps=args.reps)
    save_results(rows, summary)
    for r in rows:
        print(f"{r['consulta']:<22} -> {r['correcao_otimizada']:<22} "
              f"base={r['baseline_ms']:8.2f}ms opt={r['otimizado_ms']:7.3f}ms "
              f"speedup={r['speedup']:6.1f}x evitadas={r['comparacoes_evitadas_pct']:5.1f}% "
              f"{'OK' if r['concordam'] else 'DIVERGE'}")
    print(summary)


if __name__ == "__main__":
    main()

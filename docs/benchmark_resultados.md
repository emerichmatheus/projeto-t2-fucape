# Resultados do benchmark (gerado por `python -m search_engine.benchmark`)

Corpus: **15,962** reviews · vocabulário total **17,419** termos · dicionário de correção **3,939** termos · 20 repetições por consulta (após aquecimento).

| Consulta | Correção | Baseline (ms) | Otimizado (ms) | Δ% | Speedup | Comparações evitadas | Concordam |
|---|---|---:|---:|---:|---:|---:|:---:|
| `otimizasao` | otimizacao | 160.99 ± 62.42 | 0.312 ± 0.053 | 99.81% | 516.4× | 99.92% | ✅ |
| `travano` | travado | 154.80 ± 72.95 | 0.329 ± 0.061 | 99.79% | 471.0× | 99.82% | ✅ |
| `servidro` | servidor | 103.00 ± 7.77 | 0.385 ± 0.134 | 99.63% | 267.5× | 99.85% | ✅ |
| `hackr` | hack | 68.60 ± 6.33 | 0.079 ± 0.026 | 99.88% | 867.8× | 99.90% | ✅ |
| `lagadno` | lagado | 80.67 ± 3.27 | 0.080 ± 0.016 | 99.90% | 1005.8× | 99.97% | ✅ |
| `graficso ruim` | grafico ruim | 87.29 ± 6.57 | 0.144 ± 0.024 | 99.84% | 607.2× | 99.92% | ✅ |
| `multiplayr` | multiplayer | 124.38 ± 24.64 | 0.135 ± 0.031 | 99.89% | 922.7× | 99.95% | ✅ |
| `atualisacao` | atualizacao | 128.62 ± 8.73 | 0.542 ± 0.131 | 99.58% | 237.4× | 99.82% | ✅ |
| `bugado demias` | bugado demais | 101.31 ± 35.83 | 0.539 ± 0.173 | 99.47% | 188.1× | 99.75% | ✅ |
| `dificil dmeais` | dificil dmais | 75.62 ± 5.92 | 0.206 ± 0.059 | 99.73% | 366.6× | 99.72% | ✅ |
| `jogabilidadde` | jogabilidade | 210.93 ± 92.68 | 0.423 ± 0.038 | 99.80% | 499.1× | 99.85% | ✅ |
| `pessimo suprote` | pessimo suporte | 135.18 ± 72.27 | 0.955 ± 1.192 | 99.29% | 141.5× | 99.90% | ✅ |
| `comunidadde toxica` | comunidade toxica | 296.70 ± 183.04 | 1.343 ± 0.728 | 99.55% | 221.0× | 99.75% | ✅ |
| `viciamte` | viciante | 95.78 ± 19.00 | 0.422 ± 0.425 | 99.56% | 227.0× | 99.80% | ✅ |
| `trapasa` | trapaca | 109.03 ± 19.38 | 0.404 ± 0.151 | 99.63% | 269.6× | 99.77% | ✅ |
| `histroia incrivel` | historia incrivel | 88.53 ± 13.49 | 0.351 ± 0.059 | 99.60% | 251.9× | 99.85% | ✅ |
| `desempneho` | desempenho | 136.91 ± 54.30 | 0.358 ± 0.199 | 99.74% | 382.0× | 99.95% | ✅ |
| `chetaers` | cheaters | 95.39 ± 20.72 | 0.121 ± 0.059 | 99.87% | 785.7× | 99.97% | ✅ |
| `precço alto` | preco alto | 59.02 ± 15.84 | 0.321 ± 0.187 | 99.46% | 184.0× | 99.59% | ✅ |
| `otmizado` | otimizado | 54.44 ± 4.41 | 0.217 ± 0.066 | 99.60% | 251.1× | 99.85% | ✅ |

| Métrica global | Valor |
|---|---:|
| Tempo médio baseline (T_antes) | 118.36 ms |
| Tempo médio otimizado (T_depois) | 0.383 ms |
| Δ% = (T_antes − T_depois) / T_antes × 100 | 99.68% |
| Speedup = T_antes / T_depois | 308.8× |
| Comparações de Levenshtein evitadas | 99.85% |
| Concordância das correções | 100.0% |
| Memória das estruturas — baseline | 0.13 MB |
| Memória das estruturas — otimizado (k-gramas + Trie) | 3.95 MB |

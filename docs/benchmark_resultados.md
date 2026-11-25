# Resultados do benchmark (gerado por `python -m search_engine.benchmark`)

Corpus: **15,962** reviews · vocabulário total **17,419** termos · dicionário de correção **3,939** termos · 20 repetições por consulta (após aquecimento).

| Consulta | Correção | Baseline (ms) | Otimizado (ms) | Δ% | Speedup | Comparações evitadas | Concordam |
|---|---|---:|---:|---:|---:|---:|:---:|
| `otimizasao` | otimizacao | 77.69 ± 16.16 | 0.142 ± 0.070 | 99.82% | 548.3× | 99.92% | ✅ |
| `travano` | travado | 41.96 ± 1.87 | 0.157 ± 0.059 | 99.63% | 267.0× | 99.82% | ✅ |
| `servidro` | servidor | 54.63 ± 11.69 | 0.125 ± 0.034 | 99.77% | 436.0× | 99.85% | ✅ |
| `hackr` | hack | 38.67 ± 6.62 | 0.044 ± 0.006 | 99.89% | 888.7× | 99.90% | ✅ |
| `lagadno` | lagado | 67.11 ± 25.99 | 0.033 ± 0.004 | 99.95% | 2055.7× | 99.97% | ✅ |
| `graficso ruim` | grafico ruim | 53.50 ± 7.88 | 0.092 ± 0.054 | 99.83% | 583.4× | 99.92% | ✅ |
| `multiplayr` | multiplayer | 64.17 ± 14.80 | 0.159 ± 0.031 | 99.75% | 402.5× | 99.95% | ✅ |
| `atualisacao` | atualizacao | 86.27 ± 17.75 | 0.222 ± 0.041 | 99.74% | 389.1× | 99.82% | ✅ |
| `bugado demias` | bugado demais | 42.15 ± 4.86 | 0.161 ± 0.058 | 99.62% | 261.6× | 99.75% | ✅ |
| `dificil dmeais` | dificil dmais | 42.35 ± 5.21 | 0.172 ± 0.083 | 99.59% | 245.6× | 99.72% | ✅ |
| `jogabilidadde` | jogabilidade | 82.44 ± 6.40 | 0.209 ± 0.163 | 99.75% | 393.9× | 99.85% | ✅ |
| `pessimo suprote` | pessimo suporte | 74.42 ± 20.97 | 0.124 ± 0.017 | 99.83% | 599.3× | 99.90% | ✅ |
| `comunidadde toxica` | comunidade toxica | 110.71 ± 27.54 | 0.294 ± 0.090 | 99.73% | 376.2× | 99.75% | ✅ |
| `viciamte` | viciante | 54.13 ± 4.12 | 0.173 ± 0.028 | 99.68% | 312.2× | 99.80% | ✅ |
| `trapasa` | trapaca | 54.69 ± 9.89 | 0.145 ± 0.011 | 99.74% | 377.9× | 99.77% | ✅ |
| `histroia incrivel` | historia incrivel | 50.07 ± 5.15 | 0.110 ± 0.011 | 99.78% | 455.0× | 99.85% | ✅ |
| `desempneho` | desempenho | 48.89 ± 1.33 | 0.082 ± 0.010 | 99.83% | 599.0× | 99.95% | ✅ |
| `chetaers` | cheaters | 55.23 ± 9.78 | 0.043 ± 0.003 | 99.92% | 1298.9× | 99.97% | ✅ |
| `precço alto` | preco alto | 68.90 ± 21.93 | 0.284 ± 0.096 | 99.59% | 242.9× | 99.59% | ✅ |
| `otmizado` | otimizado | 67.09 ± 12.33 | 0.276 ± 0.122 | 99.59% | 243.0× | 99.85% | ✅ |

| Métrica global | Valor |
|---|---:|
| Tempo médio baseline (T_antes) | 61.75 ms |
| Tempo médio otimizado (T_depois) | 0.152 ms |
| Δ% = (T_antes − T_depois) / T_antes × 100 | 99.75% |
| Speedup = T_antes / T_depois | 405.3× |
| Comparações de Levenshtein evitadas | 99.85% |
| Concordância das correções | 100.0% |
| Memória das estruturas — baseline | 0.13 MB |
| Memória das estruturas — otimizado (k-gramas + Trie) | 4.10 MB |

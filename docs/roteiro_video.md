# Roteiro do vídeo (≤ 10 min)

## Preparação (antes de gravar)

- `docker compose up -d` e `docker compose ps`: tudo *healthy*.
- Para mostrar retries nos logs, coloque `STEAM_SIMULATE_429_RATE=0.2` no `.env`, rode `docker compose up -d` (recria os contêineres) e, se quiser uma coleta curta, `STEAM_MAX_PAGES=5`. **Volte para 0 / 20 depois.**
- Deixe abertos: Airflow (`localhost:8080`), DBeaver ou terminal com `psql` (`localhost:5433`, dw/dw, `steam_dw`), painel (`localhost:8501`) e o README no GitHub.

## Cronograma

| Tempo | Bloco | O que mostrar / falar |
|---|---|---|
| 0:00–0:45 | **Abertura** | Tema e dor: estúdios recebem milhares de reviews em PT-BR, cheias de erro de digitação. Mostrar o diagrama de arquitetura do README |
| 0:45–1:30 | **Docker** | `docker-compose.yml`: webserver, scheduler, triggerer, Postgres de metadados, DW separado, Streamlit. Volumes nomeados + bind mount `./data`. `docker compose ps` |
| 1:30–3:30 | **Airflow: DAG 1** | *Graph view*: `coletar_reviews` mapeada (8 instâncias, `.expand`), `coletar_appdetails`, auditoria, `disparar_consolidacao_dw`. Disparar. Abrir o log de uma instância e mostrar `página=N ... cursor=...` e as linhas `[RETRY 1/5] ... HTTP 429 ... Aguardando 1.52s (backoff exponencial + jitter)`. Mostrar a pasta `data/raw/steam_reviews/ingest_date=.../app_id=730.jsonl` |
| 3:30–4:30 | **Airflow: DAG 2** | Disparada sozinha pelo TriggerDagRunOperator (mostrar o `conf` com `ds`). Tasks em sequência até `validar_integridade`. Log da `carregar_fato` com inseridas/atualizadas |
| 4:30–5:15 | **Idempotência** | Rodar `bash scripts/prova_idempotencia.sh` (ou mostrar a tabela do README): contagem e somas idênticas, `inseridas = 0` na 2ª execução |
| 5:15–6:15 | **Data Warehouse** | No DBeaver: as 5 tabelas do schema `dw`, o diagrama ER (DBeaver gera) e a consulta `SELECT * FROM dw.dim_jogo`. Uma consulta analítica (taxa de recomendação por jogo). Ler em voz alta a granularidade |
| 6:15–7:15 | **Painel: Negócio** | KPIs, reviews por mês, % de recomendação por jogo/gênero, faixa do autor. Filtrar um jogo (ex.: Apex Legends, a menor taxa) |
| 7:15–8:30 | **Painel: Busca** | Digitar `servidro caindo` → "Você quis dizer: servidor caindo", resultados com BM25 e trecho destacado. Mostrar o autocompletar (Trie) digitando `otim`. Trocar para Baseline e ver o tempo subir de ~0,15 ms para ~60 ms |
| 8:30–9:30 | **Painel: Engenharia** | Benchmark ao vivo (Antes vs. Depois, Δ%, speedup, comparações evitadas), gráfico do benchmark completo (~400×, 100% de concordância), status dos pipelines vindo da `etl_auditoria` |
| 9:30–10:00 | **Fechamento** | Resumo: resiliência + idempotência + Kimball + Opção 3 com ganho de 99,75% |

---

# Perguntas prováveis na arguição + respostas curtas

### Engenharia / Airflow

**Como você garantiu a idempotência da DAG 1?**
Cada `ds` tem uma partição e cada jogo tem um arquivo. Escrevo num `.tmp` e faço `os.replace` (rename atômico) por cima do arquivo do dia. Rodar de novo substitui o arquivo em vez de acrescentar. Também deduplico por `recommendationid` dentro da execução.

**E da DAG 2?**
UPSERT pela chave natural: `ON CONFLICT (nk) DO UPDATE` nas dimensões e `ON CONFLICT (nk_recommendation_id)` na fato, que é `UNIQUE`. Na 2ª execução tudo vira UPDATE, nada é inserido, e contagens e somas ficam idênticas (prova no README).

**Por que backoff exponencial com jitter?**
O exponencial dá tempo para o servidor se recuperar sem martelar a API. O jitter (aleatório de 0 a 1 s) dessincroniza clientes que falharam juntos e evita o *thundering herd*. Se vier `Retry-After`, eu respeito o cabeçalho.

**Quais erros você repete e quais não?**
Repito 429, 5xx, timeout e erro de conexão, que são transitórios. Não repito os outros 4xx nem JSON inválido, porque tentar de novo não resolve.

**Como funciona a paginação?**
Por cursor: começo com `*` e mando de volta o `cursor` de cada resposta. Paro com lista vazia, cursor nulo, cursor repetido (proteção contra loop) ou no limite de páginas.

**Por que TriggerDagRunOperator e não Datasets?**
Porque ele passa o `ds` no `conf`, e a DAG 2 sabe exatamente qual partição ler. O vínculo também fica visível na UI. A DAG 2 tem `schedule=None`.

**O endpoint do enunciado (`/appreviews`) funcionou?**
Não. Hoje ele redireciona (302) para a home, porque foi descontinuado. Migrei para o substituto oficial `IUserReviewsService/GetAppReviews`, que é público e mantém os mesmos campos e o cursor.

**Por que um Postgres separado para o DW?**
Isolamento: carga analítica e metadados do Airflow não competem por recursos, e posso recriar um sem afetar o outro.

### Modelagem

**Qual é a granularidade?**
Uma linha por review publicada por um usuário sobre um jogo, na data de criação da review.

**O que é surrogate key e por que usar?**
É uma chave inteira artificial, sem significado de negócio, gerada pelo DW (IDENTITY). Ela desacopla o DW da fonte (se o steamid mudar de formato, nada quebra), permite SCD, deixa os joins mais rápidos que com strings e dá uma chave uniforme para a fato.

**Mas `sk_tempo` é YYYYMMDD, isso não é natural key?**
Para a dimensão data, Kimball recomenda essa smart key: é inteira, estável (o calendário não muda), legível e facilita particionar. As outras SKs são IDENTITY puras.

**Por que `max(sk_autor)` é maior que o número de autores?**
No Postgres, o `INSERT ... ON CONFLICT` reserva um valor da sequência mesmo quando vira UPDATE. Isso gera lacunas, o que é normal, porque SK não é contador. A SK de uma linha existente nunca muda.

**Diferença entre aditiva, semi-aditiva e não-aditiva no seu modelo?**
Aditivas (`qtd_review`, `recomendou`, votos, horas na review) somam em qualquer corte. `horas_jogadas_total` é semi-aditiva: é snapshot acumulado do autor, então soma entre autores mas não ao longo do tempo. `score_utilidade` e a taxa de recomendação são não-aditivas: usa-se a média, ou `SUM(recomendou)/SUM(qtd_review)`.

**O que é `nk_recommendation_id`?**
Uma dimensão degenerada: é a chave de negócio da transação e fica na fato porque não tem atributos próprios. Também é a chave do UPSERT.

**Como `dim_autor` lida com mudanças?**
SCD Tipo 1: sobrescreve com o valor mais recente (nº de reviews do autor). Se precisasse de histórico, usaria Tipo 2 com `valido_de`/`valido_ate`.

**Por que o texto da review está na fato?**
Pela granularidade, o texto é um atributo da própria review (1:1 com a linha). Ele é o corpus da busca. Uma alternativa seria uma "junk/text dimension" 1:1, sem ganho real aqui.

### Busca (PLN & RI)

**Explique o algoritmo otimizado.**
São 2 estágios. (1) Quebro o termo em trigramas com `$` nas pontas e uso um índice invertido de k-gramas para achar só os termos que compartilham trigramas. Filtro por Jaccard ≥ 0,2 e por diferença de tamanho ≤ 2. (2) Calculo Levenshtein, com corte antecipado, só nesses ~6 candidatos em vez de 3.939. Escolho a menor distância e desempato pela frequência.

**Por que é mais rápido?**
Levenshtein custa O(|a|·|b|) por par. O baseline faz isso para o vocabulário inteiro. O índice de k-gramas descarta 99,85% dos termos com operações baratas (contagem de interseção), então só sobra trabalho caro para poucos candidatos. Resultado: ~400× mais rápido.

**O filtro de tamanho não perde correções?**
Não, porque Levenshtein(a, b) ≥ ||a| − |b||. Se a diferença de tamanho passa de 2, a distância também passa, e esse termo nunca seria escolhido.

**E o Jaccard, pode perder?**
Pode, com limiar alto. Por isso calibrei: com k=3 e J ≥ 0,2, a concordância com o força-bruta foi de 100% nas 20 consultas. Com 0,3 caiu para ~89%.

**Para que serve a Trie?**
Para o autocompletar: descer até o nó do prefixo custa O(|P|), e cada nó já guarda as top-8 palavras mais frequentes da subárvore.

**Como funciona o BM25?**
Soma, para cada termo da consulta, `IDF · tf·(k1+1) / (tf + k1·(1 − b + b·|D|/avgdl))`. O IDF valoriza termos raros, `k1=1,5` satura a frequência e `b=0,75` penaliza documentos longos.

**Qual é a linha de base?**
Levenshtein força-bruta: a mesma DP (sem corte) contra todo o dicionário, com o mesmo critério de escolha. Por isso dá para comparar tempo e concordância de forma justa.

**Como você mediu?**
Com `time.perf_counter()`: 1 aquecimento e 20 repetições por consulta, média e desvio padrão em ms. Também meço comparações evitadas e memória com `tracemalloc`.

**Qual o custo da otimização?**
Memória: ~4 MB para os índices, contra 0,13 MB do baseline. É um trade-off espaço × tempo muito favorável.

**Limitações?**
Levenshtein não trata transposição como 1 operação (`dmeais` → `dmais`, não `demais`). Damerau-Levenshtein resolveria. O dicionário também vem do próprio corpus, então erros frequentes (≥ 5 ocorrências) viram "palavras".

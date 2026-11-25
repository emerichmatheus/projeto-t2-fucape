#!/usr/bin/env bash
# Prova de idempotência da DAG 2: roda a consolidação DUAS vezes sobre a
# mesma partição raw e compara contagem e somas da fato antes/depois.
# Uso: bash scripts/prova_idempotencia.sh [AAAA-MM-DD]
set -euo pipefail
cd "$(dirname "$0")/.."

DS="${1:-$(ls data/raw/steam_reviews | sed 's/ingest_date=//' | sort | tail -1)}"
SNAPSHOT="SELECT count(*) AS linhas, count(DISTINCT nk_recommendation_id) AS nks_distintas,
  sum(qtd_review) AS soma_qtd_review, sum(recomendou) AS soma_recomendou,
  sum(votos_util) AS soma_votos_util, round(sum(horas_jogadas_na_review), 2) AS soma_horas,
  (SELECT count(*) FROM dw.dim_autor) AS autores, (SELECT max(sk_autor) FROM dw.dim_autor) AS max_sk_autor,
  (SELECT count(*) FROM dw.dim_jogo) AS jogos, (SELECT count(*) FROM dw.dim_tempo) AS dias
FROM dw.fato_review;"

snapshot() {
  echo "== $1"
  docker compose exec -T dw-postgres psql -U "${DW_USER:-dw}" -d "${DW_DB:-steam_dw}" -c "$SNAPSHOT"
}

run_dag2() {
  local run_id="prova_idempotencia_$1_$(date +%s)"
  docker compose exec -T airflow-scheduler airflow dags trigger dag_consolidacao_dw \
    -r "$run_id" -c "{\"ds\": \"$DS\"}" > /dev/null
  echo -n "Aguardando $run_id "
  while true; do
    state=$(docker compose exec -T airflow-scheduler airflow dags list-runs -d dag_consolidacao_dw \
      -o plain 2>/dev/null | grep "$run_id" | awk '{print $3}')
    case "$state" in
      success) echo " -> success"; break ;;
      failed) echo " -> FAILED"; exit 1 ;;
      *) echo -n "."; sleep 5 ;;
    esac
  done
}

echo "Partição raw: ingest_date=$DS"
snapshot "ANTES"
run_dag2 1
snapshot "DEPOIS DA 1ª EXECUÇÃO"
run_dag2 2
snapshot "DEPOIS DA 2ª EXECUÇÃO (deve ser idêntico ao anterior)"
docker compose exec -T dw-postgres psql -U "${DW_USER:-dw}" -d "${DW_DB:-steam_dw}" -c \
  "SELECT run_id, linhas_lidas, linhas_inseridas, linhas_atualizadas, status
     FROM dw.etl_auditoria WHERE run_id LIKE 'prova_idempotencia%' ORDER BY fim DESC LIMIT 2;"

"""Painel executivo — Steam Reviews Intelligence (T2 FUCAPE).

Três abas, todas lendo o Data Warehouse (Star Schema):
1. Visão de Negócio  — KPIs e agregações via SQL nas tabelas fato/dimensões;
2. Busca Textual     — correção ortográfica (baseline ou otimizada) + BM25;
3. Engenharia        — benchmark ao vivo e completo + status dos pipelines.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

import config  # noqa: E402
from search_engine.benchmark import QUERIES, compare_query, run_benchmark, save_results  # noqa: E402
from search_engine.corpus import load_corpus  # noqa: E402
from search_engine.engine import SearchEngine, highlight  # noqa: E402
from search_engine.preprocess import tokenize  # noqa: E402

st.set_page_config(page_title="Steam Reviews Intelligence", page_icon="🎮", layout="wide")
BENCH_CSV = ROOT / "docs" / "benchmark_resultados.csv"


# ------------------------------------------------------------------ recursos
@st.cache_resource
def get_db():
    return create_engine(config.dw_sqlalchemy_url(), pool_pre_ping=True)


@st.cache_resource(show_spinner="Construindo índices (BM25, k-gramas, Trie)...")
def get_search_engine() -> SearchEngine:
    return SearchEngine(load_corpus(get_db()))


@st.cache_data(ttl=300)
def query_df(sql: str, **params) -> pd.DataFrame:
    with get_db().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def fato_filter_sql() -> str:
    return ("FROM dw.fato_review f JOIN dw.dim_jogo j ON j.sk_jogo = f.sk_jogo "
            "JOIN dw.dim_tempo t ON t.sk_tempo = f.sk_tempo "
            "JOIN dw.dim_autor a ON a.sk_autor = f.sk_autor "
            "WHERE j.nome_jogo = ANY(:jogos) AND t.data_completa BETWEEN :ini AND :fim")


# ------------------------------------------------------------- verificação
try:
    jogos_df = query_df("SELECT nome_jogo FROM dw.dim_jogo ORDER BY 1")
    periodo = query_df("SELECT min(t.data_completa) ini, max(t.data_completa) fim "
                       "FROM dw.fato_review f JOIN dw.dim_tempo t USING (sk_tempo)")
except Exception as exc:  # DW ainda vazio
    st.error("Não foi possível ler o Data Warehouse. Rode a DAG 1 (que dispara a DAG 2) "
             f"no Airflow e recarregue a página.\n\n`{exc.__class__.__name__}: {exc}`")
    st.stop()

if jogos_df.empty or pd.isna(periodo.loc[0, "ini"]):
    st.warning("O Data Warehouse está vazio. Rode a DAG 1 no Airflow.")
    st.stop()

st.title("🎮 Steam Reviews Intelligence")
st.caption("Percepção dos jogadores brasileiros · Airflow → Raw (JSONL) → Star Schema → "
           "Painel + Busca tolerante a erros")

aba_neg, aba_busca, aba_eng = st.tabs(
    ["📊 Visão de Negócio", "🔎 Busca Textual", "⚙️ Engenharia & Benchmark"])

# =========================================================== 1. NEGÓCIO
with aba_neg:
    c1, c2 = st.columns([3, 2])
    todos = jogos_df["nome_jogo"].tolist()
    jogos = c1.multiselect("Jogos", todos, default=todos)
    ini, fim = periodo.loc[0, "ini"], periodo.loc[0, "fim"]
    datas = c2.date_input("Período (data da review)", (ini, fim), min_value=ini, max_value=fim)
    if not jogos or not isinstance(datas, tuple) or len(datas) != 2:
        st.info("Selecione ao menos um jogo e um período completo.")
    else:
        p = {"jogos": jogos, "ini": datas[0], "fim": datas[1]}
        base = fato_filter_sql()
        kpi = query_df(
            "SELECT SUM(f.qtd_review) total, SUM(f.recomendou)::float / NULLIF(SUM(f.qtd_review), 0) taxa, "
            "AVG(f.horas_jogadas_na_review) horas, SUM(f.votos_util) votos, "
            f"AVG(f.score_utilidade) score {base}", **p).iloc[0]
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total de reviews", f"{int(kpi.total or 0):,}".replace(",", "."))
        k2.metric("% de recomendação", f"{(kpi.taxa or 0) * 100:.1f}%")
        k3.metric("Média de horas na review", f"{kpi.horas or 0:.1f} h")
        k4.metric("Votos úteis (soma)", f"{int(kpi.votos or 0):,}".replace(",", "."))
        k5.metric("Score de utilidade (média)", f"{kpi.score or 0:.3f}")

        mensal = query_df(
            "SELECT t.ano_mes, j.nome_jogo, SUM(f.qtd_review) reviews, "
            "100.0 * SUM(f.recomendou) / SUM(f.qtd_review) pct_recomendacao "
            f"{base} GROUP BY 1, 2 ORDER BY 1", **p)
        st.plotly_chart(px.bar(mensal, x="ano_mes", y="reviews", color="nome_jogo",
                               title="Reviews por mês (dim_tempo)",
                               labels={"ano_mes": "Mês", "reviews": "Reviews",
                                       "nome_jogo": "Jogo"}), use_container_width=True)

        g1, g2 = st.columns(2)
        por_jogo = query_df(
            "SELECT j.nome_jogo, SUM(f.qtd_review) reviews, "
            "100.0 * SUM(f.recomendou) / SUM(f.qtd_review) pct_recomendacao, "
            "AVG(f.horas_jogadas_na_review) horas_media "
            f"{base} GROUP BY 1 ORDER BY 3", **p)
        g1.plotly_chart(px.bar(por_jogo, x="pct_recomendacao", y="nome_jogo", orientation="h",
                               text_auto=".1f", title="% de recomendação por jogo (dim_jogo)",
                               labels={"pct_recomendacao": "% recomendação", "nome_jogo": ""},
                               range_x=[0, 100]), use_container_width=True)
        por_genero = query_df(
            "SELECT TRIM(g) genero, SUM(f.qtd_review) reviews, "
            "100.0 * SUM(f.recomendou) / SUM(f.qtd_review) pct_recomendacao "
            f"{base.replace('WHERE', ', LATERAL unnest(string_to_array(j.generos, %s)) g WHERE')} "
            "GROUP BY 1 ORDER BY 2 DESC".replace("%s", "','"), **p)
        g2.plotly_chart(px.bar(por_genero, x="genero", y="pct_recomendacao", text_auto=".1f",
                               hover_data=["reviews"],
                               title="% de recomendação por gênero (dim_jogo.generos)",
                               labels={"genero": "Gênero", "pct_recomendacao": "% recomendação"},
                               range_y=[0, 100]), use_container_width=True)

        g3, g4 = st.columns(2)
        faixa = query_df(
            "SELECT a.faixa_reviews_escritas faixa, SUM(f.qtd_review) reviews, "
            "100.0 * SUM(f.recomendou) / SUM(f.qtd_review) pct_recomendacao "
            f"{base} GROUP BY 1", **p)
        ordem = ["1", "2-5", "6-20", "21-100", "100+", "Não informado"]
        faixa["ordem"] = faixa["faixa"].map({v: i for i, v in enumerate(ordem)})
        faixa = faixa.sort_values("ordem")
        g3.plotly_chart(px.bar(faixa, x="faixa", y="reviews", text="reviews",
                               color="pct_recomendacao", color_continuous_scale="RdYlGn",
                               range_color=[60, 100],
                               title="Reviews por experiência do autor (dim_autor)",
                               labels={"faixa": "Reviews já escritas pelo autor",
                                       "reviews": "Reviews", "pct_recomendacao": "% rec."}),
                        use_container_width=True)
        horas = query_df(
            "SELECT CASE WHEN f.horas_jogadas_na_review < 10 THEN '0-10h' "
            "WHEN f.horas_jogadas_na_review < 50 THEN '10-50h' "
            "WHEN f.horas_jogadas_na_review < 200 THEN '50-200h' "
            "WHEN f.horas_jogadas_na_review < 1000 THEN '200-1000h' ELSE '1000h+' END faixa, "
            "MIN(f.horas_jogadas_na_review) o, SUM(f.qtd_review) reviews, "
            "100.0 * SUM(f.recomendou) / SUM(f.qtd_review) pct_recomendacao "
            f"{base} GROUP BY 1 ORDER BY 2", **p)
        g4.plotly_chart(px.line(horas, x="faixa", y="pct_recomendacao", markers=True,
                                title="% de recomendação por horas jogadas na review",
                                labels={"faixa": "Horas jogadas ao escrever",
                                        "pct_recomendacao": "% recomendação"}),
                        use_container_width=True)
        with st.expander("Tabela por jogo"):
            st.dataframe(por_jogo, use_container_width=True, hide_index=True)

# ============================================================= 2. BUSCA
with aba_busca:
    engine = get_search_engine()

    def _usar_sugestao(palavra: str) -> None:
        partes = st.session_state.get("q", "").rstrip().split(" ")
        partes[-1] = palavra
        st.session_state["q"] = " ".join(partes) + " "

    c1, c2 = st.columns([4, 2])
    q = c1.text_input("Buscar nas reviews (tolerante a erros de digitação)",
                      key="q", placeholder="ex.: otimizasao, servidro, travano...")
    metodo = c2.radio("Método de correção", ["otimizado", "baseline"], horizontal=True,
                      format_func=lambda m: {"otimizado": "Otimizado (k-gramas + Jaccard)",
                                             "baseline": "Baseline (força-bruta)"}[m])
    ultimo = q.split(" ")[-1] if q and not q.endswith(" ") else ""
    sugestoes = engine.autocomplete(ultimo, 6) if len(ultimo) >= 2 else []
    if sugestoes:
        cols = st.columns(len(sugestoes) + 1)
        cols[0].caption("Autocompletar (Trie):")
        for col, (w, f) in zip(cols[1:], sugestoes):
            col.button(f"{w} ({f})", key=f"sug_{w}", on_click=_usar_sugestao, args=(w,))

    if q.strip():
        res = engine.search(q, method=metodo, k=10)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tempo da correção", f"{res.ms_correcao:.3f} ms")
        m2.metric("Tempo do BM25", f"{res.ms_ranking:.3f} ms")
        m3.metric("Comparações de Levenshtein", f"{res.correction.comparisons:,}".replace(",", "."))
        m4.metric("Resultados", len(res.hits))
        if res.suggestion:
            st.info(f"🔤 Você quis dizer: **{res.suggestion}**")
        termos = res.correction.corrected_terms
        if not res.hits:
            st.warning("Nenhuma review encontrada.")
        for i, h in enumerate(res.hits, 1):
            icone = "👍" if h["recomendou"] else "👎"
            with st.container(border=True):
                st.markdown(f"**#{i} · {h['nome_jogo']}** · {h['data_completa']:%d/%m/%Y} · "
                            f"{icone} · BM25 = `{h['score']:.3f}` · {h['votos_util']} votos úteis")
                st.markdown(highlight(h["texto"], termos))
    else:
        st.caption(f"Corpus: {len(engine.docs):,} reviews · dicionário de correção: "
                   f"{len(engine.dictionary):,} termos".replace(",", "."))

# ======================================================= 3. ENGENHARIA
with aba_eng:
    engine = get_search_engine()
    st.subheader("⏱️ Benchmark ao vivo — Antes vs. Depois")
    c1, c2 = st.columns([3, 1])
    q_live = c1.text_input("Consulta", value=st.session_state.get("q", "") or "otimizasao travano",
                           key="q_live")
    reps = c2.number_input("Repetições", 1, 100, 20)
    if q_live.strip() and tokenize(q_live):
        r = compare_query(engine, q_live, reps=int(reps))
        m = st.columns(5)
        m[0].metric("Tempo Antes (baseline)", f"{r['baseline_ms']:.2f} ms",
                    help=f"± {r['baseline_std_ms']:.2f} ms")
        m[1].metric("Tempo Depois (otimizado)", f"{r['otimizado_ms']:.3f} ms",
                    help=f"± {r['otimizado_std_ms']:.3f} ms")
        m[2].metric("Δ% de ganho", f"{r['delta_pct']:.2f}%")
        m[3].metric("Speedup", f"{r['speedup']:.1f}×")
        m[4].metric("Comparações evitadas", f"{r['comparacoes_evitadas_pct']:.2f}%",
                    help=f"{r['comparacoes_baseline']} → {r['comparacoes_otimizado']}")
        st.caption(f"Correção baseline: **{r['correcao_baseline']}** · otimizada: "
                   f"**{r['correcao_otimizada']}** · "
                   f"{'✅ concordam' if r['concordam'] else '❌ divergem'}")

    st.divider()
    st.subheader("📋 Benchmark completo")
    if st.button(f"Rodar benchmark completo agora ({len(QUERIES)} consultas × 20 repetições)"):
        with st.spinner("Medindo..."):
            rows, summary = run_benchmark(engine, reps=20)
            save_results(rows, summary)
            st.session_state["bench_summary"] = summary
    if BENCH_CSV.exists():
        bench = pd.read_csv(BENCH_CSV)
        s = st.session_state.get("bench_summary")
        tot_b, tot_o = bench["baseline_ms"].mean(), bench["otimizado_ms"].mean()
        m = st.columns(5)
        m[0].metric("T_antes médio", f"{tot_b:.2f} ms")
        m[1].metric("T_depois médio", f"{tot_o:.3f} ms")
        m[2].metric("Δ% global", f"{(tot_b - tot_o) / tot_b * 100:.2f}%")
        m[3].metric("Speedup global", f"{tot_b / tot_o:.1f}×")
        m[4].metric("Concordância", f"{bench['concordam'].mean() * 100:.0f}%")
        longo = bench.melt(id_vars="consulta", value_vars=["baseline_ms", "otimizado_ms"],
                           var_name="método", value_name="ms")
        fig = px.bar(longo, x="consulta", y="ms", color="método", barmode="group", log_y=True,
                     title="Tempo de correção por consulta (escala log)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(bench, use_container_width=True, hide_index=True)
        if s:
            st.json(s)
    else:
        st.info("Ainda não há resultados salvos. Clique no botão acima.")

    st.divider()
    st.subheader("🩺 Status dos pipelines (etl_auditoria)")
    audit = query_df("SELECT dag_id, run_id, ds, status, linhas_lidas, linhas_inseridas, "
                     "linhas_atualizadas, inicio, fim, fim - inicio AS duracao "
                     "FROM dw.etl_auditoria ORDER BY fim DESC NULLS LAST LIMIT 20")
    for dag_id in ["dag_ingestao_raw", "dag_consolidacao_dw"]:
        ult = audit[audit.dag_id == dag_id].head(1)
        if not ult.empty:
            u = ult.iloc[0]
            ok = "🟢" if u.status == "success" else "🔴"
            st.markdown(f"{ok} **{dag_id}** — última execução `{u.fim:%d/%m/%Y %H:%M}` · "
                        f"status **{u.status}** · lidas {u.linhas_lidas:,} · inseridas "
                        f"{u.linhas_inseridas:,} · atualizadas {u.linhas_atualizadas:,}")
    st.dataframe(audit, use_container_width=True, hide_index=True)
    integ = query_df(
        "SELECT (SELECT count(*) FROM dw.fato_review) linhas_fato, "
        "(SELECT count(*) - count(DISTINCT nk_recommendation_id) FROM dw.fato_review) nk_duplicadas, "
        "(SELECT count(*) FROM dw.fato_review f LEFT JOIN dw.dim_autor a USING (sk_autor) "
        " WHERE a.sk_autor IS NULL) fk_orfas_autor, "
        "(SELECT count(*) FROM dw.fato_review f LEFT JOIN dw.dim_jogo j USING (sk_jogo) "
        " WHERE j.sk_jogo IS NULL) fk_orfas_jogo")
    st.caption("Integridade do Star Schema (ao vivo)")
    st.dataframe(integ, hide_index=True)

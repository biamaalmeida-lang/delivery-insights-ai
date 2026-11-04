"""Delivery Insights AI — aplicação Streamlit para feedback de delivery."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import hashlib
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from core import (CAMPOS, COLS_IA, SENTIMENTOS, labeled, normalize_frame,
                  plan_actions, read_input, score_against_gold, suggest_columns, summarize)
from ai_classifier import analyze_batch

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Delivery Insights AI", page_icon="🍽️", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
.block-container {padding-top:1.5rem; max-width:1450px}
h1 {font-weight:800 !important; letter-spacing:-.03em}
div[data-testid="stMetric"] {background:#f2f7f9;border-radius:14px;padding:14px 18px}
[data-testid="stSidebar"] {background:#f7fafb}
</style>""", unsafe_allow_html=True)

st.title("🍽️ Delivery Insights AI")
st.caption("Transformando avaliações em decisões inteligentes · Protótipo independente com dados de demonstração sintéticos")

with st.sidebar:
    st.header("📂 Fonte dos dados")
    origem = st.radio("Escolha a base", ["Demonstração classificada", "Demonstração sem rótulos", "Enviar minha planilha"], index=0)
    up = None
    if origem == "Enviar minha planilha":
        up = st.file_uploader("CSV ou Excel (.xlsx), até 10 MB", type=["csv", "xlsx"])
        if up is None:
            st.info("Selecione um arquivo para continuar.")
            st.stop()
        raw, nome = up.getvalue(), up.name
    else:
        sample = "avaliacoes_classificadas_120.csv" if origem == "Demonstração classificada" else "avaliacoes_120.csv"
        path = ROOT / "samples" / sample
        raw, nome = path.read_bytes(), sample
    digest = hashlib.sha256(raw).hexdigest()
    st.caption("Somente dados fictícios/públicos autorizados. Em modo IA, comentários são enviados à API escolhida.")

try:
    base, abas = read_input(raw, nome)
except Exception as exc:
    st.error(f"Não foi possível ler o arquivo: {exc}")
    st.stop()
if abas and len(abas) > 1:
    aba = st.sidebar.selectbox("Aba do Excel", abas)
    base, _ = read_input(raw, nome, aba)

suggest = suggest_columns(base.columns)
with st.sidebar.expander("Associar colunas", expanded=("comentario" not in suggest)):
    st.caption("Confira o nome da coluna de comentário. Os demais campos são opcionais.")
    choices = ["(não informado)"] + list(base.columns)
    mapping = {}
    for field in CAMPOS:
        proposal = suggest.get(field)
        index = choices.index(proposal) if proposal in choices else 0
        val = st.selectbox(field, choices, index=index, key=f"map_{digest[:9]}_{field}")
        if val != "(não informado)":
            mapping[field] = val

try:
    normalized = normalize_frame(base, mapping)
except Exception as exc:
    st.error(f"Corrija a associação das colunas: {exc}")
    st.stop()

source_id = digest + "|" + str(sorted(mapping.items()))
if st.session_state.get("source_id") != source_id:
    st.session_state["source_id"] = source_id
    st.session_state["dataset"] = normalized.copy()
    st.session_state["analysis_origin"] = "Planilha já classificada" if labeled(normalized) else "Aguardando análise"
    st.session_state["last_error"] = ""

df = st.session_state["dataset"]
with st.sidebar:
    st.divider()
    st.header("⚙️ Classificação")
    st.caption(f"Status: {st.session_state['analysis_origin']}")
    remaining = int(df["sentimento"].str.strip().eq("").sum())
    st.write(f"**{remaining}** de **{len(df)}** comentários sem classificação")
    if remaining:
        st.caption("A demonstração classificada funciona sem chave. Para analisar novos textos, conecte uma API real.")
        key_default = os.getenv("OPENAI_API_KEY", "")
        try:
            key_default = st.secrets.get("OPENAI_API_KEY", key_default)
        except Exception:
            pass
        key_input = st.text_input("Chave da API OpenAI", type="password", help="Não será incluída no projeto ou salva em arquivo.")
        apikey = key_input.strip() or key_default
        maxrows = st.slider("Máximo de comentários nesta execução", 1, min(200, remaining), min(40, remaining))
        model = st.selectbox("Modelo", ["gpt-4o-mini", "gpt-4.1-mini"], index=0)
        if st.button("✨ Analisar com IA real", type="primary", disabled=(not apikey), use_container_width=True):
            target = df[df["sentimento"].str.strip().eq("")].head(maxrows)
            bar = st.progress(0, text="Conectando à API...")
            total = len(target)
            done = 0
            try:
                for start in range(0, total, 8):
                    batch = target.iloc[start:start+8]
                    items = [{"id_pedido": str(r["id_pedido"]), "comentario": str(r["comentario"])} for _, r in batch.iterrows()]
                    results = analyze_batch(items, apikey, model)
                    for r in results:
                        ix = st.session_state["dataset"].index[st.session_state["dataset"]["id_pedido"].eq(r["id_pedido"])]
                        if len(ix):
                            for col in COLS_IA:
                                st.session_state["dataset"].at[ix[0], col] = str(r.get(col, ""))
                    done += len(batch)
                    bar.progress(done/total, text=f"Classificados: {done}/{total}")
                st.session_state["analysis_origin"] = f"IA via API ({model}), revisão humana recomendada"
                st.success(f"Análise concluída: {done} avaliações. Pode haver custos de API.")
                st.rerun()
            except Exception as exc:
                st.error(f"A análise parou após {done} avaliações. As classificações concluídas foram preservadas. Detalhe: {exc}")
    st.divider()
    st.header("🔎 Filtros")
    restaurants = sorted(df["restaurante"].dropna().unique()) if "restaurante" in df else []
    selected_rest = st.multiselect("Restaurante", restaurants, default=restaurants)
    sent_options = [x for x in SENTIMENTOS if x in df["sentimento"].unique()]
    selected_sent = st.multiselect("Sentimento", sent_options, default=sent_options)
    probs = sorted([x for x in df["problema_principal"].dropna().unique() if str(x).strip() and str(x).casefold() != "nenhum"])
    selected_prob = st.multiselect("Problema principal (opcional)", probs)

filtered = df.copy()
if restaurants:
    filtered = filtered[filtered["restaurante"].isin(selected_rest)]
if sent_options and selected_sent:
    filtered = filtered[filtered["sentimento"].isin(selected_sent)]
if sent_options and not selected_sent:
    filtered = filtered.iloc[0:0]
if selected_prob:
    filtered = filtered[filtered["problema_principal"].isin(selected_prob)]

if not labeled(df):
    st.warning("Esta base ainda não foi classificada. Use a API para analisar os comentários ou selecione a demonstração classificada. Não simulamos uma IA.")
elif st.session_state["analysis_origin"] == "Planilha já classificada":
    st.info("Modo demonstração: os rótulos foram importados de uma planilha previamente classificada. Esta execução não realizou chamadas de IA.")

tab1, tab2, tab3, tab4 = st.tabs(["📈 Dashboard", "🧾 Avaliações", "🎯 Plano de ação", "🧪 Validação do modelo"])

with tab1:
    st.subheader("Visão executiva")
    stats = summarize(filtered)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Avaliações", f"{stats['total']:,}".replace(",", "."))
    m2.metric("Nota média", "—" if stats["nota_media"] is None or pd.isna(stats["nota_media"]) else f"{stats['nota_media']:.2f} / 5")
    m3.metric("Reclamações no texto", stats["reclamacoes"] if labeled(filtered) else "—")
    m4.metric("Entregas com atraso", "—" if stats["atraso_pct"] is None else f"{stats['atraso_pct']:.1f}%")
    if filtered.empty:
        st.warning("Nenhuma avaliação corresponde aos filtros selecionados.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            if labeled(filtered):
                sent = filtered[filtered["sentimento"].str.strip().ne("")]["sentimento"].value_counts().reset_index()
                sent.columns = ["sentimento", "avaliacoes"]
                fig = px.pie(sent, names="sentimento", values="avaliacoes", hole=.55, title="Sentimentos identificados", color="sentimento", color_discrete_map={"Positivo":"#18937b", "Negativo":"#d24b4b", "Misto":"#e2a53c", "Neutro":"#7b90a8"})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aguardando classificação para gráficos de sentimento.")
        with c2:
            plan = plan_actions(filtered)
            if not plan.empty:
                chart = plan.head(10).sort_values("Ocorrências")
                st.plotly_chart(px.bar(chart, x="Ocorrências", y="Problema", orientation="h", title="Problemas principais mais frequentes", color_discrete_sequence=["#087F8C"]), use_container_width=True)
            else:
                st.info("Nenhum problema classificado para os filtros atuais.")
        c3, c4 = st.columns(2)
        with c3:
            if "restaurante" in filtered and "nota_1a5" in filtered and filtered["nota_1a5"].notna().any():
                avg = filtered.groupby("restaurante", as_index=False)["nota_1a5"].mean().sort_values("nota_1a5")
                f = px.bar(avg, x="nota_1a5", y="restaurante", orientation="h", title="Nota média por restaurante", range_x=[0,5], color_discrete_sequence=["#128b85"])
                st.plotly_chart(f, use_container_width=True)
        with c4:
            if "data_pedido" in filtered and filtered["data_pedido"].notna().any() and "nota_1a5" in filtered:
                temporal = filtered.dropna(subset=["data_pedido", "nota_1a5"]).copy()
                temporal["semana"] = temporal["data_pedido"].dt.to_period("W").dt.start_time
                timeline = temporal.groupby("semana", as_index=False)["nota_1a5"].mean()
                if not timeline.empty:
                    st.plotly_chart(px.line(timeline, x="semana", y="nota_1a5", markers=True, title="Evolução semanal da nota média", range_y=[0,5]), use_container_width=True)
        if "restaurante" in filtered and labeled(filtered):
            r = filtered.groupby("restaurante", as_index=False).agg(avaliacoes=("id_pedido", "size"), reclamacoes=("sentimento", lambda x: x.isin(["Negativo", "Misto"]).sum()))
            r["% reclamações"] = (r["reclamacoes"] / r["avaliacoes"] * 100).round(1)
            st.subheader("Comparação entre restaurantes")
            st.dataframe(r, use_container_width=True, hide_index=True)
        st.caption("Reclamações: comentários com sentimento Negativo ou Misto. Problemas recorrentes: categoria principal atribuída a cada avaliação; problemas secundários não entram nesse ranking. Atraso é calculado pelos campos operacionais, quando disponíveis.")

with tab2:
    st.subheader("Avaliações e classificações")
    st.caption("Revise e edite as colunas de classificação. A edição preserva o comentário original. Não cole dados pessoais na versão pública.")
    all_cols = [col for col in ["id_pedido", "restaurante", "nota_1a5", "comentario"] + COLS_IA if col in df.columns]
    if not filtered.empty:
        edited = st.data_editor(filtered[all_cols], hide_index=True, use_container_width=True, num_rows="fixed", key="review_table", disabled=[c for c in ["id_pedido", "restaurante", "nota_1a5", "comentario"] if c in all_cols], column_config={"sentimento": st.column_config.SelectboxColumn("Sentimento", options=SENTIMENTOS, required=False), "prioridade": st.column_config.SelectboxColumn("Prioridade", options=["Alta","Média","Baixa"], required=False)})
        if st.button("Salvar revisões humanas"):
            data = st.session_state["dataset"]
            updated = edited.set_index("id_pedido")
            for idx, entry in data.iterrows():
                if entry["id_pedido"] in updated.index:
                    for field in COLS_IA:
                        if field in updated.columns:
                            data.at[idx, field] = str(updated.loc[entry["id_pedido"], field])
            st.session_state["analysis_origin"] = "Classificações revisadas por humano"
            st.success("Revisões salvas na sessão atual.")
    st.divider()
    st.subheader("Exportação")
    output_csv = df.copy()
    if "data_pedido" in output_csv:
        output_csv["data_pedido"] = output_csv["data_pedido"].dt.strftime("%Y-%m-%d")
    for col in output_csv.select_dtypes(include="object").columns:
        output_csv[col] = output_csv[col].map(lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
    st.download_button("⬇️ Baixar resultados em CSV", output_csv.to_csv(index=False, sep=";").encode("utf-8-sig"), file_name="delivery_insights_resultados.csv", mime="text/csv")
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        output_csv.to_excel(writer, sheet_name="Avaliacoes", index=False)
        plan_actions(df).to_excel(writer, sheet_name="Plano_de_acao", index=False)
    st.download_button("⬇️ Baixar Excel", buffer.getvalue(), file_name="delivery_insights_resultados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab3:
    st.subheader("Problemas recorrentes e recomendações")
    p = plan_actions(filtered)
    if p.empty:
        st.info("Nenhuma ocorrência categorizada para gerar recomendações.")
    else:
        st.caption("As ações são sugestões de melhoria, não resultados já alcançados. Priorize após validação com o time responsável.")
        st.dataframe(p, hide_index=True, use_container_width=True)
        top = p.iloc[0]
        st.markdown(f"**Maior recorrência:** {top['Problema']} — {int(top['Ocorrências'])} avaliações ({top['% das avaliações']}%).")
        st.write(f"**Ação inicial sugerida:** {top['Ação recomendada']}")
        st.write(f"**KPI para monitorar:** {top['KPI de acompanhamento']}")
        st.download_button("⬇️ Baixar plano de ação", p.to_csv(index=False, sep=";").encode("utf-8-sig"), "plano_de_acao.csv", mime="text/csv")

with tab4:
    st.subheader("Validação contra um gabarito")
    st.write("Faça o upload de classificações de referência feitas sem mostrar os rótulos à IA. O gabarito de demonstração está na pasta `samples/`.")
    gold_file = st.file_uploader("Gabarito CSV ou Excel", type=["csv", "xlsx"], key="gold")
    if gold_file is not None:
        try:
            gold, _ = read_input(gold_file.getvalue(), gold_file.name)
            comparison = score_against_gold(df, gold)
            acc = float(comparison["acertou_sentimento"].mean()*100)
            co1, co2, co3 = st.columns(3)
            co1.metric("Amostra comparável", len(comparison))
            co2.metric("Acurácia do sentimento", f"{acc:.1f}%")
            if "acertou_problema" in comparison:
                co3.metric("Concordância do problema principal", f"{comparison['acertou_problema'].mean()*100:.1f}%")
            m = pd.crosstab(comparison["sentimento_referencia"], comparison["sentimento"])
            st.plotly_chart(px.imshow(m, text_auto=True, title="Matriz de confusão — sentimento", labels=dict(x="Previsto",y="Referência", color="Casos")), use_container_width=True)
            st.dataframe(comparison[comparison["acertou_sentimento"] == False], use_container_width=True, hide_index=True)
            st.caption("Métrica calculada nesta amostra, não uma medida comprovada de desempenho em dados reais.")
        except Exception as exc:
            st.error(f"Não foi possível validar o gabarito: {exc}")
    else:
        st.info("Envie o gabarito para visualizar a comparação.")

st.divider()
st.caption("Projeto experimental independente · Dados de exemplo sintéticos · Classificações produzidas por IA exigem revisão humana · Não afiliado ao iFood")

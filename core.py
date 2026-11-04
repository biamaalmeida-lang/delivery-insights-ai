"""Leitura, padronização e análises do Delivery Insights AI."""
from __future__ import annotations
from io import BytesIO
import unicodedata
import pandas as pd

SENTIMENTOS = ["Positivo", "Negativo", "Misto", "Neutro"]
CAMPOS = ["id_pedido", "data_pedido", "restaurante", "tipo_culinaria", "nota_1a5", "comentario", "prazo_estimado_min", "tempo_entrega_min", "atraso_min", "valor_pedido_brl", "frete_brl"]
COLS_IA = ["sentimento", "problema_principal", "problema_secundario", "aspecto_positivo", "prioridade", "justificativa", "acao_recomendada"]
SINONIMOS = {
    "comentario": ["comentarios", "comentarios_clientes", "avaliacao", "avaliacoes", "review", "texto", "feedback", "mensagem", "descricao_avaliacao"],
    "id_pedido": ["pedido", "id", "order_id", "numero_pedido"],
    "restaurante": ["loja", "estabelecimento", "nome_restaurante", "merchant", "restaurant"],
    "nota_1a5": ["nota", "estrelas", "rating", "avaliacao_nota", "nota_avaliacao"],
    "data_pedido": ["data", "date", "data_avaliacao", "data_da_avaliacao"],
    "tipo_culinaria": ["culinaria", "categoria"],
    "tempo_entrega_min": ["tempo_entrega", "tempo_real", "duracao_entrega"],
    "prazo_estimado_min": ["prazo_estimado", "previsao_entrega"],
    "valor_pedido_brl": ["valor_pedido", "valor", "ticket"],
    "frete_brl": ["frete", "taxa_entrega"],
}
ACOES = {
    "Atraso na entrega": ("Revisar previsão de entrega e capacidade em horários de pico; avisar clientes proativamente.", "% de entregas no prazo"),
    "Atrasos": ("Revisar previsão de entrega e capacidade em horários de pico; avisar clientes proativamente.", "% de entregas no prazo"),
    "Embalagem danificada": ("Revisar vedação, transporte e inspeção das embalagens na expedição.", "Reclamações de embalagem / 100 pedidos"),
    "Embalagens": ("Revisar vedação, transporte e inspeção das embalagens na expedição.", "Reclamações de embalagem / 100 pedidos"),
    "Item faltando": ("Implementar conferência de itens e acompanhamentos antes do despacho.", "% de pedidos com itens faltantes"),
    "Itens faltantes": ("Implementar conferência de itens e acompanhamentos antes do despacho.", "% de pedidos com itens faltantes"),
    "Pedido incorreto": ("Conferir itens e modificações do pedido antes de lacrar a embalagem.", "% de pedidos incorretos"),
    "Pedidos incorretos": ("Conferir itens e modificações do pedido antes de lacrar a embalagem.", "% de pedidos incorretos"),
    "Temperatura inadequada": ("Reduzir intervalo entre preparo e coleta e revisar embalagem térmica.", "Reclamações de temperatura / 100 pedidos"),
    "Temperatura": ("Reduzir intervalo entre preparo e coleta e revisar embalagem térmica.", "Reclamações de temperatura / 100 pedidos"),
    "Qualidade da comida": ("Reforçar padrões de preparo, conservação e inspeção final.", "Reclamações de qualidade / 100 pedidos"),
    "Atendimento": ("Padronizar respostas e acompanhar tempo até a primeira solução.", "Tempo de primeira resposta"),
    "Preço ou cobrança": ("Conferir valores e comunicar claramente porções, frete e taxas.", "Reclamações de cobrança / 100 pedidos"),
    "Preço/cobrança": ("Conferir valores e comunicar claramente porções, frete e taxas.", "Reclamações de cobrança / 100 pedidos"),
    "Instrução não atendida": ("Destacar restrições na comanda e conferir customizações na expedição.", "% de instruções atendidas"),
    "Instruções ignoradas": ("Destacar restrições na comanda e conferir customizações na expedição.", "% de instruções atendidas"),
}


def norm(value: str) -> str:
    x = unicodedata.normalize("NFKD", str(value).strip().lower())
    x = "".join(c for c in x if not unicodedata.combining(c))
    return "_".join(x.replace("-", " ").split())


def suggest_columns(cols):
    normalized = {norm(col): col for col in cols}
    result = {}
    for field in CAMPOS:
        for candidate in [field] + SINONIMOS.get(field, []):
            if norm(candidate) in normalized:
                result[field] = normalized[norm(candidate)]
                break
    return result


def read_input(raw: bytes, name: str, sheet=None) -> tuple[pd.DataFrame, list[str]]:
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError("Arquivo excede o limite de 10 MB.")
    if name.lower().endswith(".csv"):
        df = None
        for encoding in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                df = pd.read_csv(BytesIO(raw), sep=None, engine="python", encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        if df is None:
            raise ValueError("CSV com codificação incompatível.")
        return df, []
    if name.lower().endswith(".xlsx"):
        x = pd.ExcelFile(BytesIO(raw), engine="openpyxl")
        return pd.read_excel(x, sheet_name=sheet or x.sheet_names[0]), x.sheet_names
    raise ValueError("Use arquivos .csv ou .xlsx.")


def normalize_frame(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    if not mapping.get("comentario"):
        raise ValueError("Selecione a coluna que contém os comentários.")
    reverse = {original: canonical for canonical, original in mapping.items() if original}
    if len(reverse) != len([v for v in mapping.values() if v]):
        raise ValueError("Uma coluna original não pode ser atribuída a dois campos diferentes.")
    d = df.rename(columns=reverse).copy()
    if "comentario" not in d.columns:
        raise ValueError("A coluna de comentário não foi encontrada.")
    d["comentario"] = d["comentario"].fillna("").astype(str).str.strip()
    d = d[d["comentario"].ne("")].reset_index(drop=True)
    if d.empty:
        raise ValueError("A planilha não possui comentários válidos.")
    if len(d) > 3000:
        raise ValueError("Para esta versão, utilize até 3.000 avaliações por arquivo.")
    if "id_pedido" not in d:
        d["id_pedido"] = [f"LINHA-{i+1:05d}" for i in range(len(d))]
    d["id_pedido"] = d["id_pedido"].fillna("").astype(str)
    d.loc[d["id_pedido"].eq(""), "id_pedido"] = [f"LINHA-{i+1:05d}" for i in d.index[d["id_pedido"].eq("")]]
    d["id_pedido"] = d["id_pedido"].astype(str)
    if d["id_pedido"].duplicated().any():
        d["id_pedido"] = [f"{i+1:05d}-{value}" for i, value in enumerate(d["id_pedido"])]
    for col in ("nota_1a5", "prazo_estimado_min", "tempo_entrega_min", "atraso_min", "valor_pedido_brl", "frete_brl"):
        if col in d:
            if d[col].dtype == object:
                d[col] = d[col].astype(str).str.replace("R$", "", regex=False).str.strip().str.replace(",", ".", regex=False)
            d[col] = pd.to_numeric(d[col], errors="coerce")
    if "data_pedido" in d:
        dates = d["data_pedido"].astype(str).str.strip()
        iso = dates.str.match(r"^\d{4}-\d{2}-\d{2}").mean() > 0.7
        d["data_pedido"] = pd.to_datetime(d["data_pedido"], errors="coerce", dayfirst=not iso)
    if "atraso_min" not in d and {"tempo_entrega_min", "prazo_estimado_min"}.issubset(d.columns):
        d["atraso_min"] = (d["tempo_entrega_min"] - d["prazo_estimado_min"]).clip(lower=0)
    for col in COLS_IA:
        if col not in d:
            d[col] = ""
        d[col] = d[col].fillna("").astype(str)
    return d


def labeled(df: pd.DataFrame) -> bool:
    return "sentimento" in df and df["sentimento"].astype(str).str.strip().ne("").any()


def summarize(df: pd.DataFrame) -> dict:
    result = {"total": len(df), "reclamacoes": 0, "nota_media": None, "atraso_pct": None}
    if "sentimento" in df:
        result["reclamacoes"] = int(df["sentimento"].isin(["Negativo", "Misto"]).sum())
    if "nota_1a5" in df:
        result["nota_media"] = df["nota_1a5"].mean()
    if "atraso_min" in df and df["atraso_min"].notna().any():
        result["atraso_pct"] = float(df["atraso_min"].gt(0).mean() * 100)
    return result


def plan_actions(df: pd.DataFrame) -> pd.DataFrame:
    if not labeled(df):
        return pd.DataFrame()
    probs = df["problema_principal"].fillna("").astype(str).str.strip()
    probs = probs[~probs.str.casefold().isin(["", "nenhum", "none", "nan", "outros"])]
    counts = probs.value_counts().rename_axis("Problema").reset_index(name="Ocorrências")
    if counts.empty:
        return pd.DataFrame()
    counts["% das avaliações"] = (counts["Ocorrências"] / len(df) * 100).round(1)
    counts["Ação recomendada"] = counts["Problema"].apply(lambda x: ACOES.get(x, ("Investigar amostra de comentários e elaborar ação corretiva específica.", "Ocorrência por 100 avaliações"))[0])
    counts["KPI de acompanhamento"] = counts["Problema"].apply(lambda x: ACOES.get(x, ("", "Ocorrência por 100 avaliações"))[1])
    return counts


def score_against_gold(predicted: pd.DataFrame, gold: pd.DataFrame):
    g = gold.copy()
    if "id_pedido" not in g or "sentimento_referencia" not in g:
        raise ValueError("O gabarito precisa ter 'id_pedido' e 'sentimento_referencia'.")
    d = predicted[["id_pedido", "sentimento", "problema_principal"]].copy()
    d["id_pedido"] = d["id_pedido"].astype(str)
    g["id_pedido"] = g["id_pedido"].astype(str)
    comparison = d.merge(g, on="id_pedido", how="inner")
    if comparison.empty:
        raise ValueError("Nenhum ID do gabarito coincide com a base carregada.")
    comparison["acertou_sentimento"] = comparison["sentimento"].astype(str).str.casefold() == comparison["sentimento_referencia"].astype(str).str.casefold()
    if "problema_principal_referencia" in comparison:
        comparison["acertou_problema"] = comparison["problema_principal"].astype(str).map(norm) == comparison["problema_principal_referencia"].astype(str).map(norm)
    return comparison

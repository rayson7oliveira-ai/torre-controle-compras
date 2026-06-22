Aqui está o código completo, consolidado e pronto para colar — com todas as 8 correções aplicadas + a 5ª métrica de pendências de aprovação:

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import io
import re
import unicodedata

# Configuração da página do Streamlit
st.set_page_config(layout="wide", page_title="Follow-Up de Compras")

# ==================================================================
# IDENTIDADE DO SISTEMA - APENAS FOLLOW-UP DE COMPRAS
# ==================================================================
st.title("🗂️ FOLLOW-UP DE COMPRAS")
st.subheader("Monitoramento Operacional de Ordens de Compra (OC)")

# ==================================================================
# HELPERS DE LEITURA E LIMPEZA (CORREÇÕES CIGAM)
# ==================================================================

def _normalizar_nome(txt: str) -> str:
    """Remove acentos, espaços extras e deixa em UPPER para comparação."""
    if txt is None:
        return ""
    s = str(txt).strip().upper()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s)
    return s


def find_col(df: pd.DataFrame, candidatos):
    """
    Localiza a coluna real do DataFrame a partir de uma lista de nomes
    candidatos (case/acento/espaço-insensível). Aceita match exato e parcial.
    """
    norm_map = {_normalizar_nome(c): c for c in df.columns}
    for cand in candidatos:
        n = _normalizar_nome(cand)
        if n in norm_map:
            return norm_map[n]
    for cand in candidatos:
        n = _normalizar_nome(cand)
        for k_norm, k_orig in norm_map.items():
            if n and n in k_norm:
                return k_orig
    return None


def _converter_ordem_texto(valor):
    """Converter para preservar a coluna ORDEM como texto (sem perder zeros)."""
    if valor is None:
        return ""
    s = str(valor).strip()
    if s.lower() in {"nan", "none", "nat"}:
        return ""
    if re.fullmatch(r"-?\d+\.0+", s):
        s = s.split(".")[0]
    return s


def _padronizar_ordem(serie: pd.Series) -> pd.Series:
    """Restaura zeros à esquerda usando o comprimento máximo observado (>=4)."""
    s = serie.astype(str).str.strip()
    apenas_digitos = s.str.fullmatch(r"\d+")
    if apenas_digitos.any():
        comprimentos = s[apenas_digitos].str.len()
        largura_alvo = int(comprimentos.max()) if not comprimentos.empty else 0
        if largura_alvo >= 4:
            s = s.where(~apenas_digitos, s.str.zfill(largura_alvo))
    return s


def limpar_data_cigam(serie: pd.Series) -> pd.Series:
    """Substitui placeholders típicos do CIGAM ('01/01/0001', '-', '0', etc.)
    por NaN antes da conversão para datetime."""
    if serie is None:
        return serie
    s = serie.astype(str).str.strip()
    placeholders = {"01/01/0001", "1/1/0001", "0001-01-01",
                    "-", "0", "00/00/0000", "nan", "none", "nat", ""}
    s = s.where(~s.str.lower().isin(placeholders), other=pd.NA)
    return s


def parse_data_robusta(serie: pd.Series) -> pd.Series:
    """
    Conversão de datas tolerante ao locale do Windows do usuário.
    Cascata: datetime nativo -> dayfirst -> formatos explícitos -> serial Excel.
    """
    if serie is None:
        return pd.Series(pd.NaT, index=[])

    if pd.api.types.is_datetime64_any_dtype(serie):
        resultado = pd.to_datetime(serie, errors="coerce")
    else:
        resultado = pd.to_datetime(serie, errors="coerce", dayfirst=True)

    mask_nat = resultado.isna() & serie.notna()
    if mask_nat.any():
        textos = serie[mask_nat].astype(str).str.strip()
        formatos = [
            "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
            "%Y-%m-%d", "%Y/%m/%d",
            "%d/%m/%y", "%d-%m-%y",
            "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
        ]
        for fmt in formatos:
            if not mask_nat.any():
                break
            parsed = pd.to_datetime(textos, format=fmt, errors="coerce")
            ok = parsed.notna()
            if ok.any():
                resultado.loc[parsed.index[ok]] = parsed[ok]
                mask_nat = resultado.isna() & serie.notna()
                textos = serie[mask_nat].astype(str).str.strip()

    mask_nat = resultado.isna() & serie.notna()
    if mask_nat.any():
        numeros = pd.to_numeric(serie[mask_nat], errors="coerce")
        validos = numeros.dropna()
        validos = validos[(validos > 32000) & (validos < 80000)]
        if not validos.empty:
            datas_excel = pd.to_datetime(
                validos, origin="1899-12-30", unit="D", errors="coerce"
            )
            resultado.loc[datas_excel.index] = datas_excel

    resultado = pd.to_datetime(resultado, errors="coerce")
    resultado.loc[resultado.dt.year <= 1970] = pd.NaT
    return resultado


# ==================================================================
# UPLOAD
# ==================================================================
arquivo_upload = st.file_uploader(
    "Carregue o relatório Excel de Follow Up (CIGAM)", type=["xlsx", "xls", "csv"]
)

if arquivo_upload is not None:
    # ------------------------------------------------------------------
    # LEITURA TOLERANTE: tudo como texto + converter específico p/ ORDEM
    # ------------------------------------------------------------------
    converters_padrao = {
        "ORDEM": _converter_ordem_texto,
        "Ordem": _converter_ordem_texto,
        "ordem": _converter_ordem_texto,
    }

    try:
        if arquivo_upload.name.lower().endswith(".csv"):
            df_original = pd.read_csv(
                arquivo_upload, header=2, dtype=str,
                converters=converters_padrao, keep_default_na=False,
                na_values=["", "nan", "NaN", "None", "NaT", "-"],
            )
        else:
            df_original = pd.read_excel(
                arquivo_upload, header=2, dtype=str,
                converters=converters_padrao, keep_default_na=False,
                na_values=["", "nan", "NaN", "None", "NaT", "-"],
            )
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        st.stop()

    # Normaliza nomes de colunas
    df_original.columns = [str(c).strip() for c in df_original.columns]

    # Remove linhas totalmente vazias
    df_original = df_original.dropna(how="all")

    # ------------------------------------------------------------------
    # CIGAM EXPORTA DUAS COLUNAS "DATA": a 1ª é da SC, a 2ª é da OC.
    # Renomeia a 1ª para DATA_SC; a 2ª permanece como DATA (criação da OC).
    # ------------------------------------------------------------------
    cols_data_idx = [i for i, c in enumerate(df_original.columns)
                     if str(c).strip().upper() in {"DATA", "DATA.1"}]
    if len(cols_data_idx) >= 2:
        novos_nomes = {}
        primeira = True
        for c in df_original.columns:
            if str(c).strip().upper() in {"DATA", "DATA.1"}:
                novos_nomes[c] = "DATA_SC" if primeira else "DATA"
                primeira = False
        df_original = df_original.rename(columns=novos_nomes)

    # ------------------------------------------------------------------
    # DETECÇÃO RESILIENTE DAS COLUNAS-CHAVE
    # ------------------------------------------------------------------
    col_ordem      = find_col(df_original, ["ORDEM", "ORDEM_OC", "NUM_ORDEM", "OC", "NUMERO ORDEM"])
    col_controle   = find_col(df_original, ["CONTROLE", "STATUS", "SITUACAO"])
    col_data       = find_col(df_original, ["DATA", "DATA_CRIACAO", "DT_CRIACAO", "DATA EMISSAO", "DT_EMISSAO"])
    col_prazo      = find_col(df_original, ["DT_PRAZO_OC", "PRAZO", "DT_PRAZO", "DATA_PRAZO", "PRAZO_ENTREGA"])
    col_aprovacao  = find_col(df_original, ["DATA_APROVACAO", "DT_APROVACAO", "APROVACAO"])
    col_comprador  = find_col(df_original, ["COMPRADOR", "USUARIO", "RESPONSAVEL"])
    col_fornecedor = find_col(df_original, ["CD_FORNECEDOR", "FORNECEDOR", "COD_FORNECEDOR"])

    if not col_ordem:
        st.error("Coluna 'ORDEM' não encontrada no arquivo.")
        st.stop()

    # Padroniza nomes para o resto do código funcionar inalterado
    renames = {}
    if col_ordem != "ORDEM": renames[col_ordem] = "ORDEM"
    if col_controle and col_controle != "CONTROLE": renames[col_controle] = "CONTROLE"
    if col_data and col_data != "DATA": renames[col_data] = "DATA"
    if col_prazo and col_prazo != "DT_PRAZO_OC": renames[col_prazo] = "DT_PRAZO_OC"
    if col_aprovacao and col_aprovacao != "DATA_APROVACAO": renames[col_aprovacao] = "DATA_APROVACAO"
    if col_comprador and col_comprador != "COMPRADOR": renames[col_comprador] = "COMPRADOR"
    if col_fornecedor and col_fornecedor != "CD_FORNECEDOR": renames[col_fornecedor] = "CD_FORNECEDOR"
    if renames:
        df_original = df_original.rename(columns=renames)

    # ------------------------------------------------------------------
    # TRATAMENTO DA COLUNA ORDEM (preserva zeros à esquerda)
    # ------------------------------------------------------------------
    df_original["ORDEM_LIMPA"] = _padronizar_ordem(df_original["ORDEM"]).str.strip()

    # Filtro de solicitações e linhas fantasmas
    df_original = df_original[
        ~df_original["ORDEM_LIMPA"].isin(["0", "0.0", "", "nan", "None", "-", "ORDEM"])
    ].copy()

    if "CONTROLE" in df_original.columns:
        df_original = df_original[df_original["CONTROLE"].astype(str).str.strip().notna()]
        df_original = df_original[
            ~df_original["CONTROLE"].astype(str).str.strip().isin(["nan", "None", "", "-"])
        ]

    df_original = df_original[df_original["ORDEM_LIMPA"].str.len() > 0]

    # ------------------------------------------------------------------
    # NORMALIZA COMPRADOR / FORNECEDOR (tira espaços extras dos códigos)
    # ------------------------------------------------------------------
    for c in ("COMPRADOR", "CD_FORNECEDOR"):
        if c in df_original.columns:
            df_original[c] = (
                df_original[c].astype(str).str.strip()
                .replace({"nan": pd.NA, "None": pd.NA, "-": pd.NA, "": pd.NA})
            )

    # ------------------------------------------------------------------
    # CONVERSÃO ROBUSTA DE DATAS (independente do locale + lixo 01/01/0001)
    # ------------------------------------------------------------------
    if "DATA" in df_original.columns:
        df_original["DATA"] = parse_data_robusta(limpar_data_cigam(df_original["DATA"]))
    else:
        df_original["DATA"] = pd.NaT

    if "DT_PRAZO_OC" in df_original.columns:
        df_original["DT_PRAZO_OC"] = parse_data_robusta(limpar_data_cigam(df_original["DT_PRAZO_OC"]))
    else:
        df_original["DT_PRAZO_OC"] = pd.NaT

    if "DATA_APROVACAO" in df_original.columns:
        df_original["DATA_APROVACAO"] = parse_data_robusta(limpar_data_cigam(df_original["DATA_APROVACAO"]))
    else:
        df_original["DATA_APROVACAO"] = pd.NaT

    hoje = pd.to_datetime(datetime.today().date())

    # ------------------------------------------------------------------
    # MAPEAMENTO DE STATUS COMPLETO (cobre todos status reais do CIGAM)
    # ------------------------------------------------------------------
    df_original["CONTROLE_LIMPO"] = (
        df_original["CONTROLE"].astype(str).str.strip()
        if "CONTROLE" in df_original.columns else ""
    )
    mapa_status = {
        "10 - PENDENTE":           "PENDENTE",
        "20 - APROVADO":           "APROVADA SEM ENVIO",
        "30 - RECEBIDA - PARCIAL": "RECEBIDA PARCIAL",
        "35 - RECEBIDA - TOTAL":   "RECEBIDA TOTAL",
        "40 - ENVIADO EMAIL":      "ENVIADA AO FORNECEDOR",
        "90 - CANCELADA":          "CANCELADA",
        "90 - CANCELADO":          "CANCELADA",
        "VV - VERBA ULTRAPASSADA": "PENDENTE DE APROVAÇÃO",
        # Variantes só com código numérico
        "10": "PENDENTE",
        "20": "APROVADA SEM ENVIO",
        "30": "RECEBIDA PARCIAL",
        "35": "RECEBIDA TOTAL",
        "40": "ENVIADA AO FORNECEDOR",
        "90": "CANCELADA",
        "VV": "PENDENTE DE APROVAÇÃO",
    }
    df_original["STATUS_AMIGAVEL"] = df_original["CONTROLE_LIMPO"].map(mapa_status).fillna(
        df_original["CONTROLE_LIMPO"]
    )

    # ------------------------------------------------------------------
    # CÁLCULO DE LEAD TIME
    # ------------------------------------------------------------------
    def calcular_lead_time_flora(linha):
        if "CANCELADA" in str(linha["STATUS_AMIGAVEL"]).upper() or "90" in str(linha["CONTROLE_LIMPO"]):
            return 888, "Cancelada", "⚫ Cancelada"
        if linha["STATUS_AMIGAVEL"] == "RECEBIDA TOTAL":
            return 999, "Recebida Total", "🔵 Recebida Total"

        prazo = linha["DT_PRAZO_OC"]
        if pd.isna(prazo):
            return pd.NA, "Sem Prazo", "⚪ Sem Prazo"

        lead_time = (prazo - hoje).days
        if lead_time < 0:
            return lead_time, "Atrasada", f"🔴 {lead_time} dias"
        elif 0 <= lead_time <= 10:
            return lead_time, "Vence em até 10 dias", f"🟡 +{lead_time} dias"
        else:
            return lead_time, "Dentro do Prazo", f"🟢 +{lead_time} dias"

    resultados = df_original.apply(calcular_lead_time_flora, axis=1)
    df_original["LEAD_TIME_NUMERICO"]   = [r[0] for r in resultados]
    df_original["SITUACAO_PRAZO"]       = [r[1] for r in resultados]
    df_original["LEAD_TIME_SINALIZADO"] = [r[2] for r in resultados]

    df_original.loc[df_original["SITUACAO_PRAZO"] == "Cancelada", "STATUS_AMIGAVEL"] = "CANCELADA"

    # ------------------------------------------------------------------
    # ALERTA DE APROVAÇÃO TRAVADA (verifica pela chave CONTROLE — não pelo rótulo)
    # ------------------------------------------------------------------
    def calcular_dias_travados(linha):
        if "VV" in str(linha["CONTROLE_LIMPO"]).upper() and not pd.isna(linha["DATA_APROVACAO"]):
            dias = (hoje - linha["DATA_APROVACAO"]).days
            if dias >= 3:
                return f"⚠️ Travado há {dias} dias!"
        return "Ok"
    df_original["ALERTA_APROVACAO"] = df_original.apply(calcular_dias_travados, axis=1)

    # ------------------------------------------------------------------
    # DETECÇÃO DA COLUNA DE SETOR/GRUPO
    # ------------------------------------------------------------------
    col_setor = find_col(df_original, ["SETOR"]) or find_col(df_original, ["GRUPO"])
    if col_setor is None:
        df_original["CLASSIFICACAO"] = "Geral"
        col_setor = "CLASSIFICACAO"

    # Elimina duplicadas por OC antes de aplicar filtros
    df_oc = df_original.drop_duplicates(subset=["ORDEM_LIMPA"]).copy()

    # ==================================================================
    # FILTRO DE PERÍODO USANDO A DATA DE CRIAÇÃO DA OC ('DATA')
    # ==================================================================
    st.markdown("### 📅 Filtro por Período de Criação da Ordem")

    datas_validas = df_oc["DATA"].dropna()
    if not datas_validas.empty:
        data_min_default = datas_validas.min().date()
        data_max_default = datas_validas.max().date()
    else:
        data_min_default = datetime.today().date()
        data_max_default = datetime.today().date()

    periodo_selecionado = st.date_input(
        "Selecione o intervalo de datas (Data Inicial e Data Final):",
        value=(data_min_default, data_max_default),
        min_value=datetime(2000, 1, 1).date(),
        max_value=datetime(2050, 12, 31).date(),
    )

    df_filtrado_data = df_oc.copy()
    if isinstance(periodo_selecionado, tuple) and len(periodo_selecionado) == 2:
        dt_inicio, dt_fim = periodo_selecionado
        df_filtrado_data = df_filtrado_data[
            (df_filtrado_data["DATA"].dt.date >= dt_inicio)
            & (df_filtrado_data["DATA"].dt.date <= dt_fim)
        ]

    # ==================================================================
    # PAINEL DE FILTROS ADICIONAIS
    # ==================================================================
    st.markdown("### 🔍 Filtros de Controle")
    f1, f2, f3, f4 = st.columns(4)

    with f1:
        lista_compradores = (
            ["Todos"] + sorted(
                [str(x) for x in df_filtrado_data["COMPRADOR"].dropna().unique()
                 if str(x).strip() not in ["nan", "None", "", "-"]]
            ) if "COMPRADOR" in df_filtrado_data.columns else ["Todos"]
        )
        comprador_sel = st.selectbox("Comprador", lista_compradores)
    with f2:
        lista_status = ["Todos"] + sorted(
            [str(x) for x in df_filtrado_data["STATUS_AMIGAVEL"].dropna().unique()
             if str(x).strip() not in ["nan", "None", "", "-"]]
        )
        status_sel = st.selectbox("Status", lista_status)
    with f3:
        lista_fornecedores = (
            ["Todos"] + sorted(
                [str(x) for x in df_filtrado_data["CD_FORNECEDOR"].dropna().unique()
                 if str(x).strip() not in ["nan", "None", "", "-"]]
            ) if "CD_FORNECEDOR" in df_filtrado_data.columns else ["Todos"]
        )
        fornecedor_sel = st.selectbox("Fornecedor", lista_fornecedores)
    with f4:
        lista_prazos = ["Todos", "Atrasada", "Vence em até 10 dias", "Dentro do Prazo",
                        "Sem Prazo", "Recebida Total", "Cancelada"]
        prazo_sel = st.selectbox("Situação Prazo", lista_prazos)

    # ==================================================================
    # BUSCA POR NÚMERO DA ORDEM (parcial, ignora zeros à esquerda)
    # ==================================================================
    busca_ordem = st.text_input(
        "🔎 Buscar por número da Ordem (parcial ou completo — ex.: 66723 ou 066723)",
        value="",
        placeholder="Digite o número da OC...",
    ).strip()

    st.markdown("---")
    apenas_gargalos = st.checkbox(
        "🚨 **Focar Apenas em Pendências** (Esconder OCs concluídas, canceladas ou no prazo)"
    )

    df_filtrado = df_filtrado_data.copy()
    if comprador_sel != "Todos" and "COMPRADOR" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["COMPRADOR"] == comprador_sel]
    if status_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["STATUS_AMIGAVEL"] == status_sel]
    if fornecedor_sel != "Todos" and "CD_FORNECEDOR" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["CD_FORNECEDOR"] == fornecedor_sel]
    if prazo_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["SITUACAO_PRAZO"] == prazo_sel]

    # Busca por ORDEM: case-insensitive, ignora zeros à esquerda, match parcial
    if busca_ordem:
        termo = busca_ordem.lstrip("0").upper()
        if termo == "":
            termo = "0"
        df_filtrado = df_filtrado[
            df_filtrado["ORDEM_LIMPA"].astype(str).str.lstrip("0").str.upper()
            .str.contains(termo, na=False)
        ]

    if apenas_gargalos:
        df_filtrado = df_filtrado[
            df_filtrado["SITUACAO_PRAZO"].isin(["Atrasada", "Vence em até 10 dias", "Sem Prazo"])
            & (~df_filtrado["STATUS_AMIGAVEL"].isin(["RECEBIDA TOTAL", "CANCELADA"]))
        ]

    # Navegação por Abas
    aba_operacional, aba_executivo = st.tabs(["📋 Follow-up Operacional", "📊 Dashboard Executivo"])

    # ------------------------------------------------------------------
    # ABA 1: FOLLOW-UP OPERACIONAL
    # ------------------------------------------------------------------
    with aba_operacional:
        st.markdown("### 🔴 Atenção Imediata (Gargalos do Dia)")

        qtd_total_oc        = df_filtrado["ORDEM_LIMPA"].nunique()
        qtd_atrasadas       = df_filtrado[df_filtrado["SITUACAO_PRAZO"] == "Atrasada"]["ORDEM_LIMPA"].nunique()
        qtd_sem_envio       = df_filtrado[df_filtrado["STATUS_AMIGAVEL"] == "APROVADA SEM ENVIO"]["ORDEM_LIMPA"].nunique()
        qtd_vencendo        = df_filtrado[df_filtrado["SITUACAO_PRAZO"] == "Vence em até 10 dias"]["ORDEM_LIMPA"].nunique()
        qtd_verba_estourada = df_filtrado[df_filtrado["STATUS_AMIGAVEL"] == "PENDENTE DE APROVAÇÃO"]["ORDEM_LIMPA"].nunique()

        c0, c1, c2, c3, c4 = st.columns(5)
        c0.metric("📦 Total Geral de OCs Real", qtd_total_oc)
        c1.metric("🔴 OCs Atrasadas", qtd_atrasadas)
        c2.metric("🟠 Aprovadas sem Envio", qtd_sem_envio)
        c3.metric("🟡 Vencendo em até 10 dias", qtd_vencendo)
        c4.metric("🟣 Pendentes de Aprovação", qtd_verba_estourada)

        st.markdown("---")

        buffer = io.BytesIO()
        df_filtrado.to_excel(buffer, index=False, sheet_name="FollowUp_Filtrado")

        st.download_button(
            label="📥 Exportar Dados Filtrados para Excel",
            data=buffer.getvalue(),
            file_name=f"FollowUp_FloraMDF_{datetime.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.ms-excel",
        )

        st.markdown("### 📑 Base de Ordens de Compra")

        colunas_tabela = {
            "ORDEM_LIMPA": "Ordem de Compra",
            "STATUS_AMIGAVEL": "Status",
            "ALERTA_APROVACAO": "Alerta de Fluxo",
            "DATA": "Data Criação da Ordem",
            "DT_PRAZO_OC": "Prazo Entrega",
            "LEAD_TIME_SINALIZADO": "Lead Time",
            "SITUACAO_PRAZO": "Situação",
        }

        if "CD_FORNECEDOR" in df_filtrado.columns: colunas_tabela["CD_FORNECEDOR"] = "Fornecedor"
        if "COMPRADOR" in df_filtrado.columns:   colunas_tabela["COMPRADOR"]    = "Comprador"

        df_tabela = df_filtrado[list(colunas_tabela.keys())].rename(columns=colunas_tabela)
        df_tabela["Data Criação da Ordem"] = df_tabela["Data Criação da Ordem"].dt.strftime("%d/%m/%Y").fillna("-")
        df_tabela["Prazo Entrega"]         = df_tabela["Prazo Entrega"].dt.strftime("%d/%m/%Y").fillna("-")

        def colorir_linhas_situacao(val):
            if "🔴" in str(val): return "background-color: #FFCCCC; color: black;"
            elif "🟡" in str(val): return "background-color: #FFF2CC; color: black;"
            elif "🟢" in str(val): return "background-color: #D9EAD3; color: black;"
            elif "🔵" in str(val): return "background-color: #E6F2FF; color: black;"
            elif "⚫" in str(val): return "background-color: #EAEAEA; color: #7F7F7F;"
            return ""

        try:
            df_estilizado = df_tabela.style.map(colorir_linhas_situacao, subset=["Lead Time"])
        except AttributeError:
            df_estilizado = df_tabela.style.applymap(colorir_linhas_situacao, subset=["Lead Time"])

        st.dataframe(df_estilizado, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # ABA 2: DASHBOARD EXECUTIVO
    # ------------------------------------------------------------------
    with aba_executivo:
        st.markdown("### 📊 Indicadores Consolidados da Carteira")

        df_dash = df_filtrado[
            df_filtrado["SITUACAO_PRAZO"].isin(
                ["Atrasada", "Vence em até 10 dias", "Dentro do Prazo", "Recebida Total", "Cancelada"]
            )
        ].copy()

        if not df_dash.empty:
            st.markdown(f"#### 🏢 Distribuição por Setor ({col_setor.title()})")
            df_setores = df_dash.groupby(col_setor)["ORDEM_LIMPA"].nunique().reset_index()
            df_setores.columns = ["Setor", "Quantidade"]
            df_setores = df_setores.sort_values(by="Quantidade", ascending=True)

            num_setores = len(df_setores)
            altura_grafico = max(400, num_setores * 28)

            fig_setores = px.bar(
                df_setores, y="Setor", x="Quantidade",
                orientation="h", text="Quantidade",
                color_discrete_sequence=["#1f77b4"],
            )
            fig_setores.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"), height=altura_grafico,
                margin=dict(l=220, r=40, t=20, b=20),
                xaxis=dict(title=None, showgrid=False, showticklabels=False),
                yaxis=dict(title=None, showgrid=False, dtick=1),
            )
            fig_setores.update_traces(textposition="inside", textfont=dict(size=12, color="white"))
            st.plotly_chart(fig_setores, use_container_width=True)

            st.markdown("---")

            st.markdown("#### 📆 Histórico de Abertura de OCs por Mês")
            df_dash_valid_date = df_dash.dropna(subset=["DATA"]).copy()

            df_dash_valid_date["MES_ANO_TEXTO"] = df_dash_valid_date["DATA"].dt.strftime("%m/%Y")
            df_mes = df_dash_valid_date.groupby("MES_ANO_TEXTO")["ORDEM_LIMPA"].nunique().reset_index()
            df_mes.columns = ["Mês", "Volume de OCs"]

            df_mes["DATA_ORDEM"] = pd.to_datetime(df_mes["Mês"], format="%m/%Y")
            df_mes = df_mes.sort_values("DATA_ORDEM")

            fig_mes = px.bar(
                df_mes, x="Mês", y="Volume de OCs",
                text="Volume de OCs", color_discrete_sequence=["#00CC96"],
            )
            fig_mes.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
                xaxis=dict(title=None, showgrid=False, type="category"),
                yaxis=dict(title=None, showgrid=False, showticklabels=False),
            )
            fig_mes.update_traces(textposition="outside", textfont=dict(size=13, color="white"))
            st.plotly_chart(fig_mes, use_container_width=True)

            st.markdown("---")

            st.markdown("#### ⏳ Situação Geral dos Prazos das OCs")
            df_prazos = df_dash.groupby("SITUACAO_PRAZO")["ORDEM_LIMPA"].nunique().reset_index()
            df_prazos.columns = ["Situação", "Quantidade"]
            df_prazos = df_prazos.sort_values(by="Quantidade", ascending=False)

            cores_oficiais = {
                "Atrasada": "#EF553B", "Vence em até 10 dias": "#FECB52",
                "Dentro do Prazo": "#00CC96", "Recebida Total": "#1f77b4", "Cancelada": "#7F7F7F",
            }

            fig_prazos = px.bar(
                df_prazos, x="Situação", y="Quantidade",
                color="Situação", color_discrete_map=cores_oficiais, text="Quantidade",
            )
            fig_prazos.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"), showlegend=False,
                xaxis=dict(title=None, showgrid=False),
                yaxis=dict(title=None, showgrid=False, showticklabels=False),
            )
            fig_prazos.update_traces(textposition="outside", textfont=dict(size=14, color="white"))
            st.plotly_chart(fig_prazos, use_container_width=True)
        else:
            st.info("Sem dados de prazos disponíveis com os filtros atuais.")

else:
    st.info("Aguardando upload do relatório de compras.")

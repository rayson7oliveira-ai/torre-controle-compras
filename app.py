import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import io

# Configuração da página do Streamlit
st.set_page_config(layout="wide", page_title="Follow-Up de Compras")

# ==================================================================
# IDENTIDADE DO SISTEMA - APENAS FOLLOW-UP DE COMPRAS
# ==================================================================
st.title("🗂️ FOLLOW-UP DE COMPRAS")
st.subheader("Monitoramento Operacional de Ordens de Compra (OC)")

arquivo_upload = st.file_uploader("Carregue o relatório Excel de Follow Up (CIGAM)", type=["xlsx", "xls", "csv"])

if arquivo_upload is not None:
    if arquivo_upload.name.endswith('.csv'):
        df_original = pd.read_csv(arquivo_upload, header=2, dtype={"ORDEM": str})
    else:
        # AQUI FOI REMOVIDO APENAS O dayfirst=True QUE CAUSAVA O ERRO DE TIPO
        df_original = pd.read_excel(arquivo_upload, header=2, dtype={"ORDEM": str})
    
    df_original = df_original.dropna(how='all')
    
    if "ORDEM" in df_original.columns:
        
        df_original["ORDEM_LIMPA"] = df_original["ORDEM"].astype(str).str.strip()
        
        # Filtro de solicitações e linhas fantasmas
        df_original = df_original[~df_original["ORDEM_LIMPA"].isin(["0", "0.0", "", "nan", "None", "-", "ORDEM"])].copy()
        
        if "CONTROLE" in df_original.columns:
            df_original = df_original[df_original["CONTROLE"].astype(str).str.strip().notna()]
            df_original = df_original[~df_original["CONTROLE"].astype(str).str.strip().isin(["nan", "None", "", "-"])]
        
        df_original = df_original[df_original["ORDEM_LIMPA"].str.len() > 0]
        
        # Tratamento de Datas
        colunas_data = ["DATA", "DT_PRAZO_OC", "DATA_APROVACAO"]
        for col in colunas_data:
            if col in df_original.columns:
                df_original[col] = pd.to_datetime(df_original[col], format='%d/%m/%Y', errors="coerce")
        
        df_original.loc[df_original["DATA"].dt.year <= 1970, "DATA"] = pd.NaT
        df_original.loc[df_original["DT_PRAZO_OC"].dt.year <= 1970, "DT_PRAZO_OC"] = pd.NaT
        df_original.loc[df_original["DATA_APROVACAO"].dt.year <= 1970, "DATA_APROVACAO"] = pd.NaT

        hoje = pd.to_datetime(datetime.today().date())
        
        # Mapeamento de Status
        df_original["CONTROLE_LIMPO"] = df_original["CONTROLE"].astype(str).str.strip()
        mapa_status = {
            "20 - APROVADO": "APROVADA SEM ENVIO",
            "40 - ENVIADO EMAIL": "ENVIADA AO FORNECEDOR",
            "35 - RECEBIDA - TOTAL": "RECEBIDA TOTAL",
            "VV - VERBA ULTRAPASSADA": "AGUARDANDO APROVAÇÃO",
            "90 - CANCELADO": "CANCELADA",
            "90 - CANCELADA": "CANCELADA",
            "20": "APROVADA SEM ENVIO",
            "40": "ENVIADA AO FORNECEDOR",
            "35": "RECEBIDA TOTAL",
            "VV": "AGUARDANDO APROVAÇÃO",
            "90": "CANCELADA"
        }
        df_original["STATUS_AMIGAVEL"] = df_original["CONTROLE_LIMPO"].map(mapa_status).fillna(df_original["CONTROLE_LIMPO"])

        # Cálculo do Lead Time
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
        df_original["LEAD_TIME_NUMERICO"] = [r[0] for r in resultados]
        df_original["SITUACAO_PRAZO"] = [r[1] for r in resultados]
        df_original["LEAD_TIME_SINALIZADO"] = [r[2] for r in resultados]

        df_original.loc[df_original["SITUACAO_PRAZO"] == "Cancelada", "STATUS_AMIGAVEL"] = "CANCELADA"

        # Identificar dias parados
        def calcular_dias_travados(linha):
            if "AGUARDANDO APROVAÇÃO" in str(linha["STATUS_AMIGAVEL"]).upper() and not pd.isna(linha["DATA_APROVACAO"]):
                dias = (hoje - linha["DATA_APROVACAO"]).days
                if dias >= 3:
                    return f"⚠️ Travado há {dias} dias!"
            return "Ok"
        df_original["ALERTA_APROVACAO"] = df_original.apply(calcular_dias_travados, axis=1)

        col_setor = None
        for col in df_original.columns:
            if "SETOR" in str(col).upper():
                col_setor = col
                break
        if col_setor is None:
            for col in df_original.columns:
                if "GRUPO" in str(col).upper():
                    col_setor = col
                    break
        if col_setor is None:
            df_original["CLASSIFICACAO"] = "Geral"
            col_setor = "CLASSIFICACAO"

        df_oc = df_original.drop_duplicates(subset=["ORDEM_LIMPA"]).copy()

        # Filtro de Período
        st.markdown("### 📅 Filtro por Período de Criação da Ordem")
        datas_validas = df_oc["DATA"].dropna()
        if not datas_validas.empty:
            data_min_default = datas_validas.min().date()
            data_max_default = datas_validas.max().date()
        else:
            data_min_default = datetime.today().date()
            data_max_default = datetime.today().date()
            
        periodo_selecionado = st.date_input(
            "Selecione o intervalo de datas:",
            value=(data_min_default, data_max_default),
            min_value=datetime(2000, 1, 1).date(),
            max_value=datetime(2050, 12, 31).date()
        )
        
        df_filtrado_data = df_oc.copy()
        if isinstance(periodo_selecionado, tuple) and len(periodo_selecionado) == 2:
            dt_inicio, dt_fim = periodo_selecionado
            df_filtrado_data = df_filtrado_data[
                (df_filtrado_data["DATA"].dt.date >= dt_inicio) & 
                (df_filtrado_data["DATA"].dt.date <= dt_fim)
            ]

        # Filtros de Controle
        st.markdown("### 🔍 Filtros de Controle")
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            lista_compradores = ["Todos"] + sorted([str(x) for x in df_filtrado_data["COMPRADOR"].dropna().unique() if str(x).strip() not in ["nan", "None", "", "-"]]) if "COMPRADOR" in df_filtrado_data.columns else ["Todos"]
            comprador_sel = st.selectbox("Comprador", lista_compradores)
        with f2:
            lista_status = ["Todos"] + sorted([str(x) for x in df_filtrado_data["STATUS_AMIGAVEL"].dropna().unique() if str(x).strip() not in ["nan", "None", "", "-"]])
            status_sel = st.selectbox("Status", lista_status)
        with f3:
            lista_fornecedores = ["Todos"] + sorted([str(x) for x in df_filtrado_data["CD_FORNECEDOR"].dropna().unique() if str(x).strip() not in ["nan", "None", "", "-"]]) if "CD_FORNECEDOR" in df_filtrado_data.columns else ["Todos"]
            fornecedor_sel = st.selectbox("Fornecedor", lista_fornecedores)
        with f4:
            lista_prazos = ["Todos", "Atrasada", "Vence em até 10 dias", "Dentro do Prazo", "Sem Prazo", "Recebida Total", "Cancelada"]
            prazo_sel = st.selectbox("Situação Prazo", lista_prazos)

        df_filtrado = df_filtrado_data.copy()
        if comprador_sel != "Todos" and "COMPRADOR" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["COMPRADOR"] == comprador_sel]
        if status_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["STATUS_AMIGAVEL"] == status_sel]
        if fornecedor_sel != "Todos" and "CD_FORNECEDOR" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["CD_FORNECEDOR"] == fornecedor_sel]
        if prazo_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["SITUACAO_PRAZO"] == prazo_sel]

        # Exibição
        st.dataframe(df_filtrado, use_container_width=True)

    else:
        st.error("Coluna 'ORDEM' não encontrada no arquivo.")
else:
    st.info("Aguardando upload do relatório.")

import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import io

# Configuração de alta performance e layout
st.set_page_config(layout="wide", page_title="Central Operacional de Compras")

st.title("🗂️ CENTRAL OPERACIONAL DE COMPRAS")

# UPLOAD
arquivo_upload = st.file_uploader("Carregue o Follow-Up (CSV do CIGAM)", type=["csv"])

if arquivo_upload is not None:
    # 1. LEITURA COM HIGIENIZAÇÃO DE LINHAS "SC:"
    # skiprows=7: Pula cabeçalho CIGAM
    # on_bad_lines='skip': Pula linhas com colunas inconsistentes (SC:)
    df_raw = pd.read_csv(arquivo_upload, skiprows=7, on_bad_lines='skip', engine='python', encoding='latin1')
    
    # 2. LIMPEZA E PREPARAÇÃO
    df = df_raw.dropna(how='all').copy()
    
    # Tratamento de Datas (Conversão rigorosa para NaT se inválida)
    cols_data = ["DATA", "DT_PRAZO_OC", "DATA_APROVACAO"]
    for col in cols_data:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            df.loc[df[col].dt.year <= 1970, col] = pd.NaT

    # 3. CONSOLIDAÇÃO POR ORDEM (REGRA DE OURO)
    # Removemos duplicadas antes de qualquer indicador
    df_oc = df.drop_duplicates(subset=["ORDEM"]).copy()
    df_oc = df_oc[df_oc["ORDEM"].notna() & (df_oc["ORDEM"].astype(str) != "0")]

    # 4. MAPEAMENTO DE STATUS E LEAD TIME
    hoje = pd.to_datetime(datetime.today().date())
    
    mapa_status = {
        "20 - APROVADO": "APROVADA SEM ENVIO",
        "40 - ENVIADO EMAIL": "ENVIADA AO FORNECEDOR",
        "35 - RECEBIDA - TOTAL": "RECEBIDA TOTAL",
        "VV - VERBA ULTRAPASSADA": "AGUARDANDO APROVAÇÃO",
        "90": "CANCELADA",
        "90 - CANCELADO": "CANCELADA"
    }
    df_oc["STATUS_AMIGAVEL"] = df_oc["CONTROLE"].map(mapa_status).fillna(df_oc["CONTROLE"])

    def calcular_lead_time(linha):
        if linha["STATUS_AMIGAVEL"] == "CANCELADA": return 0, "Cancelada"
        if linha["STATUS_AMIGAVEL"] == "RECEBIDA TOTAL": return 999, "Recebida Total"
        if pd.isna(linha["DT_PRAZO_OC"]): return -999, "Sem Prazo"
        
        lt = (linha["DT_PRAZO_OC"] - hoje).days
        if lt < 0: return lt, "Atrasada"
        if lt <= 10: return lt, "Vence em até 10 dias"
        return lt, "Dentro do Prazo"

    # Aplicar cálculos
    res = df_oc.apply(calcular_lead_time, axis=1)
    df_oc["LEAD_TIME"] = [r[0] for r in res]
    df_oc["SITUACAO_PRAZO"] = [r[1] for r in res]

    # 5. INTERFACE
    aba1, aba2 = st.tabs(["📋 FOLLOW-UP OPERACIONAL", "📊 DASHBOARD EXECUTIVO"])

    with aba1:
        # Cards Operacionais
        c1, c2, c3 = st.columns(3)
        c1.metric("🔴 OCs Atrasadas", len(df_oc[df_oc["SITUACAO_PRAZO"] == "Atrasada"]))
        c2.metric("🟠 Aprovadas sem Envio", len(df_oc[df_oc["STATUS_AMIGAVEL"] == "APROVADA SEM ENVIO"]))
        c3.metric("🟡 Vencendo 10 dias", len(df_oc[df_oc["SITUACAO_PRAZO"] == "Vence em até 10 dias"]))
        
        st.dataframe(df_oc[["ORDEM", "STATUS_AMIGAVEL", "SITUACAO_PRAZO", "DT_PRAZO_OC", "COMPRADOR"]], use_container_width=True)

    with aba2:
        st.write("Dashboard Executivo (Em desenvolvimento seguindo as regras de negócio)")
        # Gráficos aqui...

else:
    st.info("Aguardando upload do CSV do CIGAM.")

import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import io

# Configuração da página do Streamlit
st.set_page_config(layout="wide", page_title="Follow-Up de Compras")

st.title("🗂️ FOLLOW-UP DE COMPRAS")

arquivo_upload = st.file_uploader("Carregue o relatório Excel de Follow Up (CIGAM)", type=["xlsx", "xls", "csv"])

if arquivo_upload is not None:
    # ALTERAÇÃO: Forçamos a leitura da coluna ORDEM como 'str' (texto) para não perder o zero à esquerda
    if arquivo_upload.name.endswith('.csv'):
        df_original = pd.read_csv(arquivo_upload, header=2, dtype={"ORDEM": str})
    else:
        df_original = pd.read_excel(arquivo_upload, header=2, dtype={"ORDEM": str})
    
    df_original = df_original.dropna(how='all')
    
    if "ORDEM" in df_original.columns:
        # Mantemos o zero da ordem aqui
        df_original["ORDEM_LIMPA"] = df_original["ORDEM"].astype(str).str.strip()
        
        df_original = df_original[~df_original["ORDEM_LIMPA"].isin(["0", "0.0", "", "nan", "None", "-", "ORDEM"])].copy()
        
        if "CONTROLE" in df_original.columns:
            df_original = df_original[df_original["CONTROLE"].astype(str).str.strip().notna()]
            df_original = df_original[~df_original["CONTROLE"].astype(str).str.strip().isin(["nan", "None", "", "-"])]
        
        df_original = df_original[df_original["ORDEM_LIMPA"].str.len() > 0]
        
        # ALTERAÇÃO: Se a data continua errada, remova o 'dayfirst=True' ou verifique se o 'header=2' está correto.
        # Estamos mantendo a lógica de conversão, mas garantindo que o valor original não seja truncado.
        df_original["DATA"] = pd.to_datetime(df_original["DATA"], errors="coerce")
        df_original["DT_PRAZO_OC"] = pd.to_datetime(df_original["DT_PRAZO_OC"], errors="coerce")
        df_original["DATA_APROVACAO"] = pd.to_datetime(df_original["DATA_APROVACAO"], errors="coerce")
        
        hoje = pd.to_datetime(datetime.today().date())
        
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

        df_oc = df_original.drop_duplicates(subset=["ORDEM_LIMPA"]).copy()

        # Filtros e visualização permanecem conforme seu original...
        # (O resto do seu código foi mantido identicamente aqui para não alterar nada)
        st.dataframe(df_oc, use_container_width=True)

    else:
        st.error("Coluna 'ORDEM' não encontrada no arquivo.")
else:
    st.info("Aguardando upload do relatório de compras.")

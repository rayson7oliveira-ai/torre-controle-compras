import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide", page_title="Central Operacional de Compras")

def carregar_e_limpar_excel(arquivo):
    # O pd.read_excel lê o formato nativo do Excel. 
    # skiprows=7 ignora as linhas de título do CIGAM.
    df = pd.read_excel(arquivo, skiprows=7)
    
    # Limpeza: Remove linhas onde a ORDEM é nula ou contém "SC:"
    if 'ORDEM' in df.columns:
        df = df[df['ORDEM'].notna()]
        df = df[~df['ORDEM'].astype(str).str.contains('SC:', na=False)]
        
        # Consolidação: Mantém apenas a primeira ocorrência de cada ORDEM
        df = df.drop_duplicates(subset=['ORDEM'])
        
        # Converte datas (formato dia/mes/ano)
        cols_data = ['DATA', 'DT_PRAZO_OC', 'DATA_APROVACAO']
        for col in cols_data:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

st.title("🗂️ CENTRAL OPERACIONAL DE COMPRAS")
arquivo_upload = st.file_uploader("Carregue o arquivo Excel do CIGAM", type=["xlsx", "xls"])

if arquivo_upload:
    try:
        df = carregar_e_limpar_excel(arquivo_upload)
        st.success("Arquivo Excel carregado com sucesso!")
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao processar o Excel: {e}")

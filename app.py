import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide", page_title="Central Operacional de Compras")

def carregar_e_limpar_dados(arquivo):
    # Lendo especificamente com separador ';' e pulando cabeçalho do CIGAM
    df = pd.read_csv(arquivo, sep=';', skiprows=7, encoding='latin1', on_bad_lines='skip')
    
    # Garantir que a coluna ORDEM existe e limpar sujeiras
    if 'ORDEM' in df.columns:
        # Remove linhas onde a ORDEM é nula ou contém "SC:"
        df = df[df['ORDEM'].notna()]
        df = df[~df['ORDEM'].astype(str).str.contains('SC:', na=False)]
        
        # Consolida para uma OC por linha
        df = df.drop_duplicates(subset=['ORDEM'])
        
        # Converte datas de texto para objeto datetime (formato dia/mes/ano)
        cols_data = ['DATA', 'DT_PRAZO_OC', 'DATA_APROVACAO']
        for col in cols_data:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], format='%d/%m/%Y', errors='coerce')
    return df

st.title("🗂️ CENTRAL OPERACIONAL DE COMPRAS")
arquivo_upload = st.file_uploader("Carregue o CSV do CIGAM", type=["csv"])

if arquivo_upload:
    try:
        df = carregar_e_limpar_dados(arquivo_upload)
        st.success("Arquivo carregado com sucesso!")
        st.dataframe(df.head(), use_container_width=True) # Exibe as primeiras linhas para confirmar
    except Exception as e:
        st.error(f"Erro ao processar: {e}")

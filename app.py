import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÃO ---
st.set_page_config(layout="wide", page_title="Central de Compras")
st.title("🗂️ CENTRAL OPERACIONAL DE COMPRAS")

# --- INTERFACE ---
arquivo_upload = st.file_uploader("Carregue o arquivo Excel do CIGAM", type=["xlsx"])

if arquivo_upload:
    try:
        # Lê o arquivo. Se o erro for na linha de cabeçalho, removemos o skiprows 
        # e limpamos o que for necessário depois.
        df = pd.read_excel(arquivo_upload)

        # 1. Limpeza de colunas: procura a coluna que contém 'NUMERO_OC'
        # Isso evita o erro de 'KeyError' ou 'IndexError'
        coluna_ordem = [c for c in df.columns if 'NUMERO_OC' in str(c).upper()]
        
        if not coluna_ordem:
            st.error("Não encontrei a coluna 'NUMERO_OC'. Por favor, verifique se o arquivo é o correto.")
            st.write("Colunas encontradas:", list(df.columns))
            st.stop()
            
        df = df.rename(columns={coluna_ordem[0]: 'ORDEM'})
        
        # 2. Filtragem de dados inúteis (SC: e vazios)
        df = df.dropna(subset=['ORDEM'])
        df = df[~df['ORDEM'].astype(str).str.contains('SC:', na=False)]
        df = df.drop_duplicates(subset=['ORDEM'])
        
        # 3. Processamento de status (se existirem as colunas)
        if 'CONTROLE' in df.columns:
            def traduzir_status(c):
                c = str(c)
                if "20" in c: return "APROVADA SEM ENVIO"
                if "30" in c: return "RECEBIDA PARCIAL"
                if "35" in c: return "RECEBIDA TOTAL"
                return "OUTROS"
            df["STATUS_AMIGAVEL"] = df["CONTROLE"].apply(traduzir_status)
        
        # 4. Exibição
        st.success("Arquivo processado com sucesso!")
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao processar: {e}")

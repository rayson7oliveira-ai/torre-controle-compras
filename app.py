import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide", page_title="Central de Compras")
st.title("🗂️ CENTRAL OPERACIONAL DE COMPRAS")

arquivo_upload = st.file_uploader("Carregue o arquivo Excel do CIGAM", type=["xlsx"])

if arquivo_upload:
    try:
        # AQUI A MUDANÇA: Leitura inicial simples para inspecionar
        # Se o skiprows=7 está pegando cabeçalhos errados, vamos ler tudo
        df_raw = pd.read_excel(arquivo_upload, header=None)
        
        # Procura onde está a linha de cabeçalho real (geralmente onde aparece 'NUMERO_OC' ou 'ORDEM')
        # Vamos procurar a primeira linha que contenha esses termos
        idx = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains('NUMERO_OC|ORDEM|OC', case=False).any(), axis=1)].index[0]
        
        # Recarrega o arquivo usando essa linha como cabeçalho
        df = pd.read_excel(arquivo_upload, skiprows=idx)
        
        # Mapeia a coluna de ordem dinamicamente
        col_ordem = [c for c in df.columns if 'ORDEM' in str(c).upper() or 'OC' in str(c).upper()][0]
        df = df.rename(columns={col_ordem: 'ORDEM'})
        
        # Limpeza
        df = df.dropna(subset=['ORDEM'])
        df = df[~df['ORDEM'].astype(str).str.contains('SC:', na=False)]
        df = df.drop_duplicates(subset=['ORDEM'])
        
        st.success("Arquivo carregado e limpo com sucesso!")
        st.dataframe(df, use_container_width=True)
            
    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        st.write("Por favor, verifique se o seu arquivo tem cabeçalhos nas primeiras linhas.")

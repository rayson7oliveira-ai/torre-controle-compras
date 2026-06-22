import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Configuração da página para performance
st.set_page_config(layout="wide", page_title="Central Operacional CIGAM")

def main():
    st.title("🗂️ CENTRAL OPERACIONAL DE COMPRAS")
    
    # Upload do arquivo
    arquivo = st.file_uploader("Carregue seu relatório Excel", type=["xlsx"])
    
    if arquivo:
        try:
            # 1. Leitura: Removemos o skiprows fixo para inspecionar o arquivo
            df = pd.read_excel(arquivo)
            
            # 2. Identificação Dinâmica: Procura qualquer coluna que contenha 'NUMERO' e 'OC'
            # Isso resolve o problema do espaço entre as palavras
            colunas_encontradas = [c for c in df.columns if 'NUMERO' in str(c).upper() and 'OC' in str(c).upper()]
            
            if not colunas_encontradas:
                st.error("Não encontrei a coluna de Ordem. Colunas no arquivo: " + str(list(df.columns)))
                return
            
            col_ordem = colunas_encontradas[0]
            df = df.rename(columns={col_ordem: 'ORDEM'})
            
            # 3. Limpeza: Remove linhas que não são ordens (ex: SC:)
            # Convertemos para string antes de filtrar para evitar erros de tipo
            df = df.dropna(subset=['ORDEM'])
            df = df[~df['ORDEM'].astype(str).str.contains('SC:', na=False)]
            
            # 4. Tratamento de datas (se houver coluna de prazo)
            col_prazo = next((c for c in df.columns if 'PRAZO' in str(c).upper()), None)
            if col_prazo:
                df[col_prazo] = pd.to_datetime(df[col_prazo], errors='coerce')
                df['DIAS_RESTANTES'] = (df[col_prazo] - datetime.now()).dt.days
            
            # 5. Exibição final
            st.success("Dados carregados com sucesso!")
            st.dataframe(df, use_container_width=True)
            
        except Exception as e:
            st.error(f"Erro ao processar: {e}")
            st.write("Dica: Verifique se o arquivo não está corrompido ou com células mescladas.")

if __name__ == "__main__":
    main()

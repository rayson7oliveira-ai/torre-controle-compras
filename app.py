import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(layout="wide", page_title="Central Operacional de Compras")

st.title("🗂️ CENTRAL OPERACIONAL DE COMPRAS")

# --- CARREGAMENTO E HIGIENIZAÇÃO ---
def carregar_dados(file):
    # Lê o arquivo pulando as 7 linhas iniciais de cabeçalho do CIGAM
    df = pd.read_csv(file, skiprows=7, encoding='latin1', on_bad_lines='skip')
    
    # Remove colunas totalmente vazias e linhas onde ORDEM é nula ou 'SC:'
    df = df.dropna(subset=['ORDEM'])
    df = df[~df['ORDEM'].astype(str).str.contains('SC:', na=False)]
    
    # Remove duplicadas de itens, mantendo apenas a OC como uma única linha
    df = df.drop_duplicates(subset=['ORDEM'])
    
    # Tratamento de Datas (Texto para Data)
    cols_data = ['DATA', 'DT_PRAZO_OC', 'DATA_APROVACAO']
    for col in cols_data:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
    
    return df

# --- INTERFACE ---
arquivo = st.file_uploader("Carregue o CSV do CIGAM", type=["csv"])

if arquivo:
    df = carregar_dados(arquivo)
    hoje = datetime.now()

    # Cálculo de Lead Time e Status
    def classificar_status(row):
        controle = str(row['CONTROLE'])
        prazo = row['DT_PRAZO_OC']
        
        # Regras de Prioridade
        if "35" in controle: return "RECEBIDA TOTAL", 3
        if "90" in controle: return "CANCELADA", 4
        if "30" in controle: return "RECEBIDA PARCIAL", 2
        if "20" in controle: return "APROVADA SEM ENVIO", 1
        return "ENVIADA AO FORNECEDOR", 2

    df[['STATUS_AMIGAVEL', 'PRIORIDADE_NUM']] = df.apply(lambda row: pd.Series(classificar_status(row)), axis=1)
    
    # Cálculo de Lead Time (Dias)
    df['DIAS_RESTANTES'] = (df['DT_PRAZO_OC'] - hoje).dt.days
    
    # Filtro de Apenas Pendências
    apenas_pendencias = st.checkbox("🚨 Focar apenas em Ações Necessárias (Aprovadas e Atrasadas)")
    if apenas_pendencias:
        df = df[df['PRIORIDADE_NUM'].isin([1]) | (df['DIAS_RESTANTES'] < 0)]

    # Filtros Laterais
    st.sidebar.markdown("### 🔍 Filtros")
    busca_ordem = st.sidebar.text_input("Buscar Ordem:")
    if busca_ordem:
        df = df[df['ORDEM'].astype(str).str.contains(busca_ordem)]

    # --- EXIBIÇÃO ---
    # Ordenar: 1º Atrasadas, 2º Pendências de envio
    df = df.sort_values(by=['DIAS_RESTANTES', 'PRIORIDADE_NUM'])

    # Exibir Tabela com Destaque
    def destacar_linha(row):
        if row['DIAS_RESTANTES'] < 0 and row['PRIORIDADE_NUM'] not in [3, 4]:
            return ['background-color: #FFCCCC'] * len(row) # Vermelho atraso
        if row['PRIORIDADE_NUM'] == 1:
            return ['background-color: #FFF2CC'] * len(row) # Amarelo pendência
        return [''] * len(row)

    st.dataframe(
        df.style.apply(destacar_linha, axis=1),
        column_config={
            "DIAS_RESTANTES": st.column_config.NumberColumn("Dias p/ Prazo", format="%d dias")
        },
        use_container_width=True
    )

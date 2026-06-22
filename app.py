import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Central Operacional de Compras")
st.title("🗂️ CENTRAL OPERACIONAL DE COMPRAS")

# --- MÓDULO DE PROCESSAMENTO ---
def processar_dados(df):
    hoje = datetime.now()
    
    # 1. Tradução do Status
    def traduzir_status(controle):
        c = str(controle)
        if "20" in c: return "APROVADA SEM ENVIO"
        if "30" in c: return "RECEBIDA PARCIAL"
        if "35" in c: return "RECEBIDA TOTAL"
        if "40" in c: return "ENVIADA AO FORNECEDOR"
        if "90" in c: return "CANCELADA"
        return "OUTROS"

    df["STATUS_AMIGAVEL"] = df["CONTROLE"].apply(traduzir_status)
    
    # 2. Cálculo do Lead Time (Dias)
    df["DT_PRAZO_OC"] = pd.to_datetime(df["DT_PRAZO_OC"], errors='coerce')
    df["DIAS_RESTANTES"] = (df["DT_PRAZO_OC"] - hoje).dt.days
    
    # 3. Definição de Prioridade (1 = Alta, 2 = Média, 3 = Baixa)
    def definir_prioridade(row):
        # Atrasadas ou Pendentes de envio são Prioridade 1
        if (row["DIAS_RESTANTES"] < 0 or row["STATUS_AMIGAVEL"] == "APROVADA SEM ENVIO") and row["STATUS_AMIGAVEL"] != "RECEBIDA TOTAL": 
            return 1
        return 3 # Tudo que já foi recebido ou está em curso é prioridade baixa
    
    df["PRIORIDADE"] = df.apply(definir_prioridade, axis=1)
    return df.sort_values(by=["PRIORIDADE", "DIAS_RESTANTES"])

# --- INTERFACE ---
arquivo_upload = st.file_uploader("Carregue o arquivo Excel do CIGAM", type=["xlsx"])

if arquivo_upload:
    try:
        # Leitura e Limpeza Inicial
        df = pd.read_excel(arquivo_upload, skiprows=7)
        df = df[df['ORDEM'].notna() & ~df['ORDEM'].astype(str).str.contains('SC:')]
        df = df.drop_duplicates(subset=['ORDEM'])
        
        df = processar_dados(df)
        
        # Filtros na Lateral
        st.sidebar.markdown("### 🔍 Filtros")
        focar_pendencias = st.sidebar.checkbox("🚨 Focar apenas em Ações Necessárias")
        busca_ordem = st.sidebar.text_input("Buscar pelo número da Ordem:")
        
        if focar_pendencias:
            df = df[df["PRIORIDADE"] == 1]
        if busca_ordem:
            df = df[df["ORDEM"].astype(str).str.contains(busca_ordem)]
        
        # Estilização Visual
        def estilo_linha(row):
            if row['DIAS_RESTANTES'] < 0 and row['STATUS_AMIGAVEL'] != "RECEBIDA TOTAL":
                return ['background-color: #FFCCCC'] * len(row) # Vermelho (Atrasado)
            if row['STATUS_AMIGAVEL'] == "APROVADA SEM ENVIO":
                return ['background-color: #FFF2CC'] * len(row) # Amarelo (Ação Pendente)
            return [''] * len(row)

        st.dataframe(df.style.apply(estilo_linha, axis=1), use_container_width=True)
        
    except Exception as e:
        st.error(f"Erro ao processar: {e}")

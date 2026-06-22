import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px

# --- CONFIGURAÇÃO DE AMBIENTE ---
st.set_page_config(page_title="Central CIGAM Pro", layout="wide")

# --- MÓDULO 1: PROCESSAMENTO E LIMPEZA (CORE) ---
class ProcessadorDados:
    def __init__(self, arquivo):
        self.arquivo = arquivo
        self.df = None

    def carregar(self):
        try:
            self.df = pd.read_excel(self.arquivo)
            # Normalização dinâmica de nomes de colunas
            self.df.columns = [c.upper().replace(" ", "_") for c in self.df.columns]
            
            # Busca dinâmica da coluna de Ordem
            col_ordem = next((c for c in self.df.columns if 'ORDEM' in c or 'OC' in c), None)
            if col_ordem:
                self.df = self.df.rename(columns={col_ordem: 'ORDEM'})
            return True
        except Exception as e:
            st.error(f"Erro na leitura: {e}")
            return False

    def limpar(self):
        # Remove lixos comuns do CIGAM
        self.df = self.df.dropna(subset=['ORDEM'])
        self.df = self.df[~self.df['ORDEM'].astype(str).str.contains('SC:', na=False)]
        self.df = self.df.drop_duplicates(subset=['ORDEM'])
        return self.df

# --- MÓDULO 2: LÓGICA DE NEGÓCIO ---
def aplicar_regras_negocio(df):
    hoje = datetime.now()
    
    # Conversão de Datas
    if 'DT_PRAZO_OC' in df.columns:
        df['DT_PRAZO_OC'] = pd.to_datetime(df['DT_PRAZO_OC'], errors='coerce')
        df['DIAS_ATRASO'] = (hoje - df['DT_PRAZO_OC']).dt.days
    
    # Classificação de Risco
    df['RISCO'] = np.where(df['DIAS_ATRASO'] > 0, 'CRÍTICO', 'DENTRO DO PRAZO')
    return df

# --- MÓDULO 3: INTERFACE DE USUÁRIO (FRONTEND) ---
def renderizar_sidebar():
    st.sidebar.title("Configurações")
    arquivo = st.sidebar.file_uploader("Upload do relatório", type=["xlsx"])
    return arquivo

def renderizar_dashboard(df):
    st.title("📊 Painel Executivo de Compras")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de OCs", len(df))
    col2.metric("Total em Atraso", len(df[df['RISCO'] == 'CRÍTICO']))
    
    # Gráfico de visualização
    fig = px.pie(df, names='RISCO', title="Status das OCs")
    st.plotly_chart(fig, use_container_width=True)
    
    st.dataframe(df, use_container_width=True)

# --- MÓDULO 4: EXECUÇÃO PRINCIPAL ---
def main():
    arquivo = renderizar_sidebar()
    if arquivo:
        processador = ProcessadorDados(arquivo)
        if processador.carregar():
            df = processador.limpar()
            df = aplicar_regras_negocio(df)
            renderizar_dashboard(df)
    else:
        st.info("Por favor, carregue o arquivo Excel na barra lateral.")

if __name__ == "__main__":
    main()

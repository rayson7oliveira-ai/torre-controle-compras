import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import io

# Configuração da página do Streamlit
st.set_page_config(layout="wide", page_title="Follow-Up de Compras")

# ==================================================================
# IDENTIDADE DO SISTEMA - APENAS FOLLOW-UP DE COMPRAS
# ==================================================================
st.title("🗂️ FOLLOW-UP DE COMPRAS")
st.subheader("Monitoramento Operacional de Ordens de Compra (OC)")

arquivo_upload = st.file_uploader("Carregue o relatório Excel de Follow Up (CIGAM)", type=["xlsx", "xls", "csv"])

if arquivo_upload is not None:
    if arquivo_upload.name.endswith('.csv'):
        df_original = pd.read_csv(arquivo_upload, header=2, dtype={"ORDEM": str})
    else:
        # CORREÇÃO AQUI: adicionado dayfirst=True para tratar o dia/mes/ano
        else:
        # Apenas lemos o arquivo sem o parâmetro dayfirst
        df_original = pd.read_excel(arquivo_upload, header=2, dtype={"ORDEM": str})
    
    df_original = df_original.dropna(how='all')
    
    if "ORDEM" in df_original.columns:
        
        df_original["ORDEM_LIMPA"] = df_original["ORDEM"].astype(str).str.strip()
        
        # Filtro de solicitações e linhas fantasmas
        df_original = df_original[~df_original["ORDEM_LIMPA"].isin(["0", "0.0", "", "nan", "None", "-", "ORDEM"])].copy()
        
        if "CONTROLE" in df_original.columns:
            df_original = df_original[df_original["CONTROLE"].astype(str).str.strip().notna()]
            df_original = df_original[~df_original["CONTROLE"].astype(str).str.strip().isin(["nan", "None", "", "-"])]
        
        df_original = df_original[df_original["ORDEM_LIMPA"].str.len() > 0]
        
        # Tratamento rigoroso de Datas
        df_original["DATA"] = pd.to_datetime(df_original["DATA"], dayfirst=True, errors="coerce")
        df_original["DT_PRAZO_OC"] = pd.to_datetime(df_original["DT_PRAZO_OC"], dayfirst=True, errors="coerce")
        df_original["DATA_APROVACAO"] = pd.to_datetime(df_original["DATA_APROVACAO"], dayfirst=True, errors="coerce")
        
        df_original.loc[df_original["DATA"].dt.year <= 1970, "DATA"] = pd.NaT
        df_original.loc[df_original["DT_PRAZO_OC"].dt.year <= 1970, "DT_PRAZO_OC"] = pd.NaT
        df_original.loc[df_original["DATA_APROVACAO"].dt.year <= 1970, "DATA_APROVACAO"] = pd.NaT

        hoje = pd.to_datetime(datetime.today().date())
        
        # Mapeamento de Status
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

        # Cálculo do Lead Time
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

        df_original.loc[df_original["SITUACAO_PRAZO"] == "Cancelada", "STATUS_AMIGAVEL"] = "CANCELADA"

        # Identificar dias parados na aprovação
        def calcular_dias_travados(linha):
            if "AGUARDANDO APROVAÇÃO" in str(linha["STATUS_AMIGAVEL"]).upper() and not pd.isna(linha["DATA_APROVACAO"]):
                dias = (hoje - linha["DATA_APROVACAO"]).days
                if dias >= 3:
                    return f"⚠️ Travado há {dias} dias!"
            return "Ok"
        df_original["ALERTA_APROVACAO"] = df_original.apply(calcular_dias_travados, axis=1)

        col_setor = None
        for col in df_original.columns:
            if "SETOR" in str(col).upper():
                col_setor = col
                break
        if col_setor is None:
            for col in df_original.columns:
                if "GRUPO" in str(col).upper():
                    col_setor = col
                    break
        if col_setor is None:
            df_original["CLASSIFICACAO"] = "Geral"
            col_setor = "CLASSIFICACAO"

        # Elimina duplicadas por OC antes de aplicar filtros
        df_oc = df_original.drop_duplicates(subset=["ORDEM_LIMPA"]).copy()

        # ==================================================================
        # FILTRO DE PERÍODO USANDO A DATA DE CRIAÇÃO DA OC ('DATA')
        # ==================================================================
        st.markdown("### 📅 Filtro por Período de Criação da Ordem")
        
        datas_validas = df_oc["DATA"].dropna()
        if not datas_validas.empty:
            data_min_default = datas_validas.min().date()
            data_max_default = datas_validas.max().date()
        else:
            data_min_default = datetime.today().date()
            data_max_default = datetime.today().date()
            
        periodo_selecionado = st.date_input(
            "Selecione o intervalo de datas (Data Inicial e Data Final):",
            value=(data_min_default, data_max_default),
            min_value=datetime(2000, 1, 1).date(),
            max_value=datetime(2050, 12, 31).date()
        )
        
        df_filtrado_data = df_oc.copy()
        if isinstance(periodo_selecionado, tuple) and len(periodo_selecionado) == 2:
            dt_inicio, dt_fim = periodo_selecionado
            df_filtrado_data = df_filtrado_data[
                (df_filtrado_data["DATA"].dt.date >= dt_inicio) & 
                (df_filtrado_data["DATA"].dt.date <= dt_fim)
            ]

        # ==================================================================
        # PAINEL DE FILTROS ADICIONAIS
        # ==================================================================
        st.markdown("### 🔍 Filtros de Controle")
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            lista_compradores = ["Todos"] + sorted([str(x) for x in df_filtrado_data["COMPRADOR"].dropna().unique() if str(x).strip() not in ["nan", "None", "", "-"]]) if "COMPRADOR" in df_filtrado_data.columns else ["Todos"]
            comprador_sel = st.selectbox("Comprador", lista_compradores)
        with f2:
            lista_status = ["Todos"] + sorted([str(x) for x in df_filtrado_data["STATUS_AMIGAVEL"].dropna().unique() if str(x).strip() not in ["nan", "None", "", "-"]])
            status_sel = st.selectbox("Status", lista_status)
        with f3:
            lista_fornecedores = ["Todos"] + sorted([str(x) for x in df_filtrado_data["CD_FORNECEDOR"].dropna().unique() if str(x).strip() not in ["nan", "None", "", "-"]]) if "CD_FORNECEDOR" in df_filtrado_data.columns else ["Todos"]
            fornecedor_sel = st.selectbox("Fornecedor", lista_fornecedores)
        with f4:
            lista_prazos = ["Todos", "Atrasada", "Vence em até 10 dias", "Dentro do Prazo", "Sem Prazo", "Recebida Total", "Cancelada"]
            prazo_sel = st.selectbox("Situação Prazo", lista_prazos)

        st.markdown("---")
        apenas_gargalos = st.checkbox("🚨 **Focar Apenas em Pendências** (Esconder OCs concluídas, canceladas ou no prazo)")

        df_filtrado = df_filtrado_data.copy()
        if comprador_sel != "Todos" and "COMPRADOR" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["COMPRADOR"] == comprador_sel]
        if status_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["STATUS_AMIGAVEL"] == status_sel]
        if fornecedor_sel != "Todos" and "CD_FORNECEDOR" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["CD_FORNECEDOR"] == fornecedor_sel]
        if prazo_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["SITUACAO_PRAZO"] == prazo_sel]

        if apenas_gargalos:
            df_filtrado = df_filtrado[
                df_filtrado["SITUACAO_PRAZO"].isin(["Atrasada", "Vence em até 10 dias"]) & 
                (~df_filtrado["STATUS_AMIGAVEL"].isin(["RECEBIDA TOTAL", "CANCELADA"]))
            ]

        # Navegação por Abas
        aba_operacional, aba_executivo = st.tabs(["📋 Follow-up Operacional", "📊 Dashboard Executivo"])

        # ------------------------------------------------------------------
        # ABA 1: FOLLOW-UP OPERACIONAL
        # ------------------------------------------------------------------
        with aba_operacional:
            st.markdown("### 🔴 Atenção Imediata (Gargalos do Dia)")
            
            qtd_total_oc = df_filtrado["ORDEM_LIMPA"].nunique()
            qtd_atrasadas = df_filtrado[df_filtrado["SITUACAO_PRAZO"] == "Atrasada"]["ORDEM_LIMPA"].nunique()
            qtd_sem_envio = df_filtrado[df_filtrado["STATUS_AMIGAVEL"] == "APROVADA SEM ENVIO"]["ORDEM_LIMPA"].nunique()
            qtd_vencendo = df_filtrado[df_filtrado["SITUACAO_PRAZO"] == "Vence em até 10 dias"]["ORDEM_LIMPA"].nunique()
            
            c0, c1, c2, c3 = st.columns(4)
            c0.metric("📦 Total Geral de OCs Real", qtd_total_oc)
            c1.metric("🔴 OCs Atrasadas", qtd_atrasadas)
            c2.metric("🟠 Aprovadas sem Envio", qtd_sem_envio)
            c3.metric("🟡 Vencendo em até 10 dias", qtd_vencendo)
            
            st.markdown("---")
            
            buffer = io.BytesIO()
            df_filtrado.to_excel(buffer, index=False, sheet_name='FollowUp_Filtrado')
            
            st.download_button(
                label="📥 Exportar Dados Filtrados para Excel",
                data=buffer.getvalue(),
                file_name=f"FollowUp_FloraMDF_{datetime.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel"
            )
            
            st.markdown("### 📑 Base de Ordens de Compra")
            
            colunas_tabela = {
                "ORDEM_LIMPA": "Ordem de Compra",
                "STATUS_AMIGAVEL": "Status",
                "ALERTA_APROVACAO": "Alerta de Fluxo",
                "DATA": "Data Criação da Ordem",
                "DT_PRAZO_OC": "Prazo Entrega",
                "LEAD_TIME_SINALIZADO": "Lead Time",
                "SITUACAO_PRAZO": "Situação"
            }
            
            if "CD_FORNECEDOR" in df_filtrado.columns: colunas_tabela["CD_FORNECEDOR"] = "Fornecedor"
            if "COMPRADOR" in df_filtrado.columns: colunas_tabela["COMPRADOR"] = "Comprador"
            
            df_tabela = df_filtrado[list(colunas_tabela.keys())].rename(columns=colunas_tabela)
            df_tabela["Data Criação da Ordem"] = df_tabela["Data Criação da Ordem"].dt.strftime('%d/%m/%Y').fillna('-')
            df_tabela["Prazo Entrega"] = df_tabela["Prazo Entrega"].dt.strftime('%d/%m/%Y').fillna('-')
            
            def colorir_linhas_situacao(val):
                if "🔴" in str(val): return 'background-color: #FFCCCC; color: black;'
                elif "🟡" in str(val): return 'background-color: #FFF2CC; color: black;'
                elif "🟢" in str(val): return 'background-color: #D9EAD3; color: black;'
                elif "🔵" in str(val): return 'background-color: #E6F2FF; color: black;'
                elif "⚫" in str(val): return 'background-color: #EAEAEA; color: #7F7F7F;'
                return ''
            
            try:
                df_estilizado = df_tabela.style.map(colorir_linhas_situacao, subset=["Lead Time"])
            except AttributeError:
                df_estilizado = df_tabela.style.applymap(colorir_linhas_situacao, subset=["Lead Time"])
                
            st.dataframe(df_estilizado, use_container_width=True, hide_index=True)

        # ------------------------------------------------------------------
        # ABA 2: DASHBOARD EXECUTIVO 
        # ------------------------------------------------------------------
        with aba_executivo:
            st.markdown("### 📊 Indicadores Consolidados da Carteira")
            
            df_dash = df_filtrado[df_filtrado["SITUACAO_PRAZO"].isin(["Atrasada", "Vence em até 10 dias", "Dentro do Prazo", "Recebida Total", "Cancelada"])].copy()
            
            if not df_dash.empty:
                # 1. GRÁFICO HORIZONTAL DE TODOS OS SETORES - AJUSTADO CONFLITO DE TEXTO
                st.markdown(f"#### 🏢 Distribuição por Setor ({col_setor.title()})")
                df_setores = df_dash.groupby(col_setor)["ORDEM_LIMPA"].nunique().reset_index()
                df_setores.columns = ["Setor", "Quantidade"]
                df_setores = df_setores.sort_values(by="Quantidade", ascending=True)
                
                num_setores = len(df_setores)
                altura_grafico = max(400, num_setores * 28) 
                
                fig_setores = px.bar(
                    df_setores, y="Setor", x="Quantidade",
                    orientation="h", text="Quantidade",
                    color_discrete_sequence=["#1f77b4"]
                )
                fig_setores.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                    font=dict(color="white"), height=altura_grafico,
                    margin=dict(l=220, r=40, t=20, b=20), # Abre espaço na margem esquerda para nomes longos
                    xaxis=dict(title=None, showgrid=False, showticklabels=False),
                    yaxis=dict(title=None, showgrid=False, dtick=1)
                )
                # Altera posição para 'inside' para que o número não encavale com o nome do setor
                fig_setores.update_traces(textposition="inside", textfont=dict(size=12, color="white"))
                st.plotly_chart(fig_setores, use_container_width=True)
                
                st.markdown("---")
                
                # 2. GRÁFICO HISTÓRICO - CORRIGIDA A DUPLICAÇÃO DE BARRAS MENSAL
                st.markdown("#### 📆 Histórico de Abertura de OCs por Mês")
                df_dash_valid_date = df_dash.dropna(subset=["DATA"]).copy()
                
                # Agrupamento explícito por mês formatado para evitar quebras duplicadas
                df_dash_valid_date["MES_ANO_TEXTO"] = df_dash_valid_date["DATA"].dt.strftime('%m/%Y')
                df_mes = df_dash_valid_date.groupby("MES_ANO_TEXTO")["ORDEM_LIMPA"].nunique().reset_index()
                df_mes.columns = ["Mês", "Volume de OCs"]
                
                # Garante ordenação cronológica correta na tela
                df_mes["DATA_ORDEM"] = pd.to_datetime(df_mes["Mês"], format="%m/%Y")
                df_mes = df_mes.sort_values("DATA_ORDEM")
                
                fig_mes = px.bar(
                    df_mes, x="Mês", y="Volume de OCs",
                    text="Volume de OCs", color_discrete_sequence=["#00CC96"]
                )
                fig_mes.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                    font=dict(color="white"),
                    xaxis=dict(title=None, showgrid=False, type='category'), # Força o Plotly a tratar como categoria única
                    yaxis=dict(title=None, showgrid=False, showticklabels=False)
                )
                fig_mes.update_traces(textposition="outside", textfont=dict(size=13, color="white"))
                st.plotly_chart(fig_mes, use_container_width=True)

                st.markdown("---")
                
                # 3. GRÁFICO DE SITUAÇÃO
                st.markdown("#### ⏳ Situação Geral dos Prazos das OCs")
                df_prazos = df_dash.groupby("SITUACAO_PRAZO")["ORDEM_LIMPA"].nunique().reset_index()
                df_prazos.columns = ["Situação", "Quantidade"]
                df_prazos = df_prazos.sort_values(by="Quantidade", ascending=False)
                
                cores_oficiais = {
                    "Atrasada": "#EF553B", "Vence em até 10 dias": "#FECB52", 
                    "Dentro do Prazo": "#00CC96", "Recebida Total": "#1f77b4", "Cancelada": "#7F7F7F"
                }
                
                fig_prazos = px.bar(
                    df_prazos, x="Situação", y="Quantidade",
                    color="Situação", color_discrete_map=cores_oficiais, text="Quantidade"
                )
                fig_prazos.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                    font=dict(color="white"), showlegend=False,
                    xaxis=dict(title=None, showgrid=False),
                    yaxis=dict(title=None, showgrid=False, showticklabels=False)
                )
                fig_prazos.update_traces(textposition="outside", textfont=dict(size=14, color="white"))
                st.plotly_chart(fig_prazos, use_container_width=True)
            else:
                st.info("Sem dados de prazos disponíveis com os filtros atuais.")
                
    else:
        st.error("Coluna 'ORDEM' não encontrada no arquivo.")
else:
    st.info("Aguardando upload do relatório de compras.")

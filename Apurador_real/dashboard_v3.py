import streamlit as st
import sqlite3
import pandas as pd
import os
import plotly.express as px

# ==========================================
# CONFIGURAÇÃO GERAL
# ==========================================
st.set_page_config(page_title="TSE Analytics - V3 Final", layout="wide", page_icon="🏆", initial_sidebar_state="expanded")

# Definindo o path relativo à própria pasta onde o script está sendo rodado
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eleicoes_2026.db")

st.markdown('''
    <style>
    /* Tema Premium Escuro e Moderno */
    .stApp { background-color: #0f172a; color: #f8fafc; }
    .main-header { font-size: 2.8rem; font-weight: 900; background: linear-gradient(90deg, #10b981, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 25px; border-bottom: 2px solid #1e293b; padding-bottom: 10px;}
    
    /* Cards de Métricas */
    .metric-container { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 30px;}
    .metric-card { flex: 1; background: #1e293b; padding: 25px; border-radius: 12px; text-align: center; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); }
    .metric-title { font-size: 1.1rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;}
    .metric-value { font-size: 2.8rem; font-weight: 800; color: #38bdf8; margin-top: 10px; line-height: 1;}
    .metric-value.alert { color: #f43f5e; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #020617; border-right: 1px solid #1e293b; }
    </style>
''', unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 Central de Comando Eleitoral 2026 (V3)</div>', unsafe_allow_html=True)

@st.cache_data(ttl=5)
def carregar_dados():
    try:
        if not os.path.exists(db_path):
            return pd.DataFrame()
            
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='votacao_nominal'")
        if not cursor.fetchone():
            return pd.DataFrame()
            
        df = pd.read_sql("SELECT * FROM votacao_nominal WHERE cand_dest IN ('Válido', 'Válido (legenda)')", conn)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

df = carregar_dados()

if df.empty:
    st.info("🔄 Aguardando injeção de dados no banco SQLite... (Garanta que 'python main.py' está rodando na mesma pasta)")
else:
    cargos_map = {'1': 'Presidente', '3': 'Governador', '5': 'Senador', '6': 'Dep. Federal', '7': 'Dep. Estadual'}
    cargos_disponiveis = [c for c in df['cargo'].unique() if c in cargos_map]

    st.sidebar.markdown("### 🎛️ Painel de Controle")
    cargo_sel = st.sidebar.selectbox("Selecione o Cargo", cargos_disponiveis, format_func=lambda x: cargos_map.get(x, x))
    df_cargo = df[df['cargo'] == cargo_sel].copy()
    
    # Tratamento de Nulos para evitar bugs de agrupamento
    df_cargo['cod_mun'] = df_cargo['cod_mun'].fillna('')

    # ==========================
    # SEÇÃO 1: KPIs
    # ==========================
    total_votos = df_cargo['votos'].sum()
    total_candidatos = df_cargo['cand_nm'].nunique()
    
    # Checa se há matematicamente definidos no cargo atual
    uf_definidas = df_cargo[df_cargo['matematicamente_definido'].isin(['e', 's'])]['uf'].unique()
    alerta_definido = f"SIM ({len(uf_definidas)} UFs)" if len(uf_definidas) > 0 else "NÃO"
    css_class = "alert" if len(uf_definidas) > 0 else ""

    kpi_html = f'''
    <div class="metric-container">
        <div class="metric-card">
            <div class="metric-title">Votos Válidos Processados</div>
            <div class="metric-value">{total_votos:,}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Candidatos no Cargo</div>
            <div class="metric-value">{total_candidatos}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Decisão Matemática Atingida?</div>
            <div class="metric-value {css_class}">{alerta_definido}</div>
        </div>
    </div>
    '''
    st.markdown(kpi_html, unsafe_allow_html=True)

    # ==========================
    # SEÇÃO 2: ABAS VISUAIS
    # ==========================
    tab_resumo, tab_mapa = st.tabs(["📊 Rank & Estatísticas", "🗺️ Mapa Geopolítico (Treemap)"])

    with tab_resumo:
        col1, col2 = st.columns([1.5, 1])
        
        with col1:
            st.markdown("#### Ranking Consolidado")
            votos_rank = df_cargo.groupby(['cand_nm', 'partido', 'uf'])['votos'].sum().reset_index()
            # Agrupa para o ranking geral
            rank_geral = votos_rank.groupby(['cand_nm', 'partido'])['votos'].sum().reset_index().sort_values('votos', ascending=False)
            rank_geral['%'] = (rank_geral['votos'] / total_votos * 100).round(2) if total_votos > 0 else 0
            
            st.dataframe(
                rank_geral.head(20).style.background_gradient(cmap='Greens', subset=['votos']).format({'%': '{:.2f}%', 'votos': '{:,}'}),
                use_container_width=True, height=500
            )
            
        with col2:
            st.markdown("#### Top 5 Vencedores")
            if not rank_geral.empty:
                fig = px.bar(rank_geral.head(5), x='votos', y='cand_nm', color='partido', orientation='h', text_auto='.2s')
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color="white", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

    with tab_mapa:
        st.markdown("#### Dominância Territorial (Mapa Hierárquico)")
        st.info("Navegue clicando nos blocos! O agrupamento é dinâmico com base na granularidade dos dados baixados pelo pipeline.")
        
        # Correção de Bug do Mapa (V2 agrupava por município mesmo quando a ingestão era apenas Estadual ou Nacional)
        # Identificamos a granularidade real:
        tem_municipio = (df_cargo['cod_mun'] != '').any()
        tem_uf_real = (df_cargo['uf'] != 'BR').any()
        
        # Filtra top 6 para não estourar paleta de cores
        top_cands = rank_geral.head(6)['cand_nm'].tolist()
        df_mapa = df_cargo[df_cargo['cand_nm'].isin(top_cands)].copy()
        
        if not df_mapa.empty:
            # Estratégia de Hierarquia Dinâmica
            if tem_municipio:
                path = [px.Constant("Brasil"), 'uf', 'cod_mun', 'cand_nm']
                agrupamento = ['uf', 'cod_mun', 'cand_nm']
                id_max_group = ['uf', 'cod_mun']
            elif tem_uf_real:
                path = [px.Constant("Brasil"), 'uf', 'cand_nm']
                agrupamento = ['uf', 'cand_nm']
                id_max_group = ['uf']
            else:
                # Granularidade puramente Nacional (ex: Presidente onde o pipeline só puxa BR)
                path = [px.Constant("Brasil"), 'cand_nm']
                agrupamento = ['cand_nm']
                id_max_group = [] # Sem vencedor territorial regionalizado

            df_tree = df_mapa.groupby(agrupamento)['votos'].sum().reset_index()
            
            if id_max_group:
                # Mantém apenas o vencedor de cada região
                df_vencedores = df_tree.loc[df_tree.groupby(id_max_group)['votos'].idxmax()]
            else:
                df_vencedores = df_tree

            fig_tree = px.treemap(
                df_vencedores, 
                path=path, 
                values='votos',
                color='cand_nm',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_tree.update_traces(root_color="#1e293b", marker=dict(line=dict(color='#0f172a', width=2)))
            fig_tree.update_layout(margin=dict(t=20, l=10, r=10, b=10), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color="white", height=700)
            
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.warning("Dados insuficientes para renderizar o Treemap.")

st.sidebar.markdown("---")
st.sidebar.caption("By Engenharia de Dados")

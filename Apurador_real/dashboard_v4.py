import streamlit as st
import sqlite3
import pandas as pd
import os
import plotly.express as px
import requests
import json

# ==========================================
# CONFIGURACAO GERAL
# ==========================================
st.set_page_config(page_title="TSE Analytics - V4 Cartografico", layout="wide", page_icon="map", initial_sidebar_state="expanded")

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eleicoes_2026.db")

st.markdown('''
    <style>
    .stApp { background-color: #0f172a; color: #f8fafc; }
    .main-header { font-size: 2.8rem; font-weight: 900; background: linear-gradient(90deg, #10b981, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 25px; border-bottom: 2px solid #1e293b; padding-bottom: 10px;}
    .metric-container { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 30px;}
    .metric-card { flex: 1; background: #1e293b; padding: 25px; border-radius: 12px; text-align: center; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); }
    .metric-title { font-size: 1.1rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;}
    .metric-value { font-size: 2.8rem; font-weight: 800; color: #38bdf8; margin-top: 10px; line-height: 1;}
    .metric-value.alert { color: #f43f5e; }
    [data-testid="stSidebar"] { background-color: #020617; border-right: 1px solid #1e293b; }
    </style>
''', unsafe_allow_html=True)

st.markdown('<div class="main-header">Centro Cartografico Eleitoral 2026 (V4)</div>', unsafe_allow_html=True)

# ==========================================
# INTEGRACAO GEO-ESPACIAL TSE -> IBGE
# ==========================================
UF_TO_IBGE = {
    'AC': '12', 'AL': '27', 'AP': '16', 'AM': '13', 'BA': '29', 'CE': '23', 'DF': '53', 'ES': '32',
    'GO': '52', 'MA': '21', 'MT': '51', 'MS': '50', 'MG': '31', 'PA': '15', 'PB': '25', 'PR': '41',
    'PE': '26', 'PI': '22', 'RJ': '33', 'RN': '24', 'RS': '43', 'RO': '11', 'RR': '14', 'SC': '42',
    'SP': '35', 'SE': '28', 'TO': '17'
}

@st.cache_data(ttl=3600)
def carregar_de_para_tse_ibge():
    # Baixa o EA12 do TSE para mapear codigo do TSE (5 digitos) para Codigo IBGE (7 digitos)
    url = "https://resultados-sim.tse.jus.br/simulado/simulado2026/ele2026/21272/config/mun-e021272-cm.json"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        mapa = {}
        for uf_node in data.get('abr', []):
            for mun_node in uf_node.get('mu', []):
                cd_tse = str(mun_node.get('cd', '')).zfill(5)
                cd_ibge = str(mun_node.get('cdi', ''))
                if cd_tse and cd_ibge:
                    mapa[cd_tse] = cd_ibge
        return mapa
    except:
        return {}

@st.cache_data(ttl=3600)
def carregar_geojson_uf(uf_sigla):
    # Baixa o GeoJSON simplificado de uma UF especifica
    uf_id = UF_TO_IBGE.get(uf_sigla.upper())
    if not uf_id:
        return None
    url = f"https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-{uf_id}-mun.json"
    try:
        r = requests.get(url, timeout=5)
        return r.json()
    except:
        return None

# ==========================================
# CARREGAMENTO DOS DADOS (BANCO SQLITE)
# ==========================================
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
    except:
        return pd.DataFrame()

df = carregar_dados()

if df.empty:
    st.info("Aguardando injecao de dados no banco SQLite...")
else:
    cargos_map = {'1': 'Presidente', '3': 'Governador', '5': 'Senador', '6': 'Dep. Federal', '7': 'Dep. Estadual'}
    cargos_disponiveis = [c for c in df['cargo'].unique() if c in cargos_map]

    st.sidebar.markdown("### Painel de Controle")
    cargo_sel = st.sidebar.selectbox("Selecione o Cargo", cargos_disponiveis, format_func=lambda x: cargos_map.get(x, x))
    df_cargo = df[df['cargo'] == cargo_sel].copy()
    df_cargo['cod_mun'] = df_cargo['cod_mun'].fillna('')

    total_votos = df_cargo['votos'].sum()
    total_candidatos = df_cargo['cand_nm'].nunique()
    
    uf_definidas = df_cargo[df_cargo['matematicamente_definido'].isin(['e', 's'])]['uf'].unique()
    alerta_definido = f"SIM ({len(uf_definidas)} UFs)" if len(uf_definidas) > 0 else "NAO"
    css_class = "alert" if len(uf_definidas) > 0 else ""

    st.markdown(f'''
    <div class="metric-container">
        <div class="metric-card"><div class="metric-title">Votos Validos</div><div class="metric-value">{total_votos:,}</div></div>
        <div class="metric-card"><div class="metric-title">Candidatos</div><div class="metric-value">{total_candidatos}</div></div>
        <div class="metric-card"><div class="metric-title">Decisao Atingida?</div><div class="metric-value {css_class}">{alerta_definido}</div></div>
    </div>
    ''', unsafe_allow_html=True)

    tab_resumo, tab_mapa_real = st.tabs(["Rank & Estatisticas", "Mapa Geografico Real (IBGE)"])

    with tab_resumo:
        col1, col2 = st.columns([1.5, 1])
        with col1:
            st.markdown("#### Ranking Consolidado")
            votos_rank = df_cargo.groupby(['cand_nm', 'partido'])['votos'].sum().reset_index().sort_values('votos', ascending=False)
            votos_rank['%'] = (votos_rank['votos'] / total_votos * 100).round(2) if total_votos > 0 else 0
            st.dataframe(votos_rank.head(20).style.background_gradient(cmap='Greens', subset=['votos']).format({'%': '{:.2f}%', 'votos': '{:,}'}), use_container_width=True, height=500)
        with col2:
            st.markdown("#### Top 5 Vencedores")
            if not votos_rank.empty:
                fig = px.bar(votos_rank.head(5), x='votos', y='cand_nm', color='partido', orientation='h', text_auto='.2s')
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color="white", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

    with tab_mapa_real:
        st.markdown("#### Cartografia de Vencedores por Municipio")
        st.info("Este mapa faz fetch em tempo real do arquivo EA12 do TSE para traduzir o Codigo de Urna para Codigo IBGE e cruza com a malha geografica do tbrugz/geodata-br!")
        
        ufs_disponiveis = sorted([uf for uf in df_cargo['uf'].unique() if uf != 'BR'])
        
        if not ufs_disponiveis:
            st.warning("Ainda nao temos dados com granularidade municipal ou estadual carregados para este cargo.")
        else:
            uf_selecionada = st.selectbox("Selecione um Estado para Renderizar o Mapa:", ufs_disponiveis)
            df_uf = df_cargo[(df_cargo['uf'] == uf_selecionada) & (df_cargo['cod_mun'] != '')].copy()
            
            if df_uf.empty:
                st.warning(f"O pipeline ainda nao salvou os votos dos municipios de {uf_selecionada} (Apenas abrangencia estadual detectada).")
            else:
                mapa_ibge = carregar_de_para_tse_ibge()
                df_uf['cod_ibge'] = df_uf['cod_mun'].map(mapa_ibge)
                df_uf_valido = df_uf.dropna(subset=['cod_ibge'])
                
                if df_uf_valido.empty:
                    st.error("Nenhum codigo TSE da base correspondeu ao EA12. Aguardando sincronizacao.")
                else:
                    df_mun_agrupado = df_uf_valido.groupby(['cod_ibge', 'cand_nm'])['votos'].sum().reset_index()
                    idx_vencedores = df_mun_agrupado.groupby('cod_ibge')['votos'].idxmax()
                    df_vencedores = df_mun_agrupado.loc[idx_vencedores]
                    
                    with st.spinner(f"Processando Malha Geografica de {uf_selecionada}..."):
                        geojson_uf = carregar_geojson_uf(uf_selecionada)
                    
                    if not geojson_uf:
                        st.error(f"Erro ao baixar a malha geo-espacial para a UF {uf_selecionada}.")
                    else:
                        fig_map = px.choropleth(
                            df_vencedores, 
                            geojson=geojson_uf, 
                            locations='cod_ibge', 
                            featureidkey='properties.id',
                            color='cand_nm',
                            hover_name='cand_nm',
                            hover_data={'votos': True, 'cod_ibge': False},
                            color_discrete_sequence=px.colors.qualitative.Set2
                        )
                        fig_map.update_geos(fitbounds="locations", visible=False)
                        fig_map.update_layout(
                            margin={"r":0,"t":0,"l":0,"b":0},
                            plot_bgcolor='rgba(0,0,0,0)', 
                            paper_bgcolor='rgba(0,0,0,0)',
                            geo=dict(bgcolor= 'rgba(0,0,0,0)'),
                            height=600
                        )
                        st.plotly_chart(fig_map, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.caption("Engenharia de Dados - V4 Cartografico Real")

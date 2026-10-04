import streamlit as st
import sqlite3
import pandas as pd
import os
import plotly.express as px
import requests

# ==========================================
# CONFIGURAÇÃO GERAL E UTILITÁRIOS
# ==========================================
st.set_page_config(page_title="TSE Analytics - Versão Final", layout="wide", page_icon="🇧🇷", initial_sidebar_state="expanded")

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eleicoes_2026.db")

def format_br(num, is_float=False, percent=False):
    """Formata números para o padrão brasileiro (ex: 1.000.000,00 ou 1.000)"""
    if pd.isna(num): return "0"
    if percent:
        s = f"{num:,.2f}"
        return s.replace(',', 'X').replace('.', ',').replace('X', '.') + "%"
    if is_float:
        s = f"{num:,.2f}"
        return s.replace(',', 'X').replace('.', ',').replace('X', '.')
    else:
        s = f"{int(num):,}"
        return s.replace(',', '.')

st.markdown('''
    <style>
    .stApp { background-color: #0f172a; color: #f8fafc; }
    .main-header { font-size: 2.8rem; font-weight: 900; background: linear-gradient(90deg, #10b981, #f59e0b, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 25px; border-bottom: 2px solid #1e293b; padding-bottom: 10px;}
    .metric-container { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px;}
    .metric-card { flex: 1; background: #1e293b; padding: 20px; border-radius: 12px; text-align: center; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); }
    .metric-title { font-size: 1rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;}
    .metric-value { font-size: 2.4rem; font-weight: 800; color: #38bdf8; margin-top: 5px; line-height: 1.2;}
    .alert-card { background: #3f2a28; border: 1px solid #ef4444; color: #fca5a5; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center; font-size: 1.2rem; font-weight: bold;}
    .success-card { background: #14532d; border: 1px solid #22c55e; color: #bbf7d0; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center; font-size: 1.2rem; font-weight: bold;}
    [data-testid="stSidebar"] { background-color: #020617; border-right: 1px solid #1e293b; }
    </style>
''', unsafe_allow_html=True)

st.markdown('<div class="main-header">🇧🇷 Apuração Eleições 2026 (Oficial)</div>', unsafe_allow_html=True)

# ==========================================
# INTEGRAÇÃO GEO-ESPACIAL (TSE -> IBGE)
# ==========================================

CORES_PARTIDOS = {
    '13': '#ef4444', # PT (Red)
    '22': '#1e3a8a', # PL (Dark Blue)
    '45': '#3b82f6', # PSDB (Blue)
    '15': '#10b981', # MDB (Green)
    '12': '#f43f5e', # PDT (Rose/Red)
    '44': '#0284c7', # União Brasil (Blue)
    '11': '#34d399', # PP (Teal/Green)
    '55': '#f59e0b', # PSD (Orange/Yellow)
    '10': '#14b8a6', # Republicanos (Teal)
    '30': '#fb923c', # NOVO (Orange)
    '50': '#facc15', # PSOL (Yellow)
    '65': '#b91c1c', # PCdoB (Dark Red)
    '40': '#fbbf24', # PSB (Yellow/Orange)
    '23': '#ec4899', # Cidadania (Pink)
    '43': '#16a34a', # PV (Dark Green)
    '18': '#22c55e', # REDE (Green)
    '77': '#fb7185', # Solidariedade (Pink/Red)
    '14': '#0ea5e9', # PTB / PRD (Light Blue)
    '20': '#a855f7', # Podemos (Purple)
    '19': '#64748b', # Podemos (antigo)
    '70': '#84cc16', # Avante (Lime)
    '90': '#f87171', # PROS (Red)
}

UF_TO_IBGE = {
    'AC': '12', 'AL': '27', 'AP': '16', 'AM': '13', 'BA': '29', 'CE': '23', 'DF': '53', 'ES': '32',
    'GO': '52', 'MA': '21', 'MT': '51', 'MS': '50', 'MG': '31', 'PA': '15', 'PB': '25', 'PR': '41',
    'PE': '26', 'PI': '22', 'RJ': '33', 'RN': '24', 'RS': '43', 'RO': '11', 'RR': '14', 'SC': '42',
    'SP': '35', 'SE': '28', 'TO': '17'
}

@st.cache_data(ttl=3600)
def carregar_de_para_tse_ibge():
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
    uf_id = UF_TO_IBGE.get(uf_sigla.upper())
    if not uf_id: return None
    url = f"https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-{uf_id}-mun.json"
    try:
        r = requests.get(url, timeout=5)
        return r.json()
    except:
        return None

# ==========================================
# DADOS
# ==========================================
@st.cache_data(ttl=5)
def carregar_dados():
    try:
        if not os.path.exists(db_path): return pd.DataFrame()
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM votacao_nominal WHERE cand_dest IN ('Válido', 'Válido (legenda)')", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

df = carregar_dados()

if df.empty:
    st.info("Aguardando injeção de dados no banco SQLite...")
else:
    cargos_map = {'1': 'Presidente', '3': 'Governador', '5': 'Senador', '6': 'Dep. Federal', '7': 'Dep. Estadual'}
    cargos_disponiveis = [c for c in df['cargo'].unique() if c in cargos_map]

    st.sidebar.markdown("### 🎛️ Filtros de Apuração")
    cargo_sel = st.sidebar.selectbox("Cargo", cargos_disponiveis, format_func=lambda x: cargos_map.get(x, x))
    df_cargo = df[df['cargo'] == cargo_sel].copy()
    df_cargo['cod_mun'] = df_cargo['cod_mun'].fillna('')

    # Consolidação
    total_votos = df_cargo['votos'].sum()
    votos_rank = df_cargo.groupby(['cand_nm', 'partido'])['votos'].sum().reset_index().sort_values('votos', ascending=False)
    votos_rank['perc'] = (votos_rank['votos'] / total_votos * 100) if total_votos > 0 else 0

    lider = votos_rank.iloc[0] if len(votos_rank) > 0 else None
    segundo = votos_rank.iloc[1] if len(votos_rank) > 1 else None
    
    vantagem = (lider['votos'] - segundo['votos']) if lider is not None and segundo is not None else 0
    perc_lider = lider['perc'] if lider is not None else 0

    # 1. Alertas de Turno e Decisão
    uf_definidas = df_cargo[df_cargo['matematicamente_definido'].isin(['e', 's'])]['uf'].unique()
    
    if len(uf_definidas) > 0:
        st.markdown(f'<div class="success-card">✅ ELEIÇÃO MATEMATICAMENTE DEFINIDA EM: {", ".join(uf_definidas)}</div>', unsafe_allow_html=True)
    elif cargo_sel in ['1', '3']: # Apenas Executivo tem 2º Turno (Presidente/Gov)
        if perc_lider > 50:
            st.markdown(f'<div class="success-card">📈 PREVISÃO: Vitória em 1º Turno para {lider["cand_nm"]}</div>', unsafe_allow_html=True)
        elif lider is not None and segundo is not None:
            st.markdown(f'<div class="alert-card">⚖️ PREVISÃO: 2º Turno provável entre {lider["cand_nm"]} e {segundo["cand_nm"]}</div>', unsafe_allow_html=True)

    # 2. KPIs Superiores
    st.markdown(f'''
    <div class="metric-container">
        <div class="metric-card"><div class="metric-title">Votos Válidos</div><div class="metric-value">{format_br(total_votos)}</div></div>
        <div class="metric-card"><div class="metric-title">Líder: {lider['cand_nm'] if lider is not None else '-'}</div><div class="metric-value">{format_br(lider['votos'] if lider is not None else 0)}</div></div>
        <div class="metric-card"><div class="metric-title">Vantagem do Líder</div><div class="metric-value">{format_br(vantagem)}</div></div>
    </div>
    ''', unsafe_allow_html=True)

    tab_resumo, tab_cenario, tab_mapa_real = st.tabs(["📊 Apuração Geral", "🔮 Previsões e Diferença", "🗺️ Mapa Geográfico"])

    with tab_resumo:
        col1, col2 = st.columns([1.5, 1])
        with col1:
            st.markdown("#### Ranking Oficial")
            # Tabela formatada para o padrão Brasil
            df_display = votos_rank.head(20).copy()
            df_display['%'] = df_display['perc'].apply(lambda x: format_br(x, percent=True))
            df_display['votos'] = df_display['votos'].apply(lambda x: format_br(x))
            df_display = df_display.drop(columns=['perc'])
            
            st.dataframe(df_display, use_container_width=True, height=500, hide_index=True)
        with col2:
            st.markdown("#### Distribuição do Top 5")
            if not votos_rank.empty:
                fig = px.pie(votos_rank.head(5), values='votos', names='cand_nm', color='partido', hole=0.4, color_discrete_map=CORES_PARTIDOS)
                fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color="white", showlegend=False)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)

    with tab_cenario:
        st.markdown("#### Análise de Disputa e Turno")
        st.write("Acompanhe aqui a distância entre o 1º e 2º colocado, fator decisivo na reta final da apuração das urnas.")
        
        if lider is not None and segundo is not None:
            # Gráfico de barras da diferença
            df_diff = pd.DataFrame({
                'Candidato': [lider['cand_nm'], segundo['cand_nm']],
                'Votos': [lider['votos'], segundo['votos']],
                'Partido': [lider['partido'], segundo['partido']]
            })
            fig_bar = px.bar(df_diff, x='Votos', y='Candidato', color='Partido', orientation='h', text='Votos', color_discrete_map=CORES_PARTIDOS)
            fig_bar.update_traces(texttemplate='%{text:,.0f}'.replace(',', '.'), textposition='inside')
            fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color="white", height=300)
            st.plotly_chart(fig_bar, use_container_width=True)
            
            st.info(f"💡 Para reverter a eleição, **{segundo['cand_nm']}** precisa ultrapassar a margem de **{format_br(vantagem)}** votos.")
        else:
            st.warning("Aguardando mais dados de candidatos para análise de disputa.")

    with tab_mapa_real:
        st.markdown("#### Mapa de Vencedores por Município")
        ufs_disponiveis = sorted([uf for uf in df_cargo['uf'].unique() if uf != 'BR'])
        
        if not ufs_disponiveis:
            st.warning("⚠️ Os pacotes de dados processados para este cargo até o momento possuem apenas abrangência Nacional (BR).")
        else:
            uf_selecionada = st.selectbox("Renderizar Mapa do Estado:", ufs_disponiveis)
            df_uf = df_cargo[(df_cargo['uf'] == uf_selecionada) & (df_cargo['cod_mun'] != '')].copy()
            
            if df_uf.empty:
                st.warning(f"Aguardando a carga de dados municipais para {uf_selecionada}.")
            else:
                mapa_ibge = carregar_de_para_tse_ibge()
                df_uf['cod_ibge'] = df_uf['cod_mun'].map(mapa_ibge)
                df_uf_valido = df_uf.dropna(subset=['cod_ibge'])
                
                if df_uf_valido.empty:
                    st.error("Falha ao traduzir Códigos TSE para Códigos IBGE (Sem Sincronia).")
                else:
                    df_mun_agrupado = df_uf_valido.groupby(['cod_ibge', 'cand_nm', 'partido'])['votos'].sum().reset_index()
                    idx_vencedores = df_mun_agrupado.groupby('cod_ibge')['votos'].idxmax()
                    df_vencedores = df_mun_agrupado.loc[idx_vencedores]
                    # Adiciona nome legível para tooltip do mapa
                    df_vencedores['Votos Recebidos'] = df_vencedores['votos'].apply(lambda x: format_br(x))
                    
                    with st.spinner(f"Processando Malha Cartográfica (IBGE) para {uf_selecionada}..."):
                        geojson_uf = carregar_geojson_uf(uf_selecionada)
                    
                    if not geojson_uf:
                        st.error("Servidor de malha geográfica indisponível.")
                    else:
                        fig_map = px.choropleth(
                            df_vencedores, 
                            geojson=geojson_uf, 
                            locations='cod_ibge', 
                            featureidkey='properties.id',
                            color='partido',
                            hover_name='cand_nm',
                            hover_data={'votos': False, 'cod_ibge': False, 'Votos Recebidos': True},
                            color_discrete_map=CORES_PARTIDOS
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
st.sidebar.caption("Dashboard Oficial de Cobertura Eleitoral")

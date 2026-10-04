import sqlite3
import pandas as pd
import asyncio
import logging

logger = logging.getLogger(__name__)

DB_NAME = "eleicoes_2026.db"

def _setup_db():
    query = '''
    CREATE TABLE IF NOT EXISTS votacao_nominal (
        uf TEXT,
        cod_mun TEXT,
        data_hora TEXT,
        eleicao_encerrada BOOLEAN,
        matematicamente_definido TEXT,
        eleicao_sem_eleito TEXT,
        cargo TEXT,
        vagas TEXT,
        partido TEXT,
        cand_sq TEXT,
        cand_n TEXT,
        cand_nm TEXT,
        nome_candidato_substituido TEXT,
        cand_dest TEXT,
        cand_situacao TEXT,
        votos INTEGER
    )
    '''
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(query)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_escopo ON votacao_nominal (uf, cod_mun, cargo);")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco: {e}")

_setup_db()

def _update_table_sync(df: pd.DataFrame):
    if df.empty:
        return
        
    uf = str(df['uf'].iloc[0])
    cod_mun = str(df['cod_mun'].iloc[0])
    cargo = str(df['cargo'].iloc[0])
    
    try:
        with sqlite3.connect(DB_NAME, timeout=15) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM votacao_nominal WHERE uf = ? AND cod_mun = ? AND cargo = ?",
                (uf, cod_mun, cargo)
            )
            df.to_sql("votacao_nominal", conn, if_exists="append", index=False)
            
    except Exception as e:
        logger.error(f"Erro ao salvar no banco SQLite: {e}")

async def salvar_votacao_async(df: pd.DataFrame):
    if not df.empty:
        await asyncio.to_thread(_update_table_sync, df)

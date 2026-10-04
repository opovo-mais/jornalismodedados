import pandas as pd
from typing import Dict, Any

def parse_ea20_votacao(data: Dict[str, Any], uf: str, cod_mun: str = "") -> pd.DataFrame:
    """
    Achata e converte o JSON bruto do EA20 (*-u.json) para pandas DataFrame.
    Respeita a Fidelidade Léxica Absoluta. Nenhuma formatação extra de string é feita.
    Lida com votos válidos, sub judice, legendas e substituídos de urna nativamente.
    """
    if not data or 'carg' not in data:
        return pd.DataFrame()
        
    rows = []
    
    # Metadados do Arquivo
    dt = data.get('dt', '')
    ht = data.get('ht', '')
    # Indicador de fechamento (and=f -> matematicamente definido ou encerrado)
    eleicao_andamento = data.get('and', '')
    md = data.get('md', '')
    esae = data.get('esae', '')
    
    for cargo in data['carg']:
        cd_cargo = str(cargo.get('cd', ''))
        vagas = str(cargo.get('nv', ''))
        
        for agr in cargo.get('agr', []): # Agrupamento / Coligações
            for par in agr.get('par', []): # Partidos
                cd_partido = str(par.get('n', ''))
                
                for cand in par.get('cand', []): # Candidatos nominais
                    subs = cand.get('subs', [])
                    nome_substituido = subs[0].get('nm', '') if subs else ''
                    rows.append({
                        'uf': str(uf),
                        'cod_mun': str(cod_mun).zfill(5) if cod_mun else "",
                        'data_hora': f"{dt} {ht}",
                        'eleicao_encerrada': (eleicao_andamento == 'f'),
                        'matematicamente_definido': md,
                        'eleicao_sem_eleito': esae,
                        'cargo': cd_cargo,
                        'vagas': vagas,
                        'partido': cd_partido,
                        'cand_sq': str(cand.get('sqcand', '')),
                        'cand_n': str(cand.get('n', '')),
                        'cand_nm': cand.get('nm', ''),
                        'nome_candidato_substituido': nome_substituido,
                        'cand_dest': cand.get('dvt', ''),  # Validações como "Anulado sub judice"
                        'cand_situacao': cand.get('st', ''),
                        'votos': int(cand.get('vap', 0))
                    })
    
    df = pd.DataFrame(rows)
    if not df.empty:
        # Padrões Central de Dados: Tipagem Estrita
        df['uf'] = df['uf'].astype('string')
        df['cod_mun'] = df['cod_mun'].astype('string')
        df['data_hora'] = df['data_hora'].astype('string')
        df['matematicamente_definido'] = df['matematicamente_definido'].astype('string')
        df['eleicao_sem_eleito'] = df['eleicao_sem_eleito'].astype('string')
        df['nome_candidato_substituido'] = df['nome_candidato_substituido'].astype('string')
        df['cargo'] = df['cargo'].astype('string')
        df['vagas'] = df['vagas'].astype('string')
        df['partido'] = df['partido'].astype('string')
        df['cand_sq'] = df['cand_sq'].astype('string')
        df['cand_n'] = df['cand_n'].astype('string')
        df['cand_nm'] = df['cand_nm'].astype('string')
        df['cand_dest'] = df['cand_dest'].astype('string')
        df['cand_situacao'] = df['cand_situacao'].astype('string')
    
    return df

def parse_ea14_15_timestamps(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extrai mapa de códigos para detecção de mudança temporal nos arquivos de evento.
    Funciona para acompanhar mudanças no EA14 (UF) ou EA15 (Município).
    Retorna Dict[cd, hora].
    """
    timestamps = {}
    if not data:
        return timestamps
        
    # 'abr' mapeia abrangências onde chegam atualizações
    for abr in data.get('abr', []):
        cd = str(abr.get('cd', ''))
        ht = abr.get('ht', '')
        timestamps[cd] = ht
        
    return timestamps

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List

class Environment(Enum):
    SIMULATED = "simulado2026"
    OFFICIAL = "oficial"

@dataclass
class TSEConfig:
    env: Environment
    env_path: str
    base_url: str
    cycle: str
    pleito: str
    eleicao_federal: str
    eleicao_estadual: str
    eleicao_municipal: str

# Configurações do Ambiente Simulado (Homologação / Testes)
SIMULADO_CONFIG = TSEConfig(
    env=Environment.SIMULATED,
    env_path="simulado/simulado2026",
    base_url="https://resultados-sim.tse.jus.br",
    cycle="ele2026",
    pleito="17801",
    eleicao_federal="21270",
    eleicao_estadual="21272",
    eleicao_municipal="21274"
)

# Configurações do Ambiente Oficial (Produção - 04/10/2026)
OFICIAL_CONFIG = TSEConfig(
    env=Environment.OFFICIAL,
    env_path="oficial",
    base_url="https://resultados.tse.jus.br",
    cycle="ele2026", # Pode ser substituído lendo ele-c.json
    pleito="3220",
    eleicao_federal="6257",
    eleicao_estadual="6259",
    eleicao_municipal="6261"
)

# Códigos de Cargos Oficiais do TSE
CARGOS: Dict[str, str] = {
    "c0001": "Presidente",
    "c0003": "Governador",
    "c0005": "Senador",
    "c0006": "Deputado Federal",
    "c0007": "Deputado Estadual",
    "c0008": "Deputado Distrital"
}

# Lista de Unidades Federativas (UFs) + Brasil (BR)
UFS: List[str] = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO"
]

# Teto absoluto do Rate Limit em Produção
MAX_REQ_PER_SEC = 70

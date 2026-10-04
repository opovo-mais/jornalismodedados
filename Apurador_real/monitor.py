import asyncio
import logging
from config import TSEConfig, UFS
from tse_client import TSEClient
from parsers import parse_ea20_votacao, parse_ea14_15_timestamps
from database import salvar_votacao_async

logger = logging.getLogger(__name__)

class TSEMonitor:
    """
    Orquestrador assíncrono que implementa o Funil Hierárquico:
    Camada 1: Polling em UFs e BR.
    Camada 2: Detecção de Eventos via EA14/EA15.
    Camada 3: Extração granular baseada em eventos municipais.
    """
    def __init__(self, config: TSEConfig):
        self.config = config
        self.client = TSEClient()
        self.municipios_validos = set()
        self.municipios_por_uf = {}
        
        # Estado local de timestamps (usado para detecção da Camada 2)
        self.ufs_timestamps = {}

    async def _carregar_municipios(self):
        """
        Rotina Crítica: Impede envio de chamadas para municípios inexistentes (Prevenção a 404).
        Baixa o ele-c.json ou mun-e0*.json e preenche o dicionário de abrangência.
        """
        logger.info("Carregando lista hierárquica de municípios...")
        url = f"{self.config.base_url}/{self.config.env_path}/{self.config.cycle}/{self.config.eleicao_federal}/config/mun-e0{self.config.eleicao_federal}-cm.json"
        
        data, _ = await self.client.get_json(url)
        if data and 'abr' in data:
            for uf_node in data['abr']:
                uf = uf_node.get('cd', '').upper()
                if uf not in self.municipios_por_uf:
                    self.municipios_por_uf[uf] = []
                    
                for mun_node in uf_node.get('mu', []):
                    cod_mun = self.client.format_mun(mun_node.get('cd'))
                    self.municipios_validos.add(cod_mun)
                    self.municipios_por_uf[uf].append(cod_mun)
                    
        logger.info(f"Autorizados {len(self.municipios_validos)} municípios para extração municipal.")

    async def poll_layer1_macro(self):
        """Camada 1 (Macrorresultados): Polling de acompanhamento Brasil e UF."""
        logger.info("Iniciando Camada 1: Monitorando Nacional (Presidente) e Estaduais (Governador/Senador/Deputados)...")
        while True:
            # 1. Presidente do Brasil (c0001 na Eleição Federal)
            url_br = f"{self.config.base_url}/{self.config.env_path}/{self.config.cycle}/{self.config.eleicao_federal}/dados/br/br-c0001-e0{self.config.eleicao_federal}-u.json"
            data, is_mod = await self.client.get_json(url_br)
            if is_mod and data:
                df = parse_ea20_votacao(data, uf="BR")
                logger.info(f"[BR] Atualização de Presidente recebida: {len(df)} candidaturas.")
                await salvar_votacao_async(df)

            # 2. Governador/Senador (Exemplo c0003 Governador na Estadual)
            for uf in UFS:
                url_uf = f"{self.config.base_url}/{self.config.env_path}/{self.config.cycle}/{self.config.eleicao_estadual}/dados/{uf.lower()}/{uf.lower()}-c0003-e0{self.config.eleicao_estadual}-u.json"
                data, is_mod = await self.client.get_json(url_uf)
                if is_mod and data:
                    df = parse_ea20_votacao(data, uf=uf)
                    logger.debug(f"[{uf}] Atualização de Governador recebida.")
                    await salvar_votacao_async(df)

            # Descanso estratégico para a rodada macro
            await asyncio.sleep(10)

    async def poll_layer2_municipal_events(self):
        """Camada 2 (Detecção): Varredura nos logs temporais das UFs (EA14) para engatilhar Municípios."""
        logger.info("Iniciando Camada 2: Detecção municipal por eventos do EA14...")
        while True:
            for uf in UFS:
                url_ea14 = f"{self.config.base_url}/{self.config.env_path}/{self.config.cycle}/{self.config.eleicao_estadual}/dados/{uf.lower()}/{uf.lower()}-e0{self.config.eleicao_estadual}-ab.json"
                data, is_mod = await self.client.get_json(url_ea14)
                
                if is_mod and data:
                    timestamps = parse_ea14_15_timestamps(data)
                    for cod, ht in timestamps.items():
                        if cod not in self.ufs_timestamps or self.ufs_timestamps[cod] != ht:
                            self.ufs_timestamps[cod] = ht
                            # Ao detectar modificação, agenda extração cirúrgica de municípios para o loop paralelo
                            asyncio.create_task(self.trigger_layer3_municipal(uf))
            
            # Checagem de eventos ocorre a cada 15 segundos
            await asyncio.sleep(15)

    async def trigger_layer3_municipal(self, uf: str):
        """Camada 3 (Extração Cirúrgica): Download seguro do EA20 respeitando Token Bucket."""
        if uf not in self.municipios_por_uf:
            return
            
        logger.info(f"[EVENTO Camada 3] Sincronizando EA20 para municípios atualizados em {uf}...")
        
        # Limitamos iterar municípios que tivemos certeza via EA-15 (aqui simplificado para todos da UF em caso de evento)
        for cod_mun in self.municipios_por_uf[uf]:
            # Extração de Senador (c0005) à nível municipal
            url_mun = f"{self.config.base_url}/{self.config.env_path}/{self.config.cycle}/{self.config.eleicao_estadual}/dados/{uf.lower()}/{uf.lower()}{cod_mun}-c0005-e0{self.config.eleicao_estadual}-u.json"
            
            data, is_mod = await self.client.get_json(url_mun)
            if is_mod and data:
                df = parse_ea20_votacao(data, uf=uf, cod_mun=cod_mun)
                if not df.empty:
                    logger.debug(f"[MUN] {cod_mun} ({uf}): Capturado Votação para Senador.")
                    await salvar_votacao_async(df)

    async def start(self):
        """Inicia os loops em paralelo após o carregamento seguro das cidades."""
        await self._carregar_municipios()
        await asyncio.gather(
            self.poll_layer1_macro(),
            self.poll_layer2_municipal_events()
        )

    async def stop(self):
        """Encerra graciosamente fechando conexões remanescentes."""
        await self.client.close()

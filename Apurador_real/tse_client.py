import httpx
import logging
from typing import Optional, Dict, Any, Tuple
from rate_limiter import tse_rate_limiter

logger = logging.getLogger(__name__)

class TSEClient:
    """
    Cliente HTTP assíncrono projetado para resiliência no consumo de dados do TSE.
    Implementa headers condicionais, ETag, padronização de municípios e mitigação de banimento 404.
    """
    def __init__(self):
        # httpx client otimizado para concorrência
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
        self.client = httpx.AsyncClient(timeout=10.0, limits=limits, follow_redirects=True)
        
        # Cache em memória para validação de ETag / Last-Modified
        # Formato: {url: (etag, last_modified, json_data)}
        self.cache: Dict[str, Tuple[Optional[str], Optional[str], Any]] = {}

    async def close(self):
        await self.client.aclose()

    @staticmethod
    def format_mun(cod_mun: Any) -> str:
        """
        Garante que o código do município seja formatado estritamente com 5 dígitos, 
        preenchidos com zero à esquerda.
        A ausência dessa formatação gera status 404 no TSE, levando ao banimento de IP.
        """
        return str(cod_mun).zfill(5)

    async def get_json(self, url: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Realiza GET mantendo fidelidade aos limites de infraestrutura do TSE.
        
        Retorna:
            - Tuple(Dict, bool): Onde o booleano indica se o arquivo sofreu alteração.
            - Caso status 304, retorna os dados cacheados e False.
            - Caso status 404 (prevenção ativa) loga e retorna (None, False).
        """
        # Passa pelo funil do Token Bucket (máximo 70 req/s)
        await tse_rate_limiter.consume(1)
        
        headers = {}
        if url in self.cache:
            etag, last_modified, _ = self.cache[url]
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified

        try:
            response = await self.client.get(url, headers=headers)
            
            # Tratamento de HTTP Cache (economiza processamento de extração)
            if response.status_code in (301, 302, 307, 308):
                logger.warning(f"Redirecionamento {response.status_code} detectado para {url}. O cliente httpx o seguirá automaticamente.")

            if response.status_code == 304:
                return self.cache[url][2], False
                
            # Mitigação DoS / Banimento de 10 minutos do TSE
            if response.status_code == 404:
                logger.warning(f"404 Not Found: Prevenção ativada. Abortando {url}")
                return None, False
                
            response.raise_for_status()
            data = response.json()
            
            # Atualiza Cache Local
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            self.cache[url] = (etag, last_modified, data)
            
            return data, True
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP {e.response.status_code} na rota {url}")
            return None, False
        except Exception as e:
            logger.error(f"Erro ao requisitar {url}: {str(e)}")
            return None, False

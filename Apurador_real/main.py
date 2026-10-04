import asyncio
import logging
from config import OFICIAL_CONFIG
from monitor import TSEMonitor

# Configuração Padrão de Log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s : %(message)s'
)

logger = logging.getLogger("TSE_Pipeline")

async def main():
    logger.info("=== INICIANDO PIPELINE EM TEMPO REAL: ELEIÇÕES GERAIS TSE 2026 ===")
    
    # Inicializando com ambiente simulado (segurança para testes)
    monitor = TSEMonitor(config=OFICIAL_CONFIG)
    
    try:
        # Mantém a aplicação rodando assincronamente orquestrando as 3 camadas
        await monitor.start()
    except KeyboardInterrupt:
        logger.info("Interrupção solicitada pelo usuário (Ctrl+C). Encerrando ciclos...")
    except Exception as e:
        logger.error(f"Falha crítica no Pipeline: {str(e)}")
    finally:
        await monitor.stop()
        logger.info("Pipeline Encerrado de forma segura.")

if __name__ == "__main__":
    # Contorno de erro comum no asyncio no Windows
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Fallback loop shutdown manual
        pass

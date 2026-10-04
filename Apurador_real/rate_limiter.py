import asyncio
import time

class TokenBucket:
    """
    Implementação assíncrona de um Token Bucket para Rate Limiting.
    Garante que as requisições não ultrapassem o limite estrito da CDN do TSE (100 req/s).
    Operamos calibrados com margem de segurança (máx 70 req/s).
    """
    def __init__(self, capacity: int, fill_rate: float):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.fill_rate = fill_rate
        self.timestamp = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1):
        """
        Consome tokens do balde. Bloqueia a execução (via sleep) caso não haja 
        tokens suficientes disponíveis, garantindo o throttling passivo.
        """
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.timestamp
                
                # Preenche os tokens de acordo com o tempo passado
                self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
                self.timestamp = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                
                # Se não houver tokens, dorme até que haja o suficiente para a requisição
                sleep_time = (tokens - self.tokens) / self.fill_rate
                await asyncio.sleep(sleep_time)

# Instância global configurada para no máximo 70 requisições por segundo
tse_rate_limiter = TokenBucket(capacity=70, fill_rate=70.0)

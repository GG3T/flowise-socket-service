import logging
import time
from functools import wraps
from src.config.settings import MAX_RETRY_ATTEMPTS, RETRY_BACKOFF_DELAY

logger = logging.getLogger(__name__)

def retry_with_backoff(max_attempts=MAX_RETRY_ATTEMPTS, backoff_ms=RETRY_BACKOFF_DELAY):
    """
    Decorator para tentar novamente uma função com backoff exponencial em caso de exceção.
    
    Args:
        max_attempts (int): Número máximo de tentativas.
        backoff_ms (int): Tempo inicial de espera em milissegundos.
        
    Returns:
        function: Função decorada com retry.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        logger.error(f"Excedido número máximo de tentativas ({max_attempts}). Último erro: {e}")
                        raise e
                    
                    # Backoff exponencial
                    wait_time = (backoff_ms / 1000.0) * (2 ** (attempts - 1))
                    logger.warning(f"Tentativa {attempts} falhou: {e}. Aguardando {wait_time:.2f}s antes da próxima tentativa...")
                    time.sleep(wait_time)
        return wrapper
    return decorator

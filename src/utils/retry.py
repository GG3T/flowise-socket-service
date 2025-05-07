import logging
import time
import random
from functools import wraps
from typing import Type, Tuple, Optional, List, Callable
from src.config.settings import MAX_RETRY_ATTEMPTS, RETRY_BACKOFF_DELAY

logger = logging.getLogger(__name__)

def retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS, 
    backoff_ms=RETRY_BACKOFF_DELAY,
    exceptions_to_retry: Optional[Tuple[Type[Exception]]] = None,
    exceptions_to_not_retry: Optional[Tuple[Type[Exception]]] = None,
    jitter: bool = True
):
    """
    Decorator para tentar novamente uma função com backoff exponencial em caso de exceção.
    
    Args:
        max_attempts (int): Número máximo de tentativas.
        backoff_ms (int): Tempo inicial de espera em milissegundos.
        exceptions_to_retry (Tuple[Type[Exception]]): Exceções específicas para retry.
            Se None, todas as exceções serão consideradas para retry.
        exceptions_to_not_retry (Tuple[Type[Exception]]): Exceções específicas para não fazer retry.
            Se fornecido, estas exceções serão levantadas imediatamente sem retry.
        jitter (bool): Se True, adiciona jitter aleatório para evitar thundering herd.
        
    Returns:
        function: Função decorada com retry.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            last_exception = None
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Se temos uma lista de exceções que não devem ter retry
                    if exceptions_to_not_retry and isinstance(e, exceptions_to_not_retry):
                        logger.error(f"Exceção {type(e).__name__} não está na lista de retry. Levantando imediatamente.")
                        raise e
                    
                    # Se temos uma lista de exceções para retry, verificamos se a exceção atual está nela
                    if exceptions_to_retry and not isinstance(e, exceptions_to_retry):
                        logger.error(f"Exceção {type(e).__name__} não está na lista de exceções para retry.")
                        raise e
                        
                    attempts += 1
                    last_exception = e
                    
                    if attempts == max_attempts:
                        logger.error(f"Excedido número máximo de tentativas ({max_attempts}). Último erro: {e}")
                        raise e
                    
                    # Backoff exponencial com ou sem jitter
                    base_wait_time = (backoff_ms / 1000.0) * (2 ** (attempts - 1))
                    
                    # Adiciona jitter para evitar thundering herd
                    if jitter:
                        # Adiciona jitter de até 25% para cima ou para baixo
                        jitter_factor = 1.0 + (random.random() * 0.5 - 0.25)
                        wait_time = base_wait_time * jitter_factor
                    else:
                        wait_time = base_wait_time
                    
                    logger.warning(
                        f"Tentativa {attempts}/{max_attempts} falhou com {type(e).__name__}: {e}. "
                        f"Aguardando {wait_time:.2f}s antes da próxima tentativa..."
                    )
                    time.sleep(wait_time)
                    
            # Este ponto só seria alcançado se max_attempts fosse <= 0
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


def retry_with_condition(
    max_attempts=MAX_RETRY_ATTEMPTS,
    backoff_ms=RETRY_BACKOFF_DELAY,
    retry_condition: Callable[[Exception], bool] = lambda _: True,
    jitter: bool = True
):
    """
    Decorator para tentar novamente uma função com base em uma condição personalizada.
    
    Args:
        max_attempts (int): Número máximo de tentativas.
        backoff_ms (int): Tempo inicial de espera em milissegundos.
        retry_condition (Callable): Função que recebe a exceção e retorna
            True se deve tentar novamente, False caso contrário.
        jitter (bool): Se True, adiciona jitter aleatório para evitar thundering herd.
        
    Returns:
        function: Função decorada com retry.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            last_exception = None
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    last_exception = e
                    
                    # Verifica se deve tentar novamente com base na condição
                    if not retry_condition(e):
                        logger.error(f"Condição de retry não atendida para exceção: {e}")
                        raise e
                    
                    if attempts == max_attempts:
                        logger.error(f"Excedido número máximo de tentativas ({max_attempts}). Último erro: {e}")
                        raise e
                    
                    # Cálculo do tempo de espera igual ao retry_with_backoff
                    base_wait_time = (backoff_ms / 1000.0) * (2 ** (attempts - 1))
                    if jitter:
                        jitter_factor = 1.0 + (random.random() * 0.5 - 0.25)
                        wait_time = base_wait_time * jitter_factor
                    else:
                        wait_time = base_wait_time
                    
                    logger.warning(
                        f"Tentativa {attempts}/{max_attempts} falhou: {e}. "
                        f"Aguardando {wait_time:.2f}s antes da próxima tentativa..."
                    )
                    time.sleep(wait_time)
                    
            # Este ponto só seria alcançado se max_attempts fosse <= 0
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

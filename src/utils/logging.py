import logging
import os
from src.config.settings import LOGGING_CONFIG

def setup_logging():
    """
    Configura o sistema de logging para a aplicação.
    Cria o diretório de logs se não existir.
    """
    # Configura o logger raiz com as configurações básicas
    logging.basicConfig(
        level=LOGGING_CONFIG["level"],
        format=LOGGING_CONFIG["format"],
        datefmt=LOGGING_CONFIG["datefmt"]
    )
    
    # Cria um log handler para arquivo
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    file_handler = logging.FileHandler('logs/flowise-socket-service.log')
    file_handler.setLevel(LOGGING_CONFIG["level"])
    file_handler.setFormatter(logging.Formatter(
        LOGGING_CONFIG["format"],
        datefmt=LOGGING_CONFIG["datefmt"]
    ))
    
    # Adiciona o handler ao logger raiz
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    # Suprime logs muito detalhados de bibliotecas de terceiros
    logging.getLogger('pika').setLevel(logging.WARNING)
    logging.getLogger('redis').setLevel(logging.WARNING)
    
    logging.info("Sistema de logging configurado")

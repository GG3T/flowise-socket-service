#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Flowise Socket Service

Este serviço atua como intermediário entre o RabbitMQ e a API Flowise,
processando mensagens e gerenciando respostas.
"""

import sys
import signal
import logging
from src.utils.logging import setup_logging
from src.rabbitmq.config import RabbitMQConfig
from src.services.flowise_socket_service import FlowiseSocketService


def signal_handler(sig, frame):
    """Handler para capturar sinais de interrupção e encerrar o programa graciosamente."""
    logging.info("Sinal de interrupção recebido. Encerrando o serviço...")
    sys.exit(0)


def main():
    """Função principal que configura e inicia o serviço."""
    # Configura o sistema de logging
    setup_logging()
    
    logging.info("Iniciando Flowise Socket Service")
    
    # Registra handlers para sinais de interrupção
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Inicializa a configuração do RabbitMQ
        rabbitmq_config = RabbitMQConfig()
        
        # Cria e executa o serviço
        service = FlowiseSocketService(rabbitmq_config)
        service.run()
    except Exception as e:
        logging.error(f"Erro fatal no serviço: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

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
import time
import threading
from src.utils.logging import setup_logging
from src.rabbitmq.config import RabbitMQConfig
from src.services.flowise_socket_service import FlowiseSocketService
from src.services.instance_service import InstanceService
from src.config.settings import DB_CONFIG


def signal_handler(sig, frame):
    """Handler para capturar sinais de interrupção e encerrar o programa graciosamente."""
    logging.info("Sinal de interrupção recebido. Encerrando o serviço...")
    sys.exit(0)


def health_check_loop(instance_service, exit_event):
    """
    Loop de verificação de saúde periódica do pool de conexões.
    
    Args:
        instance_service (InstanceService): Serviço de instâncias para verificar.
        exit_event (threading.Event): Evento para sinalizar encerramento do loop.
    """
    interval = DB_CONFIG.get("health_check_interval", 300)  # Padrão: 5 minutos
    
    while not exit_event.is_set():
        try:
            logging.info("Executando verificação de saúde do pool de conexões...")
            healthy = instance_service.check_pool_health()
            if healthy:
                logging.info("Pool de conexões está saudável")
            else:
                logging.warning("Pool de conexões não está saudável. Foi recriado.")
                
            # Aguarda o próximo intervalo ou até que o evento de saída seja ativado
            exit_event.wait(interval)
        except Exception as e:
            logging.error(f"Erro durante verificação de saúde: {e}")
            # Aguarda um tempo mais curto em caso de erro
            exit_event.wait(60)


def main():
    """Função principal que configura e inicia o serviço."""
    # Configura o sistema de logging
    setup_logging()
    
    logging.info("Iniciando Flowise Socket Service")
    
    # Registra handlers para sinais de interrupção
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Evento para sinalizar encerramento do loop de verificação de saúde
    exit_event = threading.Event()
    
    try:
        # Inicializa a configuração do RabbitMQ
        rabbitmq_config = RabbitMQConfig()
        
        # Inicializa o serviço de instâncias
        instance_service = InstanceService()
        
        # Executa um pré-carregamento inicial de instâncias
        try:
            logging.info("Realizando pré-carregamento inicial de instâncias...")
            instance_service.preload_instances()
            logging.info("Pré-carregamento de instâncias concluído")
        except Exception as e:
            logging.error(f"Erro no pré-carregamento inicial de instâncias: {e}")
            # Não falha completamente, apenas continua sem o pré-carregamento
        
        # Inicia o thread de verificação de saúde em background
        health_check_thread = threading.Thread(
            target=health_check_loop,
            args=(instance_service, exit_event),
            daemon=True  # Thread em segundo plano
        )
        health_check_thread.start()
        
        # Cria e executa o serviço
        service = FlowiseSocketService(rabbitmq_config)
        
        # Executa o serviço
        try:
            service.run()
        finally:
            # Em caso de saída do loop principal, sinaliza para o thread de health check encerrar
            exit_event.set()
            # Aguarda o thread encerrar (com timeout)
            health_check_thread.join(timeout=5)
            
    except Exception as e:
        logging.error(f"Erro fatal no serviço: {e}", exc_info=True)
        # Sinaliza encerramento para qualquer thread em execução
        exit_event.set()
        sys.exit(1)


if __name__ == "__main__":
    main()

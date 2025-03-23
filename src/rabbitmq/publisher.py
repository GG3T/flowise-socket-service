import json
import logging
import pika
from src.rabbitmq.config import RabbitMQConfig

logger = logging.getLogger(__name__)

class RabbitMQPublisher:
    """Classe responsável por publicar mensagens no RabbitMQ."""
    
    def __init__(self, config: RabbitMQConfig):
        """
        Inicializa o publisher com a configuração do RabbitMQ.
        
        Args:
            config (RabbitMQConfig): Configuração de conexão do RabbitMQ.
        """
        self.config = config

    def publish_response(self, exchange: str, routing_key: str, payload: dict):
        """
        Publica uma resposta no exchange especificado com o routing key determinado.
        
        Args:
            exchange (str): Nome do exchange para publicação.
            routing_key (str): Routing key para direcionar a mensagem.
            payload (dict): Dados a serem publicados (serão convertidos para JSON).
        """
        connection = pika.BlockingConnection(self.config.get_connection_parameters())
        channel = connection.channel()
        
        # Utiliza o exchange_type 'topic' conforme a configuração existente
        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
        
        message = json.dumps(payload)
        channel.basic_publish(exchange=exchange, routing_key=routing_key, body=message)
        
        logger.info(f"Resposta publicada para {exchange}/{routing_key}")
        logger.debug(f"Payload: {payload}")
        
        connection.close()

import pika
from src.config.settings import RABBITMQ_CONFIG

class RabbitMQConfig:
    """Classe para gerenciar a configuração de conexão com o RabbitMQ."""
    
    def __init__(self):
        self.host = RABBITMQ_CONFIG["host"]
        self.port = RABBITMQ_CONFIG["port"]
        self.username = RABBITMQ_CONFIG["username"]
        self.password = RABBITMQ_CONFIG["password"]
        self.virtual_host = RABBITMQ_CONFIG["virtual_host"]

    def get_connection_parameters(self):
        """
        Cria e retorna os parâmetros de conexão para o RabbitMQ.
        
        Returns:
            pika.ConnectionParameters: Parâmetros para conexão com o RabbitMQ.
        """
        credentials = pika.PlainCredentials(self.username, self.password)
        return pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.virtual_host,
            credentials=credentials,
        )

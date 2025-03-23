import json
import logging
import pika
from src.rabbitmq.config import RabbitMQConfig
from src.services.flowise_processor_service import FlowiseProcessorService
from src.config.settings import RABBITMQ_CONFIG

logger = logging.getLogger(__name__)

class RabbitMQListener:
    """Classe para consumir mensagens da fila RabbitMQ e processá-las."""
    
    def __init__(self, queue_name: str, processor_service: FlowiseProcessorService, config: RabbitMQConfig):
        """
        Inicializa o listener com os componentes necessários.
        
        Args:
            queue_name (str): Nome da fila a ser consumida.
            processor_service (FlowiseProcessorService): Serviço para processamento de mensagens.
            config (RabbitMQConfig): Configuração do RabbitMQ.
        """
        self.queue_name = queue_name
        self.processor_service = processor_service
        self.config = config
        self.connection = None
        self.channel = None
        
        logger.info(f"RabbitMQListener inicializado para fila '{queue_name}'")
    
    def connect(self):
        """
        Estabelece conexão com o RabbitMQ e configura a fila.
        Configura também o prefetch count para limitar o número de mensagens
        não confirmadas que o consumer pode receber.
        """
        try:
            # Estabelece conexão com o RabbitMQ
            self.connection = pika.BlockingConnection(self.config.get_connection_parameters())
            self.channel = self.connection.channel()
            
            # Declara a fila como durável
            self.channel.queue_declare(queue=self.queue_name, durable=True)
            
            # Configura o prefetch count (mensagens não confirmadas por consumer)
            self.channel.basic_qos(prefetch_count=RABBITMQ_CONFIG["prefetch_count"])
            
            logger.info(f"Conectado ao RabbitMQ, fila '{self.queue_name}' com prefetch {RABBITMQ_CONFIG['prefetch_count']}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao conectar ao RabbitMQ: {e}", exc_info=True)
            if self.connection and self.connection.is_open:
                self.connection.close()
            return False
    
    def on_message(self, ch, method, properties, body):
        """
        Callback para processar mensagens recebidas.
        
        Args:
            ch: Canal do RabbitMQ.
            method: Método de entrega.
            properties: Propriedades da mensagem.
            body: Conteúdo da mensagem.
        """
        delivery_tag = method.delivery_tag
        try:
            decoded_body = body.decode('utf-8')
            message = json.loads(decoded_body)
            
            # Entrega a mensagem ao serviço de processamento
            self.processor_service.process_message(message)
            
            # Confirma o recebimento da mensagem apenas depois
            # de processá-la e colocá-la na fila de sessão
            ch.basic_ack(delivery_tag)
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e} | Body: {body.decode('utf-8', errors='replace')}")
            # Rejeita a mensagem e a coloca de volta na fila
            ch.basic_nack(delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Inicia o consumo de mensagens da fila."""
        try:
            if not self.connection or not self.connection.is_open:
                if not self.connect():
                    logger.error("Não foi possível conectar ao RabbitMQ. Abortando consumo.")
                    return
            
            self.channel.basic_consume(
                queue=self.queue_name, 
                on_message_callback=self.on_message, 
                auto_ack=False
            )
            
            logger.info(f"Iniciando consumo de mensagens na fila '{self.queue_name}'...")
            self.channel.start_consuming()
            
        except Exception as e:
            logger.error(f"Erro durante consumo de mensagens: {e}", exc_info=True)
            self.stop_consuming()
    
    def stop_consuming(self):
        """Para o consumo de mensagens e fecha a conexão."""
        try:
            if self.channel and self.channel.is_open:
                self.channel.stop_consuming()
                
            if self.connection and self.connection.is_open:
                self.connection.close()
                
            logger.info("Consumo de mensagens interrompido.")
            
        except Exception as e:
            logger.error(f"Erro ao interromper consumo: {e}", exc_info=True)

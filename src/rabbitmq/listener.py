import json
import logging
import pika
from src.rabbitmq.config import RabbitMQConfig
from src.rabbitmq.publisher import RabbitMQPublisher
from src.services.instance_service import InstanceService
from src.flowise.client import FlowiseClient
from src.flowise.processor import FlowiseStreamProcessor

logger = logging.getLogger(__name__)

class RabbitMQListener:
    """Classe para consumir mensagens da fila RabbitMQ e processá-las."""
    
    def __init__(self, queue_name: str, publisher: RabbitMQPublisher, 
                 config: RabbitMQConfig, instance_service: InstanceService):
        """
        Inicializa o listener com os componentes necessários.
        
        Args:
            queue_name (str): Nome da fila a ser consumida.
            publisher (RabbitMQPublisher): Publisher para publicar respostas.
            config (RabbitMQConfig): Configuração do RabbitMQ.
            instance_service (InstanceService): Serviço para obter dados da instância.
        """
        self.queue_name = queue_name
        self.publisher = publisher
        self.config = config
        self.instance_service = instance_service
        
        # Estabelece conexão com o RabbitMQ
        self.connection = pika.BlockingConnection(self.config.get_connection_parameters())
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        self.channel.basic_qos(prefetch_count=1)

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
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e} | Body: {body.decode('utf-8', errors='replace')}")
            ch.basic_nack(delivery_tag, requeue=True)
            return

        question = message.get("question", "")
        session_id = message.get("overrideConfig", {}).get("sessionId", "")
        instance = message.get("instance", "")
        logger.info(f"Mensagem recebida para session {session_id}, instance {instance}")

        # Consulta os dados da instância via InstanceService
        instance_data = self.instance_service.get_flowise_instance_data(instance)
        if not instance_data:
            logger.info(f"Instância não configurada: {instance}")
            ch.basic_ack(delivery_tag)
            return

        # Cria um novo cliente Flowise com os dados obtidos do cache ou banco de dados
        client = FlowiseClient(instance_data["base_url"], instance_data["chatflow_id"])
        processor = FlowiseStreamProcessor(client)
        
        try:
            response_data = processor.process_question(question, session_id)

            payload = {
                "response": json.dumps(response_data),
                "sessionId": session_id,
                "instance": instance
            }
            
            self.publisher.publish_response(
                exchange="flowise.exchange", 
                routing_key="flowise.response", 
                payload=payload
            )
            
            ch.basic_ack(delivery_tag)
            logger.info("Mensagem processada e ACK enviado.")
        except Exception as e:
            logger.error(f"Erro ao processar pergunta: {e}")
            ch.basic_nack(delivery_tag, requeue=True)

    def start_consuming(self):
        """Inicia o consumo de mensagens da fila."""
        self.channel.basic_consume(
            queue=self.queue_name, 
            on_message_callback=self.on_message, 
            auto_ack=False
        )
        
        logger.info(f"Escutando mensagens na fila '{self.queue_name}'...")
        self.channel.start_consuming()

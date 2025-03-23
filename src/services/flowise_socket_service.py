import logging
from src.rabbitmq.config import RabbitMQConfig
from src.rabbitmq.publisher import RabbitMQPublisher
from src.rabbitmq.listener import RabbitMQListener
from src.services.instance_service import InstanceService
from src.services.flowise_processor_service import FlowiseProcessorService
from src.config.settings import FLOWISE_QUEUE

logger = logging.getLogger(__name__)

class FlowiseSocketService:
    """Classe principal que integra as funcionalidades do serviço."""
    
    def __init__(self, rabbitmq_config: RabbitMQConfig):
        """
        Inicializa o serviço com todas as dependências necessárias.
        
        Args:
            rabbitmq_config (RabbitMQConfig): Configuração do RabbitMQ.
        """
        # Inicializa serviço de instância
        self.instance_service = InstanceService()
        
        # Inicializa o publisher para publicação de mensagens
        self.publisher = RabbitMQPublisher(rabbitmq_config)
        
        # Inicializa o serviço de processamento
        self.processor_service = FlowiseProcessorService(
            instance_service=self.instance_service,
            publisher=self.publisher
        )
        
        # Inicializa o listener para consumo de mensagens
        self.listener = RabbitMQListener(
            queue_name=FLOWISE_QUEUE,
            processor_service=self.processor_service,
            config=rabbitmq_config
        )
        
        # Pré-carrega as instâncias para o cache
        try:
            logger.info("Pré-carregando instâncias para o cache...")
            self.instance_service.preload_instances()
        except Exception as e:
            logger.error(f"Erro durante o pré-carregamento de instâncias: {e}")
        
        logger.info("FlowiseSocketService inicializado e pronto para executar")

    def run(self):
        """Inicia o serviço de processamento de mensagens."""
        logger.info("Iniciando Flowise Socket Service...")
        self.listener.start_consuming()
    
    def stop(self):
        """Para o serviço."""
        logger.info("Parando Flowise Socket Service...")
        self.listener.stop_consuming()

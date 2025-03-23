import logging
from src.rabbitmq.config import RabbitMQConfig
from src.rabbitmq.publisher import RabbitMQPublisher
from src.rabbitmq.listener import RabbitMQListener
from src.services.instance_service import InstanceService
from src.config.settings import FLOWISE_QUEUE

logger = logging.getLogger(__name__)

class FlowiseService:
    """Classe principal que integra as funcionalidades do serviço."""
    
    def __init__(self, rabbitmq_config: RabbitMQConfig):
        """
        Inicializa o serviço com todas as dependências necessárias.
        
        Args:
            rabbitmq_config (RabbitMQConfig): Configuração do RabbitMQ.
        """
        # Inicializa o publisher para publicação de mensagens
        self.publisher = RabbitMQPublisher(rabbitmq_config)
        
        # Instancia o InstanceService para consulta no cache e banco de dados
        self.instance_service = InstanceService()
        
        # Inicializa o listener para consumo de mensagens
        self.listener = RabbitMQListener(
            queue_name=FLOWISE_QUEUE,
            publisher=self.publisher,
            config=rabbitmq_config,
            instance_service=self.instance_service
        )
        
        logger.info("FlowiseService inicializado e pronto para executar")

    def run(self):
        """Inicia o serviço de processamento de mensagens."""
        logger.info("Iniciando serviço Flowise Socket...")
        self.listener.start_consuming()

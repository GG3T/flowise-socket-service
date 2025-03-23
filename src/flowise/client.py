import logging
from flowise import Flowise, PredictionData

logger = logging.getLogger(__name__)

class FlowiseClient:
    """Cliente para comunicação com a API Flowise."""
    
    def __init__(self, base_url: str, chatflow_id: str):
        """
        Inicializa o cliente Flowise.
        
        Args:
            base_url (str): URL base do Flowise (ex.: "https://flowise.numit.com.br")
            chatflow_id (str): ID do chatflow (ex.: "2e204889-5b60-4eef-873e-dbbd3dee4ec1")
        """
        self.chatflow_id = chatflow_id
        self.client = Flowise(base_url=base_url)
        logger.info(f"Cliente Flowise inicializado para {base_url} com chatflow {chatflow_id}")

    def create_prediction(self, question: str, sessionId: str, streaming: bool = True):
        """
        Cria a previsão utilizando o PredictionData com o overrideConfig definido.

        Args:
            question (str): Pergunta a ser enviada.
            sessionId (str): SessionId que será enviado no overrideConfig.
            streaming (bool): Se a resposta deve ser em streaming.
            
        Returns:
            Generator: Gerador com os chunks da resposta.
        """
        logger.debug(f"Criando previsão para: {question[:50]}...")
        
        prediction_data = PredictionData(
            chatflowId=self.chatflow_id,
            question=question,
            streaming=streaming,
            overrideConfig={"sessionId": sessionId}
        )
        
        return self.client.create_prediction(prediction_data)

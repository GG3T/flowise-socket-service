import logging
import requests
from src.utils.retry import retry_with_backoff
from src.utils.datetime import get_brasilia_datetime

logger = logging.getLogger(__name__)

class FlowiseClient:
    """Cliente para comunicação com a API Flowise."""
    
    def __init__(self, flowise_url: str):
        """
        Inicializa o cliente Flowise.
        
        Args:
            flowise_url (str): URL da API Flowise
        """
        self.flowise_url = flowise_url
        logger.info(f"Cliente Flowise inicializado para {flowise_url}")

    @retry_with_backoff()
    def create_prediction(self, question: str, sessionId: str, messageId: str):
        """
        Cria uma previsão enviando uma requisição para a API Flowise.

        Args:
            question (str): Pergunta a ser enviada.
            sessionId (str): SessionId da conversa.
            messageId (str): ID da mensagem.
            
        Returns:
            dict: Resposta da API Flowise.
        """
        logger.debug(f"Enviando pergunta para Flowise: {question[:50]}...")
        
        # Obtém a data e hora atual no fuso horário de Brasília
        current_datetime = get_brasilia_datetime()
        logger.info(f"Data e hora atual (Brasília): {current_datetime}")
        
        payload = {
            "question": question,
            "overrideConfig": {
                "sessionId": sessionId,
                "vars": {
                    "dateTime": current_datetime
                }
            },
            "messageId": messageId
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            self.flowise_url,
            headers=headers,
            json=payload,
            timeout=60  # 60 segundos de timeout
        )
        
        response.raise_for_status()  # Lança exceção se a resposta não for 2xx
        
        # Tenta fazer parse da resposta como JSON
        try:
            return response.json()
        except:
            # Se não for JSON, retorna o texto
            return response.text

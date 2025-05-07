import logging
import requests
import json
from typing import Optional, Union, Dict, Any
from src.utils.retry import retry_with_backoff, retry_with_condition
from src.utils.datetime import get_brasilia_datetime

logger = logging.getLogger(__name__)

class FlowiseClient:
    """Cliente para comunicação com a API Flowise."""
    
    def __init__(self, flowise_url: str, timeout: int = 60):
        """
        Inicializa o cliente Flowise.
        
        Args:
            flowise_url (str): URL da API Flowise
            timeout (int): Timeout em segundos para requisições HTTP
        """
        self.flowise_url = flowise_url
        self.timeout = timeout
        logger.info(f"Cliente Flowise inicializado para {flowise_url}")

    def _is_retriable_error(self, exception: Exception) -> bool:
        """
        Determina se uma exceção justifica uma nova tentativa.
        
        Args:
            exception (Exception): A exceção ocorrida
            
        Returns:
            bool: True se deve tentar novamente, False caso contrário
        """
        # Erros de conexão e timeout são retriáveis
        if isinstance(exception, (requests.ConnectionError, 
                                  requests.Timeout)):
            return True
            
        # Erros de servidor (5xx) são retriáveis
        if isinstance(exception, requests.HTTPError):
            status_code = exception.response.status_code
            return 500 <= status_code < 600
            
        return False

    @retry_with_condition(max_attempts=3, retry_condition=_is_retriable_error)
    def create_prediction(self, question: str, sessionId: str, messageId: str) -> Union[Dict[str, Any], str]:
        """
        Cria uma previsão enviando uma requisição para a API Flowise.

        Args:
            question (str): Pergunta a ser enviada.
            sessionId (str): SessionId da conversa.
            messageId (str): ID da mensagem.
            
        Returns:
            Union[Dict[str, Any], str]: Resposta da API Flowise.
        """
        logger.debug(f"Enviando pergunta para Flowise: {question[:50]}...")
        
        # Obtém a data e hora atual no fuso horário de Brasília
        current_datetime = get_brasilia_datetime()
        logger.info(f"Data e hora atual (Brasília): {current_datetime}")

        # Prepara o payload da requisição
        payload = {
            "question": question,
            "overrideConfig": {
                "sessionId": sessionId,
                "vars": {
                    "dateTime": current_datetime
                    # TODO ENVIAR SUMMARY
                }
            },
            "messageId": messageId
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            # Envia a requisição com timeout configurável
            response = requests.post(
                self.flowise_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            # Verifica se a resposta é bem-sucedida
            response.raise_for_status()
            
            # Tenta fazer parse da resposta como JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                # Se não for JSON, retorna o texto
                return response.text
                
        except requests.HTTPError as e:
            # Log detalhado para erros HTTP
            status_code = e.response.status_code
            logger.error(f"Erro HTTP {status_code} ao chamar Flowise: {e}")
            
            # Para erros 4xx, não devemos tentar novamente
            if 400 <= status_code < 500:
                logger.warning(f"Erro cliente (4xx): {e.response.text[:200]}")
            
            # Para erros 5xx, o retry_with_condition já cuidará disso
            raise
            
        except requests.ConnectionError as e:
            logger.error(f"Erro de conexão ao chamar Flowise: {e}")
            raise
            
        except requests.Timeout as e:
            logger.error(f"Timeout ao chamar Flowise: {e}")
            raise
            
        except Exception as e:
            logger.error(f"Erro inesperado ao chamar Flowise: {e}", exc_info=True)
            raise

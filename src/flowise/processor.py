import json
import logging
from src.flowise.client import FlowiseClient

logger = logging.getLogger(__name__)

class FlowiseStreamProcessor:
    """Classe responsável por processar a resposta em streaming do Flowise."""
    
    def __init__(self, flowise_client: FlowiseClient):
        """
        Inicializa o processador com o cliente Flowise.
        
        Args:
            flowise_client (FlowiseClient): Cliente Flowise para envio de perguntas.
        """
        self.flowise_client = flowise_client

    def process_question(self, question: str, sessionId: str) -> dict:
        """
        Envia a pergunta para o Flowise e monta um dicionário com a resposta.

        Args:
            question (str): Pergunta enviada.
            sessionId (str): SessionId para overrideConfig.
            
        Returns:
            dict: Dicionário com a resposta estruturada.
        """
        logger.info("Enviando pergunta para o Flowise e aguardando resposta em streaming...")
        streaming_response = self.flowise_client.create_prediction(question, sessionId, streaming=True)

        result = {
            "text": "",
            "question": question,
            "chatId": None,
            "chatMessageId": None,
            "sessionId": None,
            "memoryType": None,
            "agentReasoning": []
        }

        for chunk in streaming_response:
            # Se o chunk for uma string, converte para dicionário
            if isinstance(chunk, str):
                try:
                    chunk = json.loads(chunk)
                except Exception as e:
                    logger.error(f"Erro ao converter chunk para JSON: {e}")
                    continue
                    
            logger.debug(f"Chunk recebido: {chunk}")
            event = chunk.get("event")
            data = chunk.get("data")

            if event == "token":
                if isinstance(data, str):
                    result["text"] += data
            elif event == "agentReasoning":
                if isinstance(data, list):
                    result["agentReasoning"].extend(data)
            elif event == "metadata":
                if isinstance(data, dict):
                    result["chatId"] = data.get("chatId")
                    result["chatMessageId"] = data.get("chatMessageId")
                    if data.get("question"):
                        result["question"] = data.get("question")
                    result["sessionId"] = data.get("sessionId")
                    result["memoryType"] = data.get("memoryType")
            # Processar outros eventos, se necessário
            elif event == "start":
                # Processa mensagens iniciais se necessário
                pass
            elif event == "end":
                pass

        logger.info("Resposta completa montada")
        logger.debug(f"Resposta: {result}")
        return result

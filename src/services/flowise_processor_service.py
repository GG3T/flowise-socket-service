import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import Dict, Optional
from src.flowise.client import FlowiseClient
from src.services.instance_service import InstanceService
from src.rabbitmq.publisher import RabbitMQPublisher
from src.config.settings import THREAD_POOL_SIZE, FLOWISE_EXCHANGE, FLOWISE_RESPONSE_ROUTING_KEY

logger = logging.getLogger(__name__)

class FlowiseProcessorService:
    """
    Serviço responsável por processar mensagens do Flowise utilizando
    um thread pool e filas por sessão para garantir processamento sequencial.
    """
    
    def __init__(self, instance_service: InstanceService, publisher: RabbitMQPublisher):
        """
        Inicializa o serviço de processamento.
        
        Args:
            instance_service (InstanceService): Serviço para obter URLs das instâncias.
            publisher (RabbitMQPublisher): Publisher para enviar respostas.
        """
        self.instance_service = instance_service
        self.publisher = publisher
        
        # Thread pool para processamento das mensagens
        self.executor = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)
        
        # Dicionário de filas por sessionId
        # Chave: sessionId, Valor: Queue de mensagens
        self.processing_queues: Dict[str, Queue] = {}
        
        # Lock para garantir acesso seguro ao dicionário de filas
        self.queue_lock = threading.Lock()
        
        # Dicionário para rastrear threads ativas por sessionId
        # Chave: sessionId, Valor: flag de thread ativa
        self.active_threads: Dict[str, bool] = {}
        self.active_threads_lock = threading.Lock()
        
        # Cache de instâncias problemáticas para evitar logs excessivos
        self.problem_instances: Dict[str, float] = {}
        
        # Inicia um thread para limpeza periódica das filas inativas
        self.cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
        self.cleanup_thread.start()
        
        logger.info(f"FlowiseProcessorService inicializado com pool de {THREAD_POOL_SIZE} threads")

    def process_message(self, message: dict):
        """
        Processa uma mensagem recebida do RabbitMQ.
        Garante que mensagens do mesmo sessionId sejam processadas em ordem.
        
        Args:
            message (dict): Mensagem recebida.
        """
        try:
            # Extrai informações da mensagem
            question = message.get("question", "")
            overrideConfig = message.get("overrideConfig", {})
            sessionId = overrideConfig.get("sessionId", "")
            instance = message.get("instance", "")
            messageId = message.get("messageId", "")
            
            logger.info(f"Processando mensagem para session {sessionId}, instance {instance}, messageId {messageId}")
            
            # Adiciona à fila específica da sessão
            with self.queue_lock:
                if sessionId not in self.processing_queues:
                    self.processing_queues[sessionId] = Queue()
                
                # Coloca a mensagem na fila
                self.processing_queues[sessionId].put(message)
            
            # Inicia uma thread para processar a fila se não houver uma ativa
            with self.active_threads_lock:
                if sessionId not in self.active_threads or not self.active_threads[sessionId]:
                    self.active_threads[sessionId] = True
                    self.executor.submit(self._process_queue, sessionId)
                    
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}", exc_info=True)
    
    def _process_queue(self, sessionId: str):
        """
        Processa as mensagens na fila para um determinado sessionId.
        
        Args:
            sessionId (str): ID da sessão a ser processada.
        """
        try:
            while True:
                # Obtém a fila para a sessão
                with self.queue_lock:
                    if sessionId not in self.processing_queues:
                        break
                    
                    queue = self.processing_queues[sessionId]
                    
                    # Se a fila estiver vazia, marca a thread como inativa e termina
                    if queue.empty():
                        with self.active_threads_lock:
                            self.active_threads[sessionId] = False
                        break
                    
                    # Obtem a próxima mensagem da fila
                    message = queue.get()
                
                # Processa a mensagem
                self._send_to_flowise(message)
                
        except Exception as e:
            logger.error(f"Erro ao processar fila para sessão {sessionId}: {e}", exc_info=True)
            # Marca thread como inativa em caso de erro
            with self.active_threads_lock:
                self.active_threads[sessionId] = False
    
    def _get_instance_url(self, instance_name: str, retry_attempt=0) -> Optional[str]:
        """
        Obtém a URL da instância, com verificação de erros e fallback.
        
        Args:
            instance_name (str): Nome da instância.
            retry_attempt (int): Número da tentativa atual (para evitar recursão infinita).
            
        Returns:
            Optional[str]: URL da instância ou None se não encontrada.
        """
        # Primeiro, tenta obter a URL normalmente
        flowise_url = self.instance_service.get_flowise_url(instance_name)
        
        # Se não encontrou e essa é a primeira tentativa, tenta recarregar
        if not flowise_url and retry_attempt == 0:
            try:
                # Tentativa de recarregar todas as instâncias
                logger.info(f"Instância '{instance_name}' não encontrada no cache. Recarregando todas...")
                
                # Verifica a saúde do pool de conexões do serviço de instâncias
                healthy = self.instance_service.check_pool_health()
                if not healthy:
                    logger.warning("Pool de conexões não está saudável após verificação")
                
                # Tenta recarregar as instâncias
                self.instance_service.preload_instances()
                
                # Tenta novamente após recarregar (com controle de recursão)
                return self._get_instance_url(instance_name, retry_attempt=1)
            except Exception as e:
                logger.error(f"Erro ao recarregar instâncias: {e}")
        
        return flowise_url
    
    def _send_to_flowise(self, message: dict):
        """
        Envia a mensagem para o Flowise e publica a resposta.
        
        Args:
            message (dict): Mensagem a ser enviada.
        """
        try:
            question = message.get("question", "")
            overrideConfig = message.get("overrideConfig", {})
            sessionId = overrideConfig.get("sessionId", "")
            instance = message.get("instance", "")
            messageId = message.get("messageId", "")
            
            # Obtém a URL da instância com tratamento de erro aprimorado
            flowise_url = self._get_instance_url(instance)
            
            if not flowise_url:
                # Evita logar muitas mensagens para a mesma instância
                current_time = time.time()
                
                # Só loga avisos a cada 5 minutos por instância
                if instance not in self.problem_instances or (current_time - self.problem_instances[instance]) > 300:
                    logger.warning(f"Instância '{instance}' não configurada. Ignorando mensagem.")
                    self.problem_instances[instance] = current_time
                    
                # Envia uma resposta de erro para que o cliente não fique esperando
                error_payload = {
                    "response": json.dumps({
                        "error": True,
                        "message": f"Instância '{instance}' não encontrada ou não configurada."
                    }),
                    "sessionId": sessionId,
                    "instance": instance,
                    "messageId": messageId
                }
                
                self.publisher.publish_response(
                    exchange=FLOWISE_EXCHANGE,
                    routing_key=FLOWISE_RESPONSE_ROUTING_KEY,
                    payload=error_payload
                )
                
                return
            
            # Cria cliente Flowise e envia a requisição
            client = FlowiseClient(flowise_url)
            logger.info(f"Enviando requisição para Flowise: {instance}, session {sessionId}")
            
            response = client.create_prediction(question, sessionId, messageId)
            logger.info(f"Resposta recebida de Flowise para session {sessionId}")
            
            # Cria payload para resposta
            payload = {
                "response": json.dumps(response) if isinstance(response, dict) else response,
                "sessionId": sessionId,
                "instance": instance,
                "messageId": messageId
            }
            
            # Publica a resposta
            self.publisher.publish_response(
                exchange=FLOWISE_EXCHANGE,
                routing_key=FLOWISE_RESPONSE_ROUTING_KEY,
                payload=payload
            )
            
            logger.info(f"Resposta publicada para session {sessionId}, messageId {messageId}")
            
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para Flowise: {e}", exc_info=True)
            
            # Tenta enviar resposta de erro em caso de falha
            try:
                error_payload = {
                    "response": json.dumps({
                        "error": True,
                        "message": f"Erro ao processar mensagem: {str(e)}"
                    }),
                    "sessionId": sessionId,
                    "instance": instance,
                    "messageId": messageId
                }
                
                self.publisher.publish_response(
                    exchange=FLOWISE_EXCHANGE,
                    routing_key=FLOWISE_RESPONSE_ROUTING_KEY,
                    payload=error_payload
                )
                
                logger.info(f"Resposta de erro publicada para session {sessionId}, messageId {messageId}")
            except Exception as inner_e:
                logger.error(f"Não foi possível enviar resposta de erro: {inner_e}")
                
    def _periodic_cleanup(self):
        """
        Thread que executa limpeza periódica de recursos não utilizados.
        Remove sessões inativas e esvazia filas antigas.
        """
        while True:
            try:
                self.cleanup_inactive_sessions()
                # Executa limpeza a cada 15 minutos
                time.sleep(900)
            except Exception as e:
                logger.error(f"Erro durante limpeza periódica: {e}")
                # Se houver falha, espera um tempo menor e tenta novamente
                time.sleep(60)
    
    def cleanup_inactive_sessions(self, max_idle_time=3600):
        """
        Remove sessões inativas do dicionário de filas.
        
        Args:
            max_idle_time (int): Tempo máximo de inatividade em segundos (padrão: 1 hora).
        """
        try:
            logger.info("Iniciando limpeza de sessões inativas")
            
            with self.queue_lock:
                inactive_sessions = []
                for session_id, queue in self.processing_queues.items():
                    with self.active_threads_lock:
                        is_active = self.active_threads.get(session_id, False)
                    
                    if not is_active and queue.empty():
                        inactive_sessions.append(session_id)
                
                # Remove sessões inativas
                for session_id in inactive_sessions:
                    del self.processing_queues[session_id]
                    with self.active_threads_lock:
                        if session_id in self.active_threads:
                            del self.active_threads[session_id]
                
                logger.info(f"Limpeza finalizada: {len(inactive_sessions)} sessões inativas removidas")
                
        except Exception as e:
            logger.error(f"Erro ao limpar sessões inativas: {e}")

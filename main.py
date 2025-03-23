import json
import time
import pika
import logging
import redis
import psycopg2
from flowise import Flowise, PredictionData

# Configuração do logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------------
# Configuração do RabbitMQ
# -----------------------------------------------------------------------------------
class RabbitMQConfig:
    def __init__(self):
        self.host = "rabbitmq.chatgmia.org"
        self.port = 5672
        self.username = "admin"
        self.password = "8a2cfcdbb1b87da5a47a2e681ca46991"
        self.virtual_host = "/"

    def get_connection_parameters(self):
        credentials = pika.PlainCredentials(self.username, self.password)
        return pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.virtual_host,
            credentials=credentials,
        )

# -----------------------------------------------------------------------------------
# Serviço para consulta da instância via Redis e PostgreSQL
# -----------------------------------------------------------------------------------
class InstanceService:
    def __init__(self):
        # Configuração do Redis
        self.redis_client = redis.Redis(
            host='golden-condor-16660.upstash.io',
            port=6379,
            password='AUEUAAIjcDEwZmQwODE0NDEzMjA0OGVkOWNjZTdhYzcyYzY5NzhkZXAxMA',
            ssl=True
        )
        # Conexão com o PostgreSQL
        self.db_conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password="71d14724653158e0e40fd03f522ac11c",
            host="178.156.146.193",
            port=5432
        )

    def get_flowise_instance_data(self, instance_name: str) -> dict:
        """
        Consulta o cache Redis para obter os dados da instância (base_url e chatflow_id).
        Caso não exista ou os dados estejam inválidos (None), consulta o banco de dados e atualiza o cache com TTL de 12 horas.
        """
        cached_data = self.redis_client.get(instance_name)
        if cached_data:
            try:
                data = json.loads(cached_data.decode('utf-8'))
                # Verifica se os dados possuem as chaves e se os valores não são None
                if data.get("base_url") is not None and data.get("chatflow_id") is not None:
                    logger.info("Dados obtidos do cache para a instância %s.", instance_name)
                    return data
                else:
                    raise ValueError("Dados inválidos: base_url ou chatflow_id são None.")
            except Exception as e:
                logger.error("Erro ao decodificar ou validar dados do cache para a instância %s: %s. Dados: %s",
                             instance_name, e, cached_data.decode('utf-8', errors='replace'))
                # Remove os dados inválidos do cache
                self.redis_client.delete(instance_name)

        logger.info("Dados não encontrados ou inválidos no cache. Consultando o banco de dados para a instância %s.",
                    instance_name)
        with self.db_conn.cursor() as cur:
            cur.execute("SELECT base_url, chatflow_id FROM flowise_instance WHERE instance_name = %s", (instance_name,))
            row = cur.fetchone()
            if row:
                base_url, chatflow_id = row[0], row[1]
                # Se os dados do banco também estiverem vazios, loga e retorna None.
                if base_url is None or chatflow_id is None:
                    logger.info("Instância %s não configurada no banco de dados (dados vazios).", instance_name)
                    return None
                data = {"base_url": base_url, "chatflow_id": chatflow_id}
                # Atualiza o Redis com um TTL de 12 horas (43200 segundos)
                self.redis_client.set(instance_name, json.dumps(data), ex=43200)
                logger.info("Cache atualizado para a instância %s.", instance_name)
                return data
            else:
                logger.info("Instância %s não configurada no banco de dados.", instance_name)
                return None


# -----------------------------------------------------------------------------------
# Classe que encapsula a comunicação com o Flowise
# -----------------------------------------------------------------------------------
class FlowiseClient:
    def __init__(self, base_url: str, chatflow_id: str):
        """
        :param base_url: URL base do Flowise (ex.: "https://flowise.numit.com.br")
        :param chatflow_id: ID do chatflow (ex.: "2e204889-5b60-4eef-873e-dbbd3dee4ec1")
        """
        self.chatflow_id = chatflow_id
        self.client = Flowise(base_url=base_url)

    def create_prediction(self, question: str, sessionId: str, streaming: bool = True):
        """
        Cria a previsão utilizando o PredictionData com o overrideConfig definido.

        :param question: Pergunta a ser enviada.
        :param sessionId: SessionId que será enviado no overrideConfig.
        :param streaming: Se a resposta deve ser em streaming.
        :return: Gerador com os chunks da resposta.
        """
        prediction_data = PredictionData(
            chatflowId=self.chatflow_id,
            question=question,
            streaming=streaming,
            overrideConfig={"sessionId": sessionId}
        )
        return self.client.create_prediction(prediction_data)


# -----------------------------------------------------------------------------------
# Classe responsável por processar a resposta em streaming do Flowise
# -----------------------------------------------------------------------------------
class FlowiseStreamProcessor:
    def __init__(self, flowise_client: FlowiseClient):
        self.flowise_client = flowise_client

    def process_question(self, question: str, sessionId: str) -> dict:
        """
        Envia a pergunta para o Flowise e monta um dicionário com a resposta.

        :param question: Pergunta enviada.
        :param sessionId: SessionId para overrideConfig.
        :return: Dicionário com a resposta estruturada.
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
                    logger.error("Erro ao converter chunk para JSON: %s", e)
                    continue
            logger.info("Chunk recebido: %s", chunk)
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

        logger.info("Resposta completa montada: %s", result)
        return result


# -----------------------------------------------------------------------------------
# Classe responsável por publicar mensagens no RabbitMQ
# -----------------------------------------------------------------------------------
class RabbitMQPublisher:
    def __init__(self, config: RabbitMQConfig):
        self.config = config

    def publish_response(self, exchange: str, routing_key: str, payload: dict):
        connection = pika.BlockingConnection(self.config.get_connection_parameters())
        channel = connection.channel()
        # Utilize o exchange_type 'topic' conforme a configuração existente
        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
        message = json.dumps(payload)
        channel.basic_publish(exchange=exchange, routing_key=routing_key, body=message)
        logger.info("Resposta publicada: %s", payload)
        connection.close()


# -----------------------------------------------------------------------------------
# Classe que consome mensagens da fila RabbitMQ e processa cada mensagem
# -----------------------------------------------------------------------------------
class RabbitMQListener:
    def __init__(self, queue_name: str, publisher: RabbitMQPublisher, config: RabbitMQConfig, instance_service):
        self.queue_name = queue_name
        self.publisher = publisher
        self.config = config
        self.instance_service = instance_service  # Agora a instância está disponível para uso
        self.connection = pika.BlockingConnection(self.config.get_connection_parameters())
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        self.channel.basic_qos(prefetch_count=1)

    def on_message(self, ch, method, properties, body):
        delivery_tag = method.delivery_tag
        try:
            decoded_body = body.decode('utf-8')
            message = json.loads(decoded_body)
        except Exception as e:
            logger.error("Erro ao processar mensagem: %s | Body: %s", e, body.decode('utf-8', errors='replace'))
            ch.basic_nack(delivery_tag, requeue=True)
            return

        question = message.get("question", "")
        session_id = message.get("overrideConfig", {}).get("sessionId", "")
        instance = message.get("instance", "")
        logger.info("Mensagem recebida para session %s, instance %s", session_id, instance)

        # Consulta os dados da instância via InstanceService
        instance_data = self.instance_service.get_flowise_instance_data(instance)
        if not instance_data:
            logger.info("Instância não configurada: %s", instance)
            ch.basic_ack(delivery_tag)
            return

        # Cria um novo cliente Flowise com os dados obtidos do cache ou banco de dados
        client = FlowiseClient(instance_data["base_url"], instance_data["chatflow_id"])
        processor = FlowiseStreamProcessor(client)
        response_data = processor.process_question(question, session_id)

        payload = {
            "response": json.dumps(response_data),
            "sessionId": session_id,
            "instance": instance
        }
        self.publisher.publish_response(exchange="flowise.exchange", routing_key="flowise.response", payload=payload)
        ch.basic_ack(delivery_tag)
        logger.info("Mensagem processada e ACK enviado.")

    def start_consuming(self):
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.on_message, auto_ack=False)
        logger.info("Escutando mensagens na fila '%s'...", self.queue_name)
        self.channel.start_consuming()


# -----------------------------------------------------------------------------------
# Classe principal que integra as funcionalidades do serviço
# -----------------------------------------------------------------------------------
class FlowiseService:
    def __init__(self, rabbitmq_config: RabbitMQConfig):
        self.publisher = RabbitMQPublisher(rabbitmq_config)
        # Instancia o InstanceService para consulta no cache e banco de dados
        self.instance_service = InstanceService()
        self.listener = RabbitMQListener(
            queue_name="flowise.queue",
            publisher=self.publisher,
            config=rabbitmq_config,
            instance_service=self.instance_service  # Passa a instância corretamente
        )

    def run(self):
        self.listener.start_consuming()

# -----------------------------------------------------------------------------------
# Execução do serviço
# -----------------------------------------------------------------------------------
def main():

    rabbitmq_config = RabbitMQConfig()
    service = FlowiseService(rabbitmq_config)
    service.run()


if __name__ == "__main__":
    main()

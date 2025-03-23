import json
import logging
import redis
import psycopg2
from src.config.settings import REDIS_CONFIG, DB_CONFIG, CACHE_TTL

logger = logging.getLogger(__name__)

class InstanceService:
    """Serviço para consulta da instância via Redis e PostgreSQL."""
    
    def __init__(self):
        """Inicializa o serviço com conexões ao Redis e PostgreSQL."""
        # Configuração do Redis
        self.redis_client = redis.Redis(
            host=REDIS_CONFIG["host"],
            port=REDIS_CONFIG["port"],
            password=REDIS_CONFIG["password"],
            ssl=REDIS_CONFIG["ssl"]
        )
        
        # Conexão com o PostgreSQL
        self.db_conn = psycopg2.connect(
            dbname=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"]
        )
        
        logger.info("InstanceService inicializado com conexões Redis e PostgreSQL")

    def get_flowise_instance_data(self, instance_name: str) -> dict:
        """
        Consulta o cache Redis para obter os dados da instância (base_url e chatflow_id).
        Caso não exista ou os dados estejam inválidos (None), consulta o banco de dados
        e atualiza o cache com TTL configurado.
        
        Args:
            instance_name (str): Nome da instância a ser consultada.
            
        Returns:
            dict: Dicionário com base_url e chatflow_id ou None se não encontrado.
        """
        # Tenta obter do cache Redis
        cached_data = self.redis_client.get(instance_name)
        if cached_data:
            try:
                data = json.loads(cached_data.decode('utf-8'))
                # Verifica se os dados possuem as chaves e se os valores não são None
                if data.get("base_url") is not None and data.get("chatflow_id") is not None:
                    logger.info(f"Dados obtidos do cache para a instância {instance_name}")
                    return data
                else:
                    raise ValueError("Dados inválidos: base_url ou chatflow_id são None")
            except Exception as e:
                logger.error(f"Erro ao decodificar ou validar dados do cache para a instância {instance_name}: {e}. "
                             f"Dados: {cached_data.decode('utf-8', errors='replace')}")
                # Remove os dados inválidos do cache
                self.redis_client.delete(instance_name)

        # Se não encontrou no cache ou dados inválidos, consulta o banco de dados
        logger.info(f"Dados não encontrados ou inválidos no cache. "
                    f"Consultando o banco de dados para a instância {instance_name}")
        
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("SELECT base_url, chatflow_id FROM flowise_instance WHERE instance_name = %s", 
                           (instance_name,))
                row = cur.fetchone()
                
                if row:
                    base_url, chatflow_id = row[0], row[1]
                    # Se os dados do banco também estiverem vazios, loga e retorna None
                    if base_url is None or chatflow_id is None:
                        logger.info(f"Instância {instance_name} não configurada no banco de dados (dados vazios)")
                        return None
                        
                    data = {"base_url": base_url, "chatflow_id": chatflow_id}
                    # Atualiza o Redis com um TTL configurado
                    self.redis_client.set(instance_name, json.dumps(data), ex=CACHE_TTL)
                    logger.info(f"Cache atualizado para a instância {instance_name}")
                    return data
                else:
                    logger.info(f"Instância {instance_name} não configurada no banco de dados")
                    return None
        except Exception as e:
            logger.error(f"Erro ao consultar banco de dados para instância {instance_name}: {e}")
            return None

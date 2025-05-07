import json
import logging
import redis
import psycopg2
import psycopg2.pool
import psycopg2.extras
import time
import threading
from src.config.settings import REDIS_CONFIG, DB_CONFIG, CACHE_TTL
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

class InstanceService:
    """Serviço para consulta da instância via Redis e PostgreSQL."""
    
    def __init__(self):
        """Inicializa o serviço com conexões ao Redis e PostgreSQL."""
        # Configuração do Redis
        try:
            self.redis_client = redis.Redis(
                host=REDIS_CONFIG["host"],
                port=REDIS_CONFIG["port"],
                password=REDIS_CONFIG["password"],
                ssl=REDIS_CONFIG["ssl"],
                socket_timeout=REDIS_CONFIG["socket_timeout"],
                socket_keepalive=REDIS_CONFIG["socket_keepalive"],
                socket_connect_timeout=REDIS_CONFIG["socket_connect_timeout"]
            )
            # Teste de conexão
            self.redis_client.ping()
            logger.info("Conexão com Redis estabelecida com sucesso")
        except Exception as e:
            logger.error(f"Erro ao inicializar conexão com Redis: {e}")
            self.redis_client = None
        
        # Pool de conexões com o PostgreSQL
        self.db_pool = None
        self._create_db_pool()
        
        # Lock para operações no pool de conexões
        self.pool_lock = threading.Lock()
        
        # Cache em memória local (fallback para quando o Redis não estiver disponível)
        self.local_cache: Dict[str, Tuple[str, float]] = {}
        self.local_cache_ttl = CACHE_TTL  # Mesmo TTL do Redis
        
        # Cache de emergência para instâncias críticas (usado quando DB e Redis falham)
        self._fallback_emergency_cache = {}
        
        # Carrega instâncias ao inicializar
        self.preload_instances()
        
        logger.info("InstanceService inicializado")
        
    def _create_db_pool(self):
        """Cria ou recria o pool de conexões do PostgreSQL."""
        try:
            # Se já existe um pool, fecha-o primeiro
            if self.db_pool:
                try:
                    self.db_pool.closeall()
                except Exception as e:
                    logger.warning(f"Erro ao fechar pool existente: {e}")
            
            # Cria um novo pool
            self.db_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=DB_CONFIG["min_connections"],
                maxconn=DB_CONFIG["max_connections"],
                dbname=DB_CONFIG["dbname"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                connect_timeout=DB_CONFIG["connect_timeout"],
                application_name="flowise-socket-service"
            )
            logger.info("Pool de conexões PostgreSQL inicializado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao inicializar pool de conexões PostgreSQL: {e}")
            self.db_pool = None

    def _reset_connection_pool(self):
        """Recria o pool de conexões de forma segura usando o lock."""
        with self.pool_lock:
            self._create_db_pool()
            
    def check_pool_health(self):
        """
        Verifica a saúde do pool de conexões e o recria se necessário.
        
        Returns:
            bool: True se o pool está saudável, False caso contrário
        """
        if not self.db_pool:
            logger.warning("Pool de conexões não existe. Tentando recriar...")
            self._reset_connection_pool()
            return False
            
        try:
            # Protege o acesso ao pool com lock
            with self.pool_lock:
                # Tenta obter uma conexão para testar
                connection = self.db_pool.getconn()
                
                # Verifica se a conexão está ativa
                if connection.closed:
                    logger.warning("Conexão obtida está fechada. Recriando pool...")
                    self.db_pool.putconn(connection)
                    self._reset_connection_pool()
                    return False
                    
                try:
                    # Executa uma query simples para testar
                    cursor = connection.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    
                    # Devolve a conexão ao pool
                    self.db_pool.putconn(connection)
                    return True
                except Exception as e:
                    logger.warning(f"Erro ao executar consulta de teste: {e}")
                    try:
                        # Fecha a conexão com problema
                        connection.close()
                    except:
                        pass
                    self._reset_connection_pool()
                    return False
        except Exception as e:
            logger.error(f"Erro na verificação de saúde do pool: {e}")
            self._reset_connection_pool()
            return False

    def get_flowise_url(self, instance_name: str) -> Optional[str]:
        """
        Consulta o cache Redis para obter a URL da instância Flowise.
        Caso não exista ou os dados estejam inválidos, consulta o banco de dados
        e atualiza o cache com TTL configurado.
        
        Args:
            instance_name (str): Nome da instância a ser consultada.
            
        Returns:
            Optional[str]: URL da instância Flowise ou None se não encontrado.
        """
        cache_key = f"flowise:instance:{instance_name}"
        logger.info(f"Cache_key: {cache_key}")

        # 1. Tenta obter do cache Redis
        url = self._get_from_redis_cache(cache_key)
        if url:
            return url
            
        # 2. Tenta obter do cache local (memória)
        url = self._get_from_local_cache(cache_key)
        if url:
            return url
            
        # 3. Tenta obter do banco de dados
        url = self._get_from_database(instance_name)
        if url:
            # 4. Atualiza o cache (Redis e local)
            self._update_cache(cache_key, url)
            return url
        
        # 5. Tenta obter do cache de emergência se tudo falhar
        if instance_name in self._fallback_emergency_cache:
            logger.warning(f"Usando URL de fallback para '{instance_name}' devido a falha no banco e caches")
            return self._fallback_emergency_cache[instance_name]
            
        # Se chegou aqui, não encontrou a instância
        return None

    def _get_from_redis_cache(self, cache_key: str) -> Optional[str]:
        """Tenta obter a URL da instância do cache Redis."""
        if not self.redis_client:
            return None
            
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                url = cached_data.decode('utf-8')
                if url and url.strip():
                    logger.info(f"URL obtida do cache Redis: {url}")
                    return url
                else:
                    # Remove do cache se for valor vazio
                    self.redis_client.delete(cache_key)
        except Exception as e:
            logger.warning(f"Erro ao consultar cache Redis: {e}")
            
        return None
        
    def _get_from_local_cache(self, cache_key: str) -> Optional[str]:
        """Tenta obter a URL da instância do cache local."""
        if cache_key in self.local_cache:
            url, expiry_time = self.local_cache[cache_key]
            # Verifica se o cache ainda é válido
            if time.time() < expiry_time:
                logger.info(f"URL obtida do cache local: {url}")
                return url
            else:
                # Remove do cache local se expirou
                del self.local_cache[cache_key]
                
        return None
        
    def _get_from_database(self, instance_name: str) -> Optional[str]:
        """
        Consulta o banco de dados para obter a URL da instância.
        """
        # Verifica a saúde do pool antes de tentar obter uma conexão
        if not self.db_pool:
            logger.error("Pool de conexão PostgreSQL não disponível")
            self._reset_connection_pool()
            return None
        
        # Se o pool está em uso intenso, verifica sua saúde
        with self.pool_lock:
            try:
                if hasattr(self.db_pool, '_used') and self.db_pool._used >= self.db_pool._maxconn - 1:
                    logger.warning("Pool de conexões próximo da capacidade máxima. Verificando saúde...")
                    if not self.check_pool_health():
                        return None
            except Exception as e:
                logger.error(f"Erro ao verificar estado do pool: {e}")
                
        connection = None
        try:
            logger.info(f"Consultando banco de dados para a instância '{instance_name}'")
            
            with self.pool_lock:
                connection = self.db_pool.getconn()
            
            # Verifica se a conexão está ativa e reconecta se necessário
            if connection.closed:
                logger.warning("Conexão fechada. Tentando reconectar...")
                with self.pool_lock:
                    try:
                        self.db_pool.putconn(connection)  # Devolve a conexão fechada
                    except:
                        pass
                self._reset_connection_pool()
                return None
                
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(
                    "SELECT flowise_url FROM flowise_instance WHERE instance_name = %s", 
                    (instance_name,)
                )
                row = cursor.fetchone()
                
                if row and row['flowise_url']:
                    url = row['flowise_url']
                    logger.info(f"URL da instância '{instance_name}' obtida do banco: {url}")
                    
                    # Atualiza o cache de emergência também
                    self._fallback_emergency_cache[instance_name] = url
                    
                    return url
                else:
                    logger.warning(f"Instância '{instance_name}' não encontrada no banco de dados")
                    return None
        except Exception as e:
            logger.error(f"Erro ao consultar banco de dados para instância '{instance_name}': {e}")
            # Se houver erro com essa conexão, descarte-a
            if connection:
                try:
                    if not connection.closed:
                        connection.close()
                except:
                    pass
                connection = None
            # Tenta recriar o pool em caso de erro
            self._reset_connection_pool()
            return None
        finally:
            # Devolve a conexão ao pool, se estiver aberta
            if connection and not connection.closed and self.db_pool:
                with self.pool_lock:
                    try:
                        self.db_pool.putconn(connection)
                    except Exception as e:
                        logger.error(f"Erro ao devolver conexão ao pool: {e}")
                        try:
                            connection.close()
                        except:
                            pass
            
    def _update_cache(self, cache_key: str, url: str) -> None:
        """Atualiza os caches (Redis e local) com a URL da instância."""
        # Atualiza o cache Redis
        if self.redis_client:
            try:
                self.redis_client.set(cache_key, url, ex=CACHE_TTL)
                logger.info(f"Cache Redis atualizado: {cache_key}")
            except Exception as e:
                logger.warning(f"Erro ao atualizar cache Redis: {e}")
        
        # Atualiza o cache local
        expiry_time = time.time() + self.local_cache_ttl
        self.local_cache[cache_key] = (url, expiry_time)
        logger.info(f"Cache local atualizado: {cache_key}")
        
        # Atualiza o cache de emergência
        instance_name = cache_key.split(":")[-1]
        self._fallback_emergency_cache[instance_name] = url

    def save_or_update_instance(self, instance_name: str, flowise_url: str) -> bool:
        """
        Salva ou atualiza uma instância no banco de dados e atualiza o cache.
        
        Args:
            instance_name (str): Nome da instância.
            flowise_url (str): URL da API Flowise.
            
        Returns:
            bool: True se foi bem sucedido, False caso contrário.
        """
        # Verifica a saúde do pool antes de usar
        if not self.check_pool_health():
            logger.error("Pool de conexões não está saudável para salvar/atualizar instância")
            return False
            
        connection = None
        try:
            # Obtém uma conexão do pool
            with self.pool_lock:
                connection = self.db_pool.getconn()
            
            # Verifica se a conexão está ativa
            if connection.closed:
                logger.warning("Conexão fechada. Tentando reconectar...")
                with self.pool_lock:
                    try:
                        self.db_pool.putconn(connection)  # Devolve a conexão fechada
                    except:
                        pass
                self._reset_connection_pool()
                return False
            
            with connection.cursor() as cursor:
                # Verifica se já existe
                cursor.execute(
                    "SELECT id FROM flowise_instance WHERE instance_name = %s", 
                    (instance_name,)
                )
                row = cursor.fetchone()
                
                if row:
                    # Atualiza o registro existente
                    cursor.execute(
                        "UPDATE flowise_instance SET flowise_url = %s WHERE instance_name = %s",
                        (flowise_url, instance_name)
                    )
                else:
                    # Insere um novo registro
                    cursor.execute(
                        "INSERT INTO flowise_instance (instance_name, flowise_url) VALUES (%s, %s)",
                        (instance_name, flowise_url)
                    )
                
                connection.commit()
                logger.info(f"Instância '{instance_name}' salva/atualizada no banco de dados")
                
                # Atualiza os caches
                cache_key = f"flowise:instance:{instance_name}"
                self._update_cache(cache_key, flowise_url)
                
                return True
        except Exception as e:
            logger.error(f"Erro ao salvar/atualizar instância '{instance_name}': {e}")
            # Se houver erro com essa conexão, descarte-a
            if connection:
                try:
                    if not connection.closed:
                        connection.close()
                except:
                    pass
                connection = None
            self._reset_connection_pool()
            return False
        finally:
            # Devolve a conexão ao pool, se estiver aberta
            if connection and not connection.closed and self.db_pool:
                with self.pool_lock:
                    try:
                        self.db_pool.putconn(connection)
                    except Exception as e:
                        logger.error(f"Erro ao devolver conexão ao pool: {e}")
                        try:
                            connection.close()
                        except:
                            pass

    def preload_instances(self) -> None:
        """
        Pré-carrega todas as instâncias do banco de dados para o cache.
        Isso é útil para inicialização do serviço.
        """
        if not self.check_pool_health():
            logger.error("Pool de conexões não está saudável para pré-carregamento")
            return
            
        connection = None
        try:
            with self.pool_lock:
                connection = self.db_pool.getconn()
            
            if connection.closed:
                logger.warning("Conexão fechada. Tentando reconectar...")
                with self.pool_lock:
                    try:
                        self.db_pool.putconn(connection)
                    except:
                        pass
                self._reset_connection_pool()
                return
                
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT instance_name, flowise_url FROM flowise_instance")
                rows = cursor.fetchall()
                
                count = 0
                for row in rows:
                    instance_name = row['instance_name']
                    flowise_url = row['flowise_url']
                    
                    if instance_name and flowise_url:
                        cache_key = f"flowise:instance:{instance_name}"
                        self._update_cache(cache_key, flowise_url)
                        count += 1
                        
                logger.info(f"Pré-carregadas {count} instâncias para o cache")
                
        except Exception as e:
            logger.error(f"Erro ao pré-carregar instâncias: {e}")
            if connection:
                try:
                    if not connection.closed:
                        connection.close()
                except:
                    pass
            self._reset_connection_pool()
        finally:
            if connection and not connection.closed and self.db_pool:
                with self.pool_lock:
                    try:
                        self.db_pool.putconn(connection)
                    except Exception as e:
                        logger.error(f"Erro ao devolver conexão ao pool: {e}")
                        try:
                            connection.close()
                        except:
                            pass

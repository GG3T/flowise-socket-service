import os
import logging
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do logger
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOGGING_CONFIG = {
    "level": getattr(logging, LOG_LEVEL),
    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S",
}

# Configuração do RabbitMQ
RABBITMQ_CONFIG = {
    "host": os.getenv("RABBITMQ_HOST", "rabbitmq.numit.com.br"),
    "port": int(os.getenv("RABBITMQ_PORT", 5672)),
    "username": os.getenv("RABBITMQ_USERNAME", "admin"),
    "password": os.getenv("RABBITMQ_PASSWORD", "8a2cfcdbb1b87da5a47a2e681ca46991"),
    "virtual_host": os.getenv("RABBITMQ_VHOST", "/"),
    "prefetch_count": int(os.getenv("RABBITMQ_PREFETCH_COUNT", 1)),
}

# Configuração do Redis
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "golden-condor-16660.upstash.io"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "password": os.getenv("REDIS_PASSWORD", "AUEUAAIjcDEwZmQwODE0NDEzMjA0OGVkOWNjZTdhYzcyYzY5NzhkZXAxMA"),
    "ssl": os.getenv("REDIS_SSL", "True").lower() in ("true", "1", "t"),
    "socket_timeout": 10,  # 10 segundos de timeout para comandos
    "socket_keepalive": True,  # Manter conexão ativa
    "socket_connect_timeout": 5,  # 5 segundos para timeout de conexão
}

# Configuração do PostgreSQL
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "d16940f9c621e23d87a4062224175db5"),
    "host": os.getenv("DB_HOST", "178.156.142.177"),
    "port": int(os.getenv("DB_PORT", 5432)),
    # Configurações do pool de conexões
    "min_connections": 2,
    "max_connections": 10,
    "connect_timeout": 30,
}

# Configuração do Flowise
FLOWISE_EXCHANGE = os.getenv("FLOWISE_EXCHANGE", "flowise.exchange")
FLOWISE_QUEUE = os.getenv("FLOWISE_QUEUE", "flowise.queue")
FLOWISE_RESPONSE_ROUTING_KEY = os.getenv("FLOWISE_RESPONSE_ROUTING_KEY", "flowise.response")

# Configuração do Thread Pool
THREAD_POOL_SIZE = int(os.getenv("THREAD_POOL_SIZE", 10))

# Cache TTL em segundos (12 horas por padrão)
CACHE_TTL = int(os.getenv("CACHE_TTL", 43200))  # 12 horas

# Configuração de retry
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", 3))
RETRY_BACKOFF_DELAY = int(os.getenv("RETRY_BACKOFF_DELAY", 2000))  # Milissegundos

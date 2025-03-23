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
    "host": os.getenv("RABBITMQ_HOST", "rabbitmq.chatgmia.org"),
    "port": int(os.getenv("RABBITMQ_PORT", 5672)),
    "username": os.getenv("RABBITMQ_USERNAME", "admin"),
    "password": os.getenv("RABBITMQ_PASSWORD", "8a2cfcdbb1b87da5a47a2e681ca46991"),
    "virtual_host": os.getenv("RABBITMQ_VHOST", "/"),
}

# Configuração do Redis
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "golden-condor-16660.upstash.io"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "password": os.getenv("REDIS_PASSWORD", "AUEUAAIjcDEwZmQwODE0NDEzMjA0OGVkOWNjZTdhYzcyYzY5NzhkZXAxMA"),
    "ssl": os.getenv("REDIS_SSL", "True").lower() in ("true", "1", "t"),
}

# Configuração do PostgreSQL
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "71d14724653158e0e40fd03f522ac11c"),
    "host": os.getenv("DB_HOST", "178.156.146.193"),
    "port": int(os.getenv("DB_PORT", 5432)),
}

# Configuração do Flowise
FLOWISE_EXCHANGE = os.getenv("FLOWISE_EXCHANGE", "flowise.exchange")
FLOWISE_QUEUE = os.getenv("FLOWISE_QUEUE", "flowise.queue")
FLOWISE_RESPONSE_ROUTING_KEY = os.getenv("FLOWISE_RESPONSE_ROUTING_KEY", "flowise.response")

# Cache TTL em segundos (12 horas por padrão)
CACHE_TTL = int(os.getenv("CACHE_TTL", 43200))

# Flowise Socket Service

Este serviço atua como intermediário entre o RabbitMQ e a API Flowise, processando mensagens e gerenciando respostas em streaming.

## Configuração

1. Copie o arquivo `.env.example` para `.env` e configure as variáveis de ambiente:
```bash
cp .env.example .env
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Execução

Para executar o serviço localmente:
```bash
python main.py
```

## Docker

Para construir e executar com Docker:
```bash
docker build -t flowise-socket-service .
docker run -d --name flowise-socket-service flowise-socket-service
```

## Estrutura do Projeto

```
flowise-socket-service/
├── src/                     # Código fonte
│   ├── config/              # Configurações da aplicação
│   ├── rabbitmq/            # Módulos relacionados ao RabbitMQ
│   ├── flowise/             # Módulos relacionados ao Flowise
│   ├── services/            # Serviços da aplicação
│   └── utils/               # Funções utilitárias
├── tests/                   # Testes automatizados
├── main.py                  # Ponto de entrada da aplicação
├── Dockerfile               # Configuração do Docker
├── requirements.txt         # Dependências do projeto
├── .env.example             # Exemplo de variáveis de ambiente
└── README.md                # Documentação
```

## Dependências

- pika: Cliente RabbitMQ
- redis: Cliente Redis
- psycopg2-binary: Driver PostgreSQL
- flowise: Cliente API Flowise
- python-dotenv: Gerenciamento de variáveis de ambiente

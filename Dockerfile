# Utiliza uma imagem base oficial do Python 3.12
FROM python:3.12-slim

# Define argumentos que podem ser passados durante o build
ARG APP_HOME=/app

# Define variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=$APP_HOME

# Define o diretório de trabalho dentro do container
WORKDIR $APP_HOME

# Instala as dependências necessárias para compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências para a imagem
COPY requirements.txt .

# Atualiza o pip e instala as dependências
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # Remove pacotes de compilação que não são mais necessários
    apt-get purge -y --auto-remove gcc

# Cria diretório para logs
RUN mkdir -p logs && chmod 777 logs

# Copia o restante do código para dentro do container
COPY . .

# Usuário não-root para segurança adicional
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser && \
    chown -R appuser:appuser $APP_HOME

USER appuser

# Define as informações de saúde para o container
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import os; os.path.exists('logs/flowise-socket-service.log') and exit(0) or exit(1)"

# Comando para executar a aplicação
CMD ["python", "main.py"]

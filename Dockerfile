# Utiliza uma imagem base oficial do Python 3.12
FROM python:3.12-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o arquivo de dependências para a imagem
COPY requirements.txt .

# Atualiza o pip e instala as dependências
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copia o restante do código para dentro do container
COPY . .

# Comando para executar a aplicação
CMD ["python", "main.py"]

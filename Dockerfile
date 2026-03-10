FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Puerto expuesto
EXPOSE 8000

# Placeholder hasta T-003 (src/main.py + uvicorn)
CMD ["python", "-c", "import time; print('Container ready — waiting for T-003'); time.sleep(86400)"]

FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Agregar CA del proxy SSL del host al bundle de certifi (httplib2 usa certifi
# directamente, no el CA store del sistema).
RUN if [ -f proxy-ca.pem ]; then python -c "import certifi; open(certifi.where(),'a').write(open('proxy-ca.pem').read())"; fi

# Puerto expuesto
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

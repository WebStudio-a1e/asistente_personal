# syntax=docker/dockerfile:1
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

# Inyectar CA del proxy SSL local en el bundle de certifi.
# httplib2 usa certifi directamente (no el CA store del sistema).
# El secret es opcional: si no se provee (CI / cloud), este paso es no-op.
# El archivo nunca entra en capas de imagen — solo existe durante este RUN.
RUN --mount=type=secret,id=proxy_ca,required=false \
    sh -c 'test -f /run/secrets/proxy_ca && python -c "import certifi; open(certifi.where(),\"a\").write(open(\"/run/secrets/proxy_ca\").read())" || true'

# Puerto expuesto
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

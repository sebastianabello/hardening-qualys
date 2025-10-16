FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias opcionales útiles para compilar/wheels + pigz para compresión paralela
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  pigz \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Usuario no root
RUN useradd -m app && chown -R app:app /app
USER app

EXPOSE 8080
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8080","--reload","--proxy-headers","--forwarded-allow-ips","*","--timeout-keep-alive","3600","--timeout-graceful-shutdown","60","--loop","uvloop","--http","httptools","--limit-concurrency","1000","--backlog","2048"]

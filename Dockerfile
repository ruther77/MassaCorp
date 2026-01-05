# Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# les dépendances système (psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev curl \
  && rm -rf /var/lib/apt/lists/*

# les dépendances python
COPY pyproject.toml poetry.lock* /app/
RUN pip install --no-cache-dir poetry \
  && poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

# code
COPY . /app

# script de démarrage
COPY ./docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]


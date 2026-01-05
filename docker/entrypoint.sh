#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL manquant}"

echo "[entrypoint] Exécution des migrations de la base de données…"
alembic upgrade head

echo "[entrypoint] Démarrage de l’API…"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000


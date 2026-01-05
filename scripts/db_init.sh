#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL manquant}"

psql "$DATABASE_URL" -f db/sql/00_init.sql


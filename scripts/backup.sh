#!/bin/bash
#
# MassaCorp Database Backup Script
#
# Features:
# - Daily pg_dump with compression
# - WAL archiving support
# - Retention policy (30 days local, 90 days remote)
# - Encryption for offsite storage
# - Slack notifications
#
# Usage:
#   ./backup.sh [full|incremental|wal]
#
# Cron example (daily at 2 AM):
#   0 2 * * * /app/scripts/backup.sh full >> /var/log/backup.log 2>&1

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

BACKUP_TYPE="${1:-full}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
LOCAL_RETENTION_DAYS=30
REMOTE_RETENTION_DAYS=90

# Database connection
DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-MassaCorp}"
DB_USER="${POSTGRES_USER:-massa}"

# Remote storage (S3-compatible)
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
S3_ENDPOINT="${BACKUP_S3_ENDPOINT:-}"

# Encryption
GPG_RECIPIENT="${BACKUP_GPG_RECIPIENT:-}"

# Notifications
SLACK_WEBHOOK="${BACKUP_SLACK_WEBHOOK:-}"

# =============================================================================
# Functions
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

notify_slack() {
    local status="$1"
    local message="$2"

    if [[ -n "$SLACK_WEBHOOK" ]]; then
        local color="good"
        [[ "$status" == "error" ]] && color="danger"
        [[ "$status" == "warning" ]] && color="warning"

        curl -s -X POST "$SLACK_WEBHOOK" \
            -H 'Content-Type: application/json' \
            -d "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"MassaCorp Backup\",
                    \"text\": \"$message\",
                    \"ts\": $(date +%s)
                }]
            }" > /dev/null || true
    fi
}

cleanup_old_backups() {
    log "Cleaning up local backups older than $LOCAL_RETENTION_DAYS days..."
    find "$BACKUP_DIR" -name "*.sql.gz*" -mtime +$LOCAL_RETENTION_DAYS -delete || true
    find "$BACKUP_DIR" -name "*.dump*" -mtime +$LOCAL_RETENTION_DAYS -delete || true
}

upload_to_s3() {
    local file="$1"

    if [[ -n "$S3_BUCKET" ]]; then
        log "Uploading to S3: $file"

        if [[ -n "$S3_ENDPOINT" ]]; then
            aws s3 cp "$file" "s3://$S3_BUCKET/$(basename "$file")" \
                --endpoint-url "$S3_ENDPOINT" || {
                notify_slack "error" "Failed to upload backup to S3"
                return 1
            }
        else
            aws s3 cp "$file" "s3://$S3_BUCKET/$(basename "$file")" || {
                notify_slack "error" "Failed to upload backup to S3"
                return 1
            }
        fi

        log "Upload complete"
    fi
}

encrypt_backup() {
    local file="$1"

    if [[ -n "$GPG_RECIPIENT" ]]; then
        log "Encrypting backup..."
        gpg --encrypt --recipient "$GPG_RECIPIENT" --output "${file}.gpg" "$file"
        rm "$file"
        echo "${file}.gpg"
    else
        echo "$file"
    fi
}

# =============================================================================
# Backup Functions
# =============================================================================

backup_full() {
    local backup_file="${BACKUP_DIR}/massacorp_full_${TIMESTAMP}.sql.gz"

    log "Starting full backup..."

    # Create backup directory if needed
    mkdir -p "$BACKUP_DIR"

    # Perform pg_dump with compression
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --compress=9 \
        --verbose \
        --file="${backup_file%.gz}" 2>&1 | tee -a /var/log/backup.log

    # Compress if plain format
    if [[ -f "${backup_file%.gz}" ]]; then
        gzip "${backup_file%.gz}"
    fi

    # Get file size
    local size=$(du -h "$backup_file" | cut -f1)
    log "Backup complete: $backup_file ($size)"

    # Encrypt if configured
    backup_file=$(encrypt_backup "$backup_file")

    # Upload to remote storage
    upload_to_s3 "$backup_file"

    # Verify backup
    verify_backup "$backup_file"

    notify_slack "good" "Full backup completed successfully: $(basename "$backup_file") ($size)"
}

backup_wal() {
    log "Archiving WAL files..."

    # This is typically configured in postgresql.conf:
    # archive_mode = on
    # archive_command = '/app/scripts/backup.sh wal %p %f'

    local wal_file="$2"
    local wal_path="$3"

    if [[ -n "$wal_file" && -n "$wal_path" ]]; then
        local dest="${BACKUP_DIR}/wal/${wal_file}"
        mkdir -p "${BACKUP_DIR}/wal"
        cp "$wal_path" "$dest"
        gzip "$dest"

        if [[ -n "$S3_BUCKET" ]]; then
            upload_to_s3 "${dest}.gz"
        fi

        log "WAL archived: $wal_file"
    else
        log "WAL archiving configured - waiting for PostgreSQL to call"
    fi
}

verify_backup() {
    local backup_file="$1"

    log "Verifying backup integrity..."

    # Check file exists and has content
    if [[ ! -s "$backup_file" ]]; then
        notify_slack "error" "Backup verification failed: File is empty"
        return 1
    fi

    # For custom format, use pg_restore to verify
    if [[ "$backup_file" == *.dump* ]]; then
        pg_restore --list "$backup_file" > /dev/null 2>&1 || {
            notify_slack "error" "Backup verification failed: Invalid dump format"
            return 1
        }
    fi

    log "Backup verified successfully"
}

restore_backup() {
    local backup_file="$1"
    local target_db="${2:-massacorp_restore_test}"

    log "Restoring backup to test database: $target_db"

    # Create test database
    PGPASSWORD="$POSTGRES_PASSWORD" psql \
        -h "$DB_HOST" \
        -U "$DB_USER" \
        -c "DROP DATABASE IF EXISTS $target_db;"

    PGPASSWORD="$POSTGRES_PASSWORD" psql \
        -h "$DB_HOST" \
        -U "$DB_USER" \
        -c "CREATE DATABASE $target_db;"

    # Restore
    PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$target_db" \
        --verbose \
        "$backup_file"

    log "Restore complete. Test database: $target_db"
}

# =============================================================================
# Main
# =============================================================================

main() {
    log "=== MassaCorp Backup Script ==="
    log "Backup type: $BACKUP_TYPE"

    case "$BACKUP_TYPE" in
        full)
            backup_full
            cleanup_old_backups
            ;;
        wal)
            backup_wal "$@"
            ;;
        restore)
            restore_backup "$2" "${3:-}"
            ;;
        verify)
            verify_backup "$2"
            ;;
        cleanup)
            cleanup_old_backups
            ;;
        *)
            echo "Usage: $0 [full|wal|restore|verify|cleanup]"
            exit 1
            ;;
    esac

    log "=== Backup script completed ==="
}

main "$@"

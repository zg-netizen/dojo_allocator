#!/bin/bash

# Dojo Allocator Backup Script
# Creates automated backups of the database and application data

set -e

# Configuration
BACKUP_DIR="/home/ubuntu/dojo_allocator/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="dojo_allocator_backup_${TIMESTAMP}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "🔄 Creating backup: $BACKUP_NAME"

# Create database backup
echo "📊 Backing up database..."
docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U dojo dojo_allocator > "$BACKUP_DIR/${BACKUP_NAME}.sql"

# Create application data backup
echo "📁 Backing up application data..."
tar -czf "$BACKUP_DIR/${BACKUP_NAME}_data.tar.gz" \
    --exclude="backups" \
    --exclude=".git" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    .

# Create environment backup (without sensitive data)
echo "🔐 Backing up environment configuration..."
cp .env.prod "$BACKUP_DIR/${BACKUP_NAME}_env.prod"

# Compress everything into a single archive
echo "📦 Creating final backup archive..."
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}_complete.tar.gz" \
    "${BACKUP_NAME}.sql" \
    "${BACKUP_NAME}_data.tar.gz" \
    "${BACKUP_NAME}_env.prod"

# Clean up individual files
rm "${BACKUP_NAME}.sql" "${BACKUP_NAME}_data.tar.gz" "${BACKUP_NAME}_env.prod"

# Keep only last 7 days of backups
echo "🧹 Cleaning up old backups..."
find "$BACKUP_DIR" -name "dojo_allocator_backup_*.tar.gz" -mtime +7 -delete

echo "✅ Backup complete: ${BACKUP_NAME}_complete.tar.gz"
echo "📁 Backup location: $BACKUP_DIR/${BACKUP_NAME}_complete.tar.gz"
echo "💾 Backup size: $(du -h "$BACKUP_DIR/${BACKUP_NAME}_complete.tar.gz" | cut -f1)"

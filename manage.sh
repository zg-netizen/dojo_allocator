#!/bin/bash

# Dojo Allocator Management Script
# This script helps manage your Dojo Allocator deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to show help
show_help() {
    echo "🥋 Dojo Allocator Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start       Start all services"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  status      Show status of all services"
    echo "  logs        Show logs (use -f for follow)"
    echo "  update      Update and restart services"
    echo "  backup      Create database backup"
    echo "  restore     Restore database from backup"
    echo "  shell       Open shell in API container"
    echo "  db-shell    Open PostgreSQL shell"
    echo "  health      Check service health"
    echo "  clean       Clean up unused Docker resources"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs -f"
    echo "  $0 backup"
    echo "  $0 shell"
}

# Function to check if services are running
check_services() {
    if [ ! -f .env.prod ]; then
        print_error ".env.prod file not found!"
        exit 1
    fi
}

# Function to start services
start_services() {
    print_info "Starting Dojo Allocator services..."
    docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
    print_status "Services started"
}

# Function to stop services
stop_services() {
    print_info "Stopping Dojo Allocator services..."
    docker-compose -f docker-compose.prod.yml down
    print_status "Services stopped"
}

# Function to restart services
restart_services() {
    print_info "Restarting Dojo Allocator services..."
    docker-compose -f docker-compose.prod.yml restart
    print_status "Services restarted"
}

# Function to show status
show_status() {
    print_info "Service Status:"
    docker-compose -f docker-compose.prod.yml ps
}

# Function to show logs
show_logs() {
    if [ "$2" = "-f" ]; then
        docker-compose -f docker-compose.prod.yml logs -f
    else
        docker-compose -f docker-compose.prod.yml logs --tail=100
    fi
}

# Function to update services
update_services() {
    print_info "Updating Dojo Allocator services..."
    docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
    print_status "Services updated"
}

# Function to create backup
create_backup() {
    print_info "Creating database backup..."
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_file="backup_${timestamp}.sql"
    
    docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U dojo dojo_allocator > "backups/${backup_file}"
    
    if [ $? -eq 0 ]; then
        print_status "Backup created: backups/${backup_file}"
    else
        print_error "Backup failed"
        exit 1
    fi
}

# Function to restore backup
restore_backup() {
    if [ -z "$2" ]; then
        print_error "Please specify backup file: $0 restore backup_file.sql"
        exit 1
    fi
    
    backup_file="$2"
    if [ ! -f "backups/${backup_file}" ]; then
        print_error "Backup file not found: backups/${backup_file}"
        exit 1
    fi
    
    print_warning "This will replace the current database. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_info "Restoring database from backup..."
        docker-compose -f docker-compose.prod.yml exec -T postgres psql -U dojo -d dojo_allocator < "backups/${backup_file}"
        print_status "Database restored"
    else
        print_info "Restore cancelled"
    fi
}

# Function to open shell
open_shell() {
    print_info "Opening shell in API container..."
    docker-compose -f docker-compose.prod.yml exec api /bin/bash
}

# Function to open database shell
open_db_shell() {
    print_info "Opening PostgreSQL shell..."
    docker-compose -f docker-compose.prod.yml exec postgres psql -U dojo -d dojo_allocator
}

# Function to check health
check_health() {
    print_info "Checking service health..."
    
    # Check API
    if curl -f http://localhost/api/health > /dev/null 2>&1; then
        print_status "API is healthy"
    else
        print_error "API health check failed"
    fi
    
    # Check Dashboard
    if curl -f http://localhost/ > /dev/null 2>&1; then
        print_status "Dashboard is healthy"
    else
        print_error "Dashboard health check failed"
    fi
}

# Function to clean up
clean_up() {
    print_info "Cleaning up unused Docker resources..."
    docker system prune -f
    docker volume prune -f
    print_status "Cleanup complete"
}

# Main script logic
case "$1" in
    start)
        check_services
        start_services
        ;;
    stop)
        check_services
        stop_services
        ;;
    restart)
        check_services
        restart_services
        ;;
    status)
        check_services
        show_status
        ;;
    logs)
        check_services
        show_logs "$@"
        ;;
    update)
        check_services
        update_services
        ;;
    backup)
        check_services
        mkdir -p backups
        create_backup
        ;;
    restore)
        check_services
        restore_backup "$@"
        ;;
    shell)
        check_services
        open_shell
        ;;
    db-shell)
        check_services
        open_db_shell
        ;;
    health)
        check_health
        ;;
    clean)
        clean_up
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac

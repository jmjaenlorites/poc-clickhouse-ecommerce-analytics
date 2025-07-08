#!/bin/bash

echo "📋 ClickHouse Analytics PoC - Service Logs"
echo "=========================================="

# Check if a specific service is requested
if [ $# -eq 1 ]; then
    echo "📊 Showing logs for: $1"
    echo "------------------------------------------"
    docker-compose logs -f $1
else
    echo "📊 Available services:"
    echo "  - clickhouse"
    echo "  - postgres"
    echo "  - grafana"
    echo "  - crud-api"
    echo "  - ecommerce-api"
    echo "  - simulator"
    echo ""
    echo "Usage:"
    echo "  $0 [service-name]  # Show logs for specific service"
    echo "  $0                 # Show aggregated logs for all services"
    echo ""
    echo "📋 Showing aggregated logs from all services..."
    echo "------------------------------------------"
    docker-compose logs -f
fi 
#!/bin/bash

echo "🛑 Stopping ClickHouse Analytics PoC..."
echo "========================================"

# Stop all services gracefully
echo "⏹️  Stopping all services..."
docker-compose down

# Optionally remove volumes (uncomment if you want to clean data)
# echo "🗑️  Removing volumes..."
# docker-compose down -v

echo ""
echo "✅ All services stopped successfully!"
echo ""
echo "🧹 To also remove data volumes:"
echo "  docker-compose down -v"
echo ""
echo "🔄 To restart:"
echo "  ./scripts/start.sh"
echo "========================================" 
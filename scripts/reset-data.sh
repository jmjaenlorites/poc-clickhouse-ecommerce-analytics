#!/bin/bash

echo "🗑️  Resetting ClickHouse Analytics PoC Data..."
echo "============================================="

# Confirm with user
read -p "⚠️  This will delete ALL data. Are you sure? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Operation cancelled"
    exit 1
fi

echo "🛑 Stopping all services..."
docker-compose down

echo "🗑️  Removing data volumes..."
docker-compose down -v

echo "🧹 Cleaning up data directories..."
sudo rm -rf data/

echo "📁 Recreating directories..."
mkdir -p logs
mkdir -p data/clickhouse
mkdir -p data/postgres  
mkdir -p data/grafana
chmod -R 777 data/

echo "🚀 Restarting services..."
./scripts/start.sh

echo ""
echo "✅ Data reset complete!"
echo "🔄 Services are starting up with fresh data"
echo "=============================================" 
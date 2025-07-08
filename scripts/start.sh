#!/bin/bash

echo "🚀 Starting ClickHouse Analytics PoC..."
echo "========================================"

# Check if Docker and Docker Compose are available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed or not in PATH"
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p data/clickhouse
mkdir -p data/postgres
mkdir -p data/grafana

# Set permissions
chmod -R 777 data/

# Start the infrastructure services first
echo "🐳 Starting infrastructure services..."
docker-compose up -d clickhouse postgres grafana

# Wait for infrastructure to be ready
echo "⏳ Waiting for infrastructure services to be ready..."
sleep 10

# Check if services are healthy
echo "🔍 Checking service health..."

# Check ClickHouse
echo "  - Checking ClickHouse..."
for i in {1..30}; do
    if curl -s http://localhost:8123/ping > /dev/null; then
        echo "    ✅ ClickHouse is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "    ❌ ClickHouse failed to start"
        exit 1
    fi
    sleep 2
done

# Check PostgreSQL
echo "  - Checking PostgreSQL..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo "    ✅ PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "    ❌ PostgreSQL failed to start"
        exit 1
    fi
    sleep 2
done

# Check Grafana
echo "  - Checking Grafana..."
for i in {1..30}; do
    if curl -s http://localhost:3000/api/health > /dev/null; then
        echo "    ✅ Grafana is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "    ❌ Grafana failed to start"
        exit 1
    fi
    sleep 2
done

# Start the API services
echo "🔧 Starting API services..."
docker-compose up -d crud-api ecommerce-api

# Wait for APIs to be ready
echo "⏳ Waiting for API services..."
sleep 20

# Check API health
echo "🔍 Checking API health..."

# Check CRUD API
echo "  - Checking CRUD API..."
for i in {1..30}; do
    if curl -s http://localhost:8001/health > /dev/null; then
        echo "    ✅ CRUD API is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "    ❌ CRUD API failed to start"
        exit 1
    fi
    sleep 2
done

# Check E-commerce API
echo "  - Checking E-commerce API..."
for i in {1..30}; do
    if curl -s http://localhost:8002/health > /dev/null; then
        echo "    ✅ E-commerce API is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "    ❌ E-commerce API failed to start"
        exit 1
    fi
    sleep 2
done

echo ""
echo "🎉 All services are running!"
echo "========================================"
echo "📊 Access URLs:"
echo "  - Grafana Dashboard: http://localhost:3000 (admin/admin)"
echo "  - ClickHouse Interface: http://localhost:8123"
echo "  - CRUD API: http://localhost:8001"
echo "  - E-commerce API: http://localhost:8002"
echo ""
echo "🔧 API Documentation:"
echo "  - CRUD API Docs: http://localhost:8001/docs"
echo "  - E-commerce API Docs: http://localhost:8002/docs"
echo ""
echo "🚀 To start the load simulator:"
echo "  docker-compose up simulator"
echo ""
echo "📋 To view logs:"
echo "  docker-compose logs -f [service-name]"
echo ""
echo "🛑 To stop everything:"
echo "  ./scripts/stop.sh"
echo "========================================" 
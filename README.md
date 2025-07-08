# ClickHouse Analytics PoC

🚀 **Proof of Concept para análisis en tiempo real con ClickHouse**

Un ecosistema completo de microservicios que demuestra las capacidades de ClickHouse para análisis en tiempo real, incluyendo APIs, simulador de carga, y dashboards interactivos.

## 🏗️ Arquitectura

```
Cliente Simulador → APIs (CRUD + E-commerce) → [PostgreSQL + ClickHouse] → Grafana
                                                       ↑
                                               Datos transaccionales + Analytics
```

### Componentes

- **ClickHouse**: Base de datos analítica para métricas en tiempo real
- **PostgreSQL**: Base de datos transaccional para datos de negocio
- **FastAPI**: Dos microservicios (CRUD + E-commerce) con middleware automático de métricas
- **Grafana**: Dashboards interactivos para visualización
- **Python Simulator**: Generador de tráfico configurable y realista

## 🚀 Quick Start

### Prerequisitos

- Docker & Docker Compose
- 8GB RAM mínimo
- Puertos disponibles: 3000, 5432, 8001, 8002, 8123, 9000

### Instalación y Ejecución

```bash
# 1. Clonar el repositorio
git clone <repository-url>
cd testing-clickhouse-mv

# 2. Iniciar todo el stack
chmod +x scripts/*.sh
./scripts/start.sh

# 3. Acceder a los servicios
# Grafana: http://localhost:3000 (admin/admin)
# APIs: http://localhost:8001 y http://localhost:8002
```

### Iniciar Simulación de Carga

```bash
# Ejecutar simulador con configuración por defecto
docker-compose up simulator

# Ver logs del simulador
docker-compose logs -f simulator
```

## 📊 URLs de Acceso

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Grafana Dashboards** | http://localhost:3000 | admin/admin |
| **CRUD API** | http://localhost:8001/docs | - |
| **E-commerce API** | http://localhost:8002/docs | - |
| **ClickHouse HTTP** | http://localhost:8123 | - |

## 📈 Dashboards Disponibles

### 1. Overview Dashboard
- Requests por segundo por servicio
- Latencia promedio y P95
- Distribución de códigos de estado
- Top 10 endpoints más utilizados
- Usuarios activos por región

### 2. Performance Dashboard
- Tiempo de respuesta por endpoint (tabla con colores)
- Throughput por servicio
- Tasa de errores y errores por minuto
- Uso de CPU y memoria por servicio
- Análisis de errores por endpoint

### 3. Business Analytics Dashboard
- Revenue en tiempo real
- Usuarios activos
- Productos más vistos
- Métricas de conversión

## ⚙️ Configuración del Simulador

Edita `simulator/config.yaml` para personalizar:

```yaml
simulation:
  workers: 5                    # Número de workers concurrentes
  requests_per_second: 50       # RPS objetivo total
  duration_minutes: 60          # Duración (0 = infinito)

user_types:
  - name: "normal_user"
    weight: 70                  # 70% de usuarios
    requests_per_session: [3, 8]
    think_time_seconds: [1, 5]

endpoints:
  crud_service:
    base_url: "http://crud-api:8000"
    endpoints:
      - path: "/users"
        methods: ["GET"]
        weight: 25
        user_types: ["normal_user", "power_user"]
```

## 🔧 Scripts de Utilidad

```bash
# Iniciar todo el stack
./scripts/start.sh

# Ver logs de servicios
./scripts/logs.sh [service-name]

# Parar todos los servicios
./scripts/stop.sh

# Resetear todos los datos
./scripts/reset-data.sh
```

## 📊 Métricas Capturadas

### Métricas de Request
- Timestamp, servicio, endpoint, método
- Código de estado y tiempo de respuesta
- Tamaños de request/response
- Usuario, sesión, IP, región geográfica
- User agent y contexto de request

### Métricas de Negocio
- ID de producto y categoría
- Monto de transacción
- Número de items en carrito
- Datos específicos de e-commerce

### Métricas de Sistema
- Uso de CPU por servicio
- Uso de memoria por servicio
- Conexiones activas

## 🗃️ Esquema de Datos

### Tabla Principal: analytics.request_metrics

```sql
CREATE TABLE analytics.request_metrics (
    timestamp DateTime64(3),
    service_name String,
    endpoint String,
    method String,
    status_code UInt16,
    response_time_ms UInt32,
    -- ... más campos
    transaction_amount Nullable(Float64),
    cart_items_count Nullable(UInt16)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (service_name, timestamp);
```

## 📋 Endpoints de las APIs

### CRUD API (Puerto 8001)
- `GET/POST /users` - Gestión de usuarios
- `GET/POST/PUT/DELETE /products` - Gestión de productos
- `GET /products/{id}` - Detalle de producto
- `POST /demo/generate-users` - Generar datos de prueba

### E-commerce API (Puerto 8002)
- `GET/POST /cart` - Gestión de carrito
- `PUT /cart/{item_id}` - Actualizar item del carrito
- `POST /checkout` - Proceso de checkout
- `GET/POST /orders` - Gestión de órdenes
- `GET /orders/{id}` - Detalle de orden

## 🔍 Queries de Ejemplo

```sql
-- Requests por minuto en la última hora
SELECT 
    toStartOfMinute(timestamp) as minute,
    count() as requests
FROM analytics.request_metrics 
WHERE timestamp >= now() - INTERVAL 1 HOUR
GROUP BY minute
ORDER BY minute;

-- Top endpoints por latencia
SELECT 
    concat(method, ' ', endpoint) as endpoint,
    avg(response_time_ms) as avg_latency,
    quantile(0.95)(response_time_ms) as p95_latency
FROM analytics.request_metrics 
WHERE timestamp >= now() - INTERVAL 1 HOUR
GROUP BY endpoint
ORDER BY avg_latency DESC;

-- Revenue por hora
SELECT 
    toStartOfHour(timestamp) as hour,
    sum(transaction_amount) as revenue
FROM analytics.request_metrics 
WHERE timestamp >= now() - INTERVAL 24 HOUR
  AND transaction_amount IS NOT NULL
GROUP BY hour
ORDER BY hour;
```

## 🔧 Troubleshooting

### Servicios no inician
```bash
# Verificar Docker
docker --version
docker-compose --version

# Verificar puertos
netstat -tulpn | grep -E ':(3000|5432|8001|8002|8123|9000)'

# Reiniciar con datos limpios
./scripts/reset-data.sh
```

### Dashboards no muestran datos
```bash
# Verificar conectividad ClickHouse
curl http://localhost:8123/ping

# Verificar datos en ClickHouse
curl "http://localhost:8123/?query=SELECT count() FROM analytics.request_metrics"

# Reiniciar simulador
docker-compose restart simulator
```

### Performance Issues
```bash
# Verificar recursos del sistema
docker stats

# Verificar logs de ClickHouse
docker-compose logs clickhouse | tail -100

# Reducir RPS del simulador
# Editar simulator/config.yaml: requests_per_second: 10
```

## 📈 Escalabilidad y Optimizaciones

### Para Mayor Volumen
1. **ClickHouse Clustering**: Configurar réplicas y sharding
2. **Buffer Tables**: Usar tablas buffer para writes masivos
3. **Materialized Views**: Pre-agregar métricas comunes
4. **TTL Policies**: Configurar retención automática de datos

### Para Producción
1. **Autenticación**: Implementar JWT en APIs
2. **Rate Limiting**: Limitar requests por usuario/IP
3. **Monitoring**: Añadir Prometheus + AlertManager
4. **Load Balancing**: Usar NGINX para balancear APIs

## 🛠️ Desarrollo

### Estructura del Proyecto
```
testing-clickhouse-mv/
├── docker-compose.yml          # Orchestración principal
├── .env                        # Variables de entorno
├── config/                     # Configuraciones
│   ├── clickhouse/            # Config ClickHouse
│   └── grafana/               # Config Grafana
├── services/                   # Microservicios
│   ├── crud-api/              # API CRUD
│   └── ecommerce-api/         # API E-commerce
├── simulator/                  # Simulador de carga
├── dashboards/                 # Dashboards Grafana
├── scripts/                    # Scripts de utilidad
└── init/                      # Scripts de inicialización
```

### Añadir Nuevas Métricas
1. Modificar `shared/metrics_middleware.py`
2. Actualizar schema en `init/clickhouse/01-create-tables.sql`
3. Crear queries en Grafana dashboards

### Añadir Nuevos Endpoints
1. Crear endpoints en APIs correspondientes
2. Añadir a `simulator/config.yaml`
3. Actualizar generadores de datos si es necesario

## 📚 Referencias

- [ClickHouse Documentation](https://clickhouse.com/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Docker Compose Reference](https://docs.docker.com/compose/)

## 🤝 Contribuir

1. Fork del repositorio
2. Crear branch de feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Añadir nueva funcionalidad'`)
4. Push al branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

MIT License - ver archivo `LICENSE` para detalles.

---

**💡 ¿Preguntas?** Revisa la sección de troubleshooting o abre un issue en el repositorio. 
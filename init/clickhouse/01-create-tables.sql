-- ClickHouse Analytics Database Tables
-- This script runs automatically on first container initialization

-- Create request_metrics table
CREATE TABLE IF NOT EXISTS analytics.request_metrics (
    timestamp DateTime64(3) DEFAULT now64(3),
    service_name String,
    endpoint String,
    method String,
    status_code UInt16,
    response_time_ms UInt32,
    request_size_bytes UInt32,
    response_size_bytes UInt32,
    user_id String,
    session_id String,
    user_agent String,
    ip_address String,
    geographic_region String,
    product_id Nullable(String),
    category Nullable(String),
    transaction_amount Nullable(Float64),
    cart_items_count Nullable(UInt16),
    error_message Nullable(String),
    request_id String DEFAULT generateUUIDv4()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (service_name, toStartOfHour(timestamp), timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

-- Create system_metrics table
CREATE TABLE IF NOT EXISTS analytics.system_metrics (
    timestamp DateTime64(3) DEFAULT now64(3),
    service_name String,
    metric_name String,
    metric_value Float64,
    unit String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (service_name, metric_name, timestamp)
TTL toDateTime(timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192; 
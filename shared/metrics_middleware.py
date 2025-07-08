import asyncio
import time
import uuid
import json
import random
import psutil
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import os
from contextlib import asynccontextmanager

class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str, clickhouse_url: str):
        super().__init__(app)
        self.service_name = service_name
        self.clickhouse_url = clickhouse_url
        self.client = httpx.AsyncClient(timeout=10.0)
        self.system_metrics_task = None
        
    async def dispatch(self, request: Request, call_next):
        # Start timing
        start_time = time.time()
        start_datetime = datetime.utcnow()
        
        # Generate request context
        request_id = str(uuid.uuid4())
        session_id = self._get_session_id(request)
        user_id = self._get_user_id(request)
        
        # Get request size
        request_size = len(await self._get_request_body(request))
        
        # Process request
        response = await call_next(request)
        
        # Calculate metrics
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        # Get response size
        response_size = self._get_response_size(response)
        
        # Prepare metrics data
        metrics_data = {
            "timestamp": start_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            "service_name": self.service_name,
            "endpoint": str(request.url.path),
            "method": request.method,
            "status_code": response.status_code,
            "response_time_ms": response_time_ms,
            "request_size_bytes": request_size,
            "response_size_bytes": response_size,
            "user_id": user_id,
            "session_id": session_id,
            "user_agent": self._get_user_agent(request),
            "ip_address": self._get_client_ip(request),
            "geographic_region": self._get_geographic_region(request),
            "request_id": request_id,
            "error_message": None if response.status_code < 400 else f"HTTP {response.status_code}",
            # Business metrics (will be populated by individual APIs)
            "product_id": None,
            "category": None,
            "transaction_amount": None,
            "cart_items_count": None
        }
        
        # Extract business metrics from response if available
        if hasattr(response, "_business_metrics"):
            metrics_data.update(response._business_metrics)
        
        # Send metrics asynchronously
        asyncio.create_task(self._send_metrics(metrics_data))
        
        return response
    
    async def _get_request_body(self, request: Request) -> bytes:
        """Get request body size"""
        try:
            body = await request.body()
            # Reset the request body for downstream processing
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive
            return body
        except:
            return b""
    
    def _get_response_size(self, response: Response) -> int:
        """Estimate response size"""
        try:
            if hasattr(response, 'body'):
                return len(response.body)
            return 0
        except:
            return 0
    
    def _get_session_id(self, request: Request) -> str:
        """Extract or generate session ID"""
        # Try to get from cookies, headers, or generate new
        session_id = request.cookies.get('session_id')
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        if not session_id:
            session_id = str(uuid.uuid4())
        return session_id
    
    def _get_user_id(self, request: Request) -> str:
        """Extract user ID from request"""
        # In a real app, this would come from JWT token or session
        # For demo, we'll simulate based on session or generate
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            # Generate deterministic user ID based on session for consistency
            session_id = self._get_session_id(request)
            user_id = f"user_{abs(hash(session_id)) % 1000:04d}"
        return user_id
    
    def _get_user_agent(self, request: Request) -> str:
        """Get user agent"""
        return request.headers.get('User-Agent', 'Unknown')
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers first
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_geographic_region(self, request: Request) -> str:
        """Simulate geographic region based on IP or headers"""
        # In a real app, you'd use a GeoIP service
        # For demo, we'll simulate based on request patterns
        ip = self._get_client_ip(request)
        
        # Simple simulation based on IP hash
        regions = ["US-East", "US-West", "EU-West", "EU-Central", "APAC", "LATAM"]
        region_index = abs(hash(ip)) % len(regions)
        return regions[region_index]
    
    async def _send_metrics(self, metrics_data: Dict[str, Any]):
        """Send metrics to ClickHouse asynchronously"""
        try:
            # Escape quotes for ClickHouse
            user_agent_escaped = metrics_data['user_agent'].replace("'", "''")
            error_message_escaped = metrics_data['error_message'].replace("'", "''") if metrics_data['error_message'] else 'NULL'
            
            # Prepare ClickHouse insert query
            values = (
                f"('{metrics_data['timestamp']}', "
                f"'{metrics_data['service_name']}', "
                f"'{metrics_data['endpoint']}', "
                f"'{metrics_data['method']}', "
                f"{metrics_data['status_code']}, "
                f"{metrics_data['response_time_ms']}, "
                f"{metrics_data['request_size_bytes']}, "
                f"{metrics_data['response_size_bytes']}, "
                f"'{metrics_data['user_id']}', "
                f"'{metrics_data['session_id']}', "
                f"'{user_agent_escaped}', "
                f"'{metrics_data['ip_address']}', "
                f"'{metrics_data['geographic_region']}', "
                f"'{metrics_data['product_id'] if metrics_data['product_id'] else 'NULL'}', "
                f"'{metrics_data['category'] if metrics_data['category'] else 'NULL'}', "
                f"{metrics_data['transaction_amount'] if metrics_data['transaction_amount'] else 'NULL'}, "
                f"{metrics_data['cart_items_count'] if metrics_data['cart_items_count'] else 'NULL'}, "
                f"'{error_message_escaped}', "
                f"'{metrics_data['request_id']}')"
            )
            
            query = f"""
            INSERT INTO analytics.request_metrics 
            (timestamp, service_name, endpoint, method, status_code, response_time_ms, 
             request_size_bytes, response_size_bytes, user_id, session_id, user_agent, 
             ip_address, geographic_region, product_id, category, transaction_amount, 
             cart_items_count, error_message, request_id) 
            VALUES {values}
            """
            
            response = await self.client.post(
                f"{self.clickhouse_url}/",
                content=query,
                headers={"Content-Type": "text/plain"}
            )
            
            if response.status_code != 200:
                print(f"Failed to send metrics: {response.text}")
                
        except Exception as e:
            print(f"Error sending metrics to ClickHouse: {e}")
    
    async def start_system_metrics_collection(self):
        """Start collecting system metrics"""
        if self.system_metrics_task is None:
            self.system_metrics_task = asyncio.create_task(self._collect_system_metrics())
    
    async def stop_system_metrics_collection(self):
        """Stop collecting system metrics"""
        if self.system_metrics_task:
            self.system_metrics_task.cancel()
            try:
                await self.system_metrics_task
            except asyncio.CancelledError:
                pass
    
    async def _collect_system_metrics(self):
        """Collect system metrics periodically"""
        while True:
            try:
                await asyncio.sleep(30)  # Collect every 30 seconds
                
                # Get system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                memory_mb = memory.used / 1024 / 1024
                
                # Send CPU metric
                await self._send_system_metric("cpu_usage_percent", cpu_percent, "percent")
                
                # Send memory metric
                await self._send_system_metric("memory_usage_mb", memory_mb, "megabytes")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error collecting system metrics: {e}")
    
    async def _send_system_metric(self, metric_name: str, value: float, unit: str):
        """Send system metric to ClickHouse"""
        try:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            query = f"""
            INSERT INTO analytics.system_metrics 
            (timestamp, service_name, metric_name, metric_value, unit) 
            VALUES ('{timestamp}', '{self.service_name}', '{metric_name}', {value}, '{unit}')
            """
            
            response = await self.client.post(
                f"{self.clickhouse_url}/",
                content=query,
                headers={"Content-Type": "text/plain"}
            )
            
        except Exception as e:
            print(f"Error sending system metric: {e}")


# Helper function to add business metrics to response
def add_business_metrics(response: Response, **metrics):
    """Add business metrics to response for tracking"""
    if not hasattr(response, '_business_metrics'):
        response._business_metrics = {}
    response._business_metrics.update(metrics)
    return response


# Context manager for application lifecycle
@asynccontextmanager
async def lifespan_with_metrics(app, middleware: MetricsMiddleware):
    """Lifespan context manager that handles metrics collection"""
    await middleware.start_system_metrics_collection()
    try:
        yield
    finally:
        await middleware.stop_system_metrics_collection()
        await middleware.client.aclose() 
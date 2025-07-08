import asyncio
import time
import random
import logging
from typing import Dict, List, Any, Optional
from asyncio_throttle import Throttler
import httpx
from .data_generators import DataGenerators, UserSession

logger = logging.getLogger(__name__)


class SimulationStats:
    """Track simulation statistics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.response_times = []
        self.status_codes = {}
        self.endpoints_hit = {}
        self.errors = []
        
    def record_request(self, endpoint: str, method: str, status_code: int, 
                      response_time: float, error: str = None):
        """Record a request result"""
        self.total_requests += 1
        
        if status_code < 400:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            
        self.response_times.append(response_time)
        
        # Track status codes
        if status_code not in self.status_codes:
            self.status_codes[status_code] = 0
        self.status_codes[status_code] += 1
        
        # Track endpoints
        endpoint_key = f"{method} {endpoint}"
        if endpoint_key not in self.endpoints_hit:
            self.endpoints_hit[endpoint_key] = 0
        self.endpoints_hit[endpoint_key] += 1
        
        if error:
            self.errors.append(error)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        elapsed = time.time() - self.start_time
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        rps = self.total_requests / elapsed if elapsed > 0 else 0
        
        return {
            'elapsed_seconds': elapsed,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'requests_per_second': rps,
            'avg_response_time_ms': avg_response_time * 1000,
            'status_codes': self.status_codes,
            'top_endpoints': dict(sorted(self.endpoints_hit.items(), 
                                       key=lambda x: x[1], reverse=True)[:10]),
            'error_count': len(self.errors)
        }


class LoadSimulator:
    """Main load simulation engine"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.data_gen = DataGenerators()
        self.stats = SimulationStats()
        self.running = False
        self.workers = []
        
        # Setup throttler for rate limiting
        rps = config['simulation']['requests_per_second']
        self.throttler = Throttler(rate_limit=rps, period=1.0)
        
        # Build endpoint configurations
        self.endpoints = self._build_endpoints()
        
        # Setup logging
        log_level = getattr(logging, config.get('reporting', {}).get('log_level', 'INFO'))
        logging.basicConfig(level=log_level, 
                          format='%(asctime)s - %(levelname)s - %(message)s')
    
    def _build_endpoints(self) -> List[Dict[str, Any]]:
        """Build weighted list of endpoints from config"""
        endpoints = []
        
        for service_name, service_config in self.config['endpoints'].items():
            base_url = service_config['base_url']
            
            for endpoint_config in service_config['endpoints']:
                for method in endpoint_config['methods']:
                    endpoint = {
                        'service': service_name,
                        'base_url': base_url,
                        'path': endpoint_config['path'],
                        'method': method,
                        'weight': endpoint_config['weight'],
                        'user_types': endpoint_config.get('user_types', []),
                        'payload_generator': endpoint_config.get('payload_generator'),
                        'path_generator': endpoint_config.get('path_generator')
                    }
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _select_endpoint(self, user_type: str) -> Dict[str, Any]:
        """Select endpoint based on weights and user type"""
        # Filter endpoints available for this user type
        available_endpoints = [
            ep for ep in self.endpoints 
            if user_type in ep['user_types']
        ]
        
        if not available_endpoints:
            return random.choice(self.endpoints)
        
        # Weight-based selection
        weights = [ep['weight'] for ep in available_endpoints]
        return random.choices(available_endpoints, weights=weights)[0]
    
    def _select_user_type(self) -> Dict[str, Any]:
        """Select user type based on configured weights"""
        user_types = self.config['user_types']
        weights = [ut['weight'] for ut in user_types]
        return random.choices(user_types, weights=weights)[0]
    
    def _select_region(self) -> Dict[str, Any]:
        """Select geographic region based on weights"""
        regions = self.config['geographic_distribution']
        weights = [r['weight'] for r in regions]
        return random.choices(regions, weights=weights)[0]
    
    async def _make_request(self, session: UserSession, endpoint: Dict[str, Any]) -> None:
        """Make a single HTTP request"""
        async with self.throttler:
            start_time = time.time()
            
            try:
                # Build URL
                path = endpoint['path']
                if endpoint.get('path_generator'):
                    param = self.data_gen.get_path_param(endpoint['path_generator'])
                    path = path.replace('{id}', param).replace('{item_id}', param)
                
                url = f"{endpoint['base_url']}{path}"
                
                # Get headers
                headers = session.get_headers()
                
                # Get payload if needed
                payload = None
                if endpoint['method'] in ['POST', 'PUT'] and endpoint.get('payload_generator'):
                    payload = self.data_gen.get_payload(endpoint['payload_generator'])
                
                # Make request
                async with httpx.AsyncClient(timeout=30.0) as client:
                    if endpoint['method'] == 'GET':
                        response = await client.get(url, headers=headers)
                    elif endpoint['method'] == 'POST':
                        response = await client.post(url, json=payload, headers=headers)
                    elif endpoint['method'] == 'PUT':
                        if payload:
                            response = await client.put(url, json=payload, headers=headers)
                        else:
                            response = await client.put(url, headers=headers)
                    elif endpoint['method'] == 'DELETE':
                        response = await client.delete(url, headers=headers)
                    
                    response_time = time.time() - start_time
                    
                    # Update session state
                    session.update_state(path, response.json() if response.status_code < 400 else None)
                    
                    # Record stats
                    self.stats.record_request(
                        endpoint=path,
                        method=endpoint['method'],
                        status_code=response.status_code,
                        response_time=response_time
                    )
                    
                    if self.config.get('reporting', {}).get('detailed_logging', False):
                        logger.info(f"{endpoint['method']} {url} -> {response.status_code} ({response_time*1000:.1f}ms)")
                    
            except Exception as e:
                response_time = time.time() - start_time
                logger.warning(f"Request failed: {e}")
                
                self.stats.record_request(
                    endpoint=endpoint['path'],
                    method=endpoint['method'],
                    status_code=500,
                    response_time=response_time,
                    error=str(e)
                )
    
    async def _user_session_worker(self, worker_id: int) -> None:
        """Simulate a user session"""
        logger.info(f"Worker {worker_id} started")
        
        try:
            while self.running:
                # Create new user session
                user_type = self._select_user_type()
                region = self._select_region()
                session_id = self.data_gen.generate_session_id()
                
                session = UserSession(session_id, user_type, region, self.data_gen)
                session.session_start = time.time()
                
                logger.debug(f"Worker {worker_id}: New session {session_id} ({user_type['name']}) from {region['region']}")
                
                # Simulate user session
                while self.running and session.should_continue_session():
                    # Select endpoint
                    endpoint = self._select_endpoint(user_type['name'])
                    
                    # Make request
                    await self._make_request(session, endpoint)
                    
                    # Think time between requests
                    think_time = session.get_think_time()
                    await asyncio.sleep(think_time)
                
                logger.debug(f"Worker {worker_id}: Session {session_id} completed ({session.requests_made} requests)")
                
                # Small break between sessions for this worker
                await asyncio.sleep(random.uniform(1, 3))
                
        except asyncio.CancelledError:
            logger.info(f"Worker {worker_id} cancelled")
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}")
    
    async def _stats_reporter(self) -> None:
        """Periodically report statistics"""
        interval = self.config.get('reporting', {}).get('stats_interval_seconds', 10)
        
        while self.running:
            await asyncio.sleep(interval)
            
            stats = self.stats.get_stats()
            logger.info(f"Stats: {stats['total_requests']} requests, "
                       f"{stats['requests_per_second']:.1f} RPS, "
                       f"{stats['avg_response_time_ms']:.1f}ms avg, "
                       f"{stats['successful_requests']}/{stats['failed_requests']} success/fail")
    
    async def run(self) -> None:
        """Run the simulation"""
        logger.info("Starting load simulation...")
        
        self.running = True
        
        # Start workers
        num_workers = self.config['simulation']['workers']
        self.workers = [
            asyncio.create_task(self._user_session_worker(i))
            for i in range(num_workers)
        ]
        
        # Start stats reporter
        stats_task = asyncio.create_task(self._stats_reporter())
        
        # Ramp up gradually
        ramp_up_seconds = self.config['simulation'].get('ramp_up_seconds', 0)
        if ramp_up_seconds > 0:
            logger.info(f"Ramping up over {ramp_up_seconds} seconds...")
            for i in range(ramp_up_seconds):
                await asyncio.sleep(1)
                # Could implement gradual RPS increase here
        
        # Run for specified duration or indefinitely
        duration_minutes = self.config['simulation'].get('duration_minutes', 0)
        if duration_minutes > 0:
            logger.info(f"Running simulation for {duration_minutes} minutes...")
            await asyncio.sleep(duration_minutes * 60)
            await self.stop()
        else:
            logger.info("Running simulation indefinitely (Ctrl+C to stop)...")
            try:
                # Wait indefinitely
                await asyncio.Future()
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                await self.stop()
        
        # Cleanup
        stats_task.cancel()
        await asyncio.gather(*[stats_task], return_exceptions=True)
        
        # Print final stats
        final_stats = self.stats.get_stats()
        logger.info("=== Final Statistics ===")
        logger.info(f"Total requests: {final_stats['total_requests']}")
        logger.info(f"Success rate: {final_stats['successful_requests']}/{final_stats['total_requests']} ({100*final_stats['successful_requests']/max(1,final_stats['total_requests']):.1f}%)")
        logger.info(f"Average RPS: {final_stats['requests_per_second']:.1f}")
        logger.info(f"Average response time: {final_stats['avg_response_time_ms']:.1f}ms")
        logger.info(f"Status codes: {final_stats['status_codes']}")
        logger.info(f"Top endpoints: {final_stats['top_endpoints']}")
    
    async def stop(self) -> None:
        """Stop the simulation"""
        logger.info("Stopping simulation...")
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("Simulation stopped") 
#!/usr/bin/env python3

import asyncio
import yaml
import os
import sys
import signal
import logging
from typing import Dict, Any

# Add app directory to path
sys.path.append('/app')
from app.simulator import LoadSimulator

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"Configuration file {config_path} not found!")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing configuration file: {e}")
        sys.exit(1)

def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration structure"""
    required_sections = ['simulation', 'user_types', 'endpoints', 'geographic_distribution']
    
    for section in required_sections:
        if section not in config:
            print(f"Missing required configuration section: {section}")
            return False
    
    # Validate simulation section
    sim_config = config['simulation']
    required_sim_fields = ['workers', 'requests_per_second']
    for field in required_sim_fields:
        if field not in sim_config:
            print(f"Missing required simulation field: {field}")
            return False
    
    # Validate workers and RPS are positive
    if sim_config['workers'] <= 0:
        print("Number of workers must be positive")
        return False
    
    if sim_config['requests_per_second'] <= 0:
        print("Requests per second must be positive")
        return False
    
    # Validate user types have weights
    for user_type in config['user_types']:
        if 'weight' not in user_type or user_type['weight'] <= 0:
            print(f"User type {user_type.get('name', 'unnamed')} must have positive weight")
            return False
    
    # Validate endpoints structure
    for service_name, service_config in config['endpoints'].items():
        if 'base_url' not in service_config:
            print(f"Service {service_name} missing base_url")
            return False
        
        if 'endpoints' not in service_config:
            print(f"Service {service_name} missing endpoints")
            return False
    
    print("Configuration validation passed")
    return True

def setup_logging(config: Dict[str, Any]):
    """Setup logging configuration"""
    log_level = config.get('reporting', {}).get('log_level', 'INFO')
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from httpx
    logging.getLogger('httpx').setLevel(logging.WARNING)

async def wait_for_services(config: Dict[str, Any]):
    """Wait for API services to be available"""
    import httpx
    
    print("Waiting for API services to be ready...")
    
    services = []
    for service_name, service_config in config['endpoints'].items():
        base_url = service_config['base_url']
        health_url = f"{base_url}/health"
        services.append((service_name, health_url))
    
    max_retries = 30
    retry_delay = 2
    
    for service_name, health_url in services:
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(health_url)
                    if response.status_code == 200:
                        print(f"✓ {service_name} is ready")
                        break
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"✗ {service_name} failed to become ready after {max_retries} attempts")
                    print(f"  Last error: {e}")
                    return False
                else:
                    print(f"  Waiting for {service_name}... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
    
    print("All services are ready!")
    return True

def print_banner(config: Dict[str, Any]):
    """Print startup banner with configuration summary"""
    print("=" * 60)
    print("🚀 ClickHouse Analytics PoC - Load Simulator")
    print("=" * 60)
    print(f"Workers: {config['simulation']['workers']}")
    print(f"Target RPS: {config['simulation']['requests_per_second']}")
    
    duration = config['simulation'].get('duration_minutes', 0)
    if duration > 0:
        print(f"Duration: {duration} minutes")
    else:
        print("Duration: Infinite (Ctrl+C to stop)")
    
    print(f"User types: {', '.join([ut['name'] for ut in config['user_types']])}")
    print(f"Services: {', '.join(config['endpoints'].keys())}")
    print(f"Regions: {', '.join([r['region'] for r in config['geographic_distribution']])}")
    print("=" * 60)

async def main():
    """Main entry point"""
    print("Starting ClickHouse Analytics PoC Simulator...")
    
    # Load and validate configuration
    config_path = os.getenv('CONFIG_PATH', '/app/config.yaml')
    config = load_config(config_path)
    
    if not validate_config(config):
        sys.exit(1)
    
    # Setup logging
    setup_logging(config)
    
    # Print banner
    print_banner(config)
    
    # Wait for services to be ready
    if not await wait_for_services(config):
        print("Failed to connect to required services. Exiting.")
        sys.exit(1)
    
    # Create and run simulator
    simulator = LoadSimulator(config)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        asyncio.create_task(simulator.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await simulator.run()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Simulator error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Simulator finished")

if __name__ == "__main__":
    if sys.platform == "win32":
        # Fix for Windows event loop policy
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main()) 
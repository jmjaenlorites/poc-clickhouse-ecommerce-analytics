import random
import uuid
from faker import Faker
from typing import Dict, Any, List
import ipaddress

class DataGenerators:
    def __init__(self):
        self.fake = Faker()
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Android 11; Mobile; rv:68.0) Gecko/68.0 Firefox/88.0"
        ]
        
        # Cache for generated data to maintain consistency
        self._generated_users = []
        self._generated_products = []
        self._session_data = {}
        
    def get_user_agent(self, region: str = None) -> str:
        """Get a realistic user agent"""
        # Could customize based on region if needed
        return random.choice(self.user_agents)
    
    def get_ip_address(self, region: str, ip_ranges: List[str] = None) -> str:
        """Generate IP address for a specific region"""
        if ip_ranges:
            # Pick a random range and generate IP within it
            range_str = random.choice(ip_ranges)
            network = ipaddress.ip_network(range_str, strict=False)
            # Generate random IP within the network
            ip_int = random.randint(
                int(network.network_address) + 1,
                int(network.broadcast_address) - 1
            )
            return str(ipaddress.ip_address(ip_int))
        else:
            # Fallback to fake IP
            return self.fake.ipv4()
    
    def generate_session_id(self) -> str:
        """Generate unique session ID"""
        return str(uuid.uuid4())
    
    def generate_user_id(self, session_id: str) -> str:
        """Generate consistent user ID for a session"""
        if session_id not in self._session_data:
            self._session_data[session_id] = {
                'user_id': f"user_{random.randint(1000, 9999)}",
                'preferences': self._generate_user_preferences()
            }
        return self._session_data[session_id]['user_id']
    
    def _generate_user_preferences(self) -> Dict[str, Any]:
        """Generate user preferences that affect behavior"""
        return {
            'preferred_categories': random.sample([1, 2, 3, 4, 5], k=random.randint(1, 3)),
            'price_range': random.choice(['low', 'medium', 'high']),
            'mobile_user': random.choice([True, False])
        }
    
    # Payload generators for different endpoints
    def create_user(self) -> Dict[str, Any]:
        """Generate payload for creating a user"""
        username = self.fake.user_name() + str(random.randint(100, 999))
        return {
            "username": username,
            "email": self.fake.email(),
            "first_name": self.fake.first_name(),
            "last_name": self.fake.last_name()
        }
    
    def create_product(self) -> Dict[str, Any]:
        """Generate payload for creating a product"""
        categories = {
            1: "Electronics", 2: "Clothing", 3: "Books", 
            4: "Home & Garden", 5: "Sports"
        }
        category_id = random.randint(1, 5)
        
        return {
            "name": self.fake.catch_phrase(),
            "description": self.fake.text(max_nb_chars=200),
            "price": round(random.uniform(9.99, 999.99), 2),
            "category_id": category_id,
            "stock_quantity": random.randint(0, 500),
            "sku": f"SKU{random.randint(10000, 99999)}"
        }
    
    def add_to_cart(self) -> Dict[str, Any]:
        """Generate payload for adding item to cart"""
        return {
            "product_id": random.randint(1, 10),  # Assuming products 1-10 exist
            "quantity": random.randint(1, 3)
        }
    
    def update_cart_item(self) -> Dict[str, Any]:
        """Generate payload for updating cart item"""
        return {
            "quantity": random.randint(1, 5)
        }
    
    def checkout(self) -> Dict[str, Any]:
        """Generate payload for checkout"""
        return {
            "shipping_address": self.fake.address()
        }
    
    # Path generators for parameterized endpoints
    def product_id(self) -> str:
        """Generate product ID for path parameter"""
        return str(random.randint(1, 10))
    
    def cart_item_id(self) -> str:
        """Generate cart item ID for path parameter"""
        return str(random.randint(1, 50))
    
    def order_id(self) -> str:
        """Generate order ID for path parameter"""
        return str(random.randint(1, 100))
    
    def get_payload(self, generator_name: str) -> Dict[str, Any]:
        """Get payload by generator name"""
        generators = {
            'create_user': self.create_user,
            'create_product': self.create_product,
            'add_to_cart': self.add_to_cart,
            'update_cart_item': self.update_cart_item,
            'checkout': self.checkout
        }
        
        if generator_name in generators:
            return generators[generator_name]()
        else:
            return {}
    
    def get_path_param(self, generator_name: str) -> str:
        """Get path parameter by generator name"""
        generators = {
            'product_id': self.product_id,
            'cart_item_id': self.cart_item_id,
            'order_id': self.order_id
        }
        
        if generator_name in generators:
            return generators[generator_name]()
        else:
            return "1"  # Default fallback


class UserSession:
    """Represents a user session with consistent behavior"""
    
    def __init__(self, session_id: str, user_type: dict, region: dict, data_gen: DataGenerators):
        self.session_id = session_id
        self.user_type = user_type
        self.region = region
        self.data_gen = data_gen
        
        # Generate consistent session attributes
        self.user_id = data_gen.generate_user_id(session_id)
        self.user_agent = data_gen.get_user_agent(region['region'])
        self.ip_address = data_gen.get_ip_address(region['region'], region.get('ip_ranges'))
        
        # Session state
        self.requests_made = 0
        self.session_start = None
        self.cart_items = []  # Track items added to cart for this session
        self.last_product_viewed = None
        
    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for this session"""
        return {
            'User-Agent': self.user_agent,
            'X-Session-ID': self.session_id,
            'X-User-ID': self.user_id,
            'X-Forwarded-For': self.ip_address
        }
    
    def should_continue_session(self) -> bool:
        """Determine if session should continue based on user type"""
        max_requests = random.randint(*self.user_type['requests_per_session'])
        return self.requests_made < max_requests
    
    def get_think_time(self) -> float:
        """Get think time between requests for this user type"""
        return random.uniform(*self.user_type['think_time_seconds'])
    
    def update_state(self, endpoint_path: str, response_data: Any = None):
        """Update session state based on endpoint called"""
        self.requests_made += 1
        
        # Track cart additions for more realistic behavior
        if '/cart' in endpoint_path and response_data:
            # Could parse response and track cart state
            pass
        
        if '/products/' in endpoint_path:
            # Remember last product viewed for cart additions
            try:
                product_id = endpoint_path.split('/')[-1]
                if product_id.isdigit():
                    self.last_product_viewed = int(product_id)
            except:
                pass 
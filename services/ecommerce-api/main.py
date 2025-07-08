import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Response
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, DECIMAL, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from faker import Faker
import random

# Add shared directory to path
sys.path.append('/app/shared')
from metrics_middleware import MetricsMiddleware, add_business_metrics, lifespan_with_metrics

# Database setup
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/business")
CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://localhost:8123")
SERVICE_NAME = os.getenv("SERVICE_NAME", "ecommerce-api")

engine = create_engine(POSTGRES_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy Models (redefining from database)
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    price = Column(DECIMAL(10, 2))
    category_id = Column(Integer)
    stock_quantity = Column(Integer, default=0)
    sku = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class Cart(Base):
    __tablename__ = "carts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='active')
    
    user = relationship("User")
    items = relationship("CartItem", back_populates="cart")

class CartItem(Base):
    __tablename__ = "cart_items"
    
    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("carts.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    price_at_time = Column(DECIMAL(10, 2))
    added_at = Column(DateTime, default=datetime.utcnow)
    
    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_amount = Column(DECIMAL(10, 2))
    status = Column(String, default='pending')
    shipping_address = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    price_at_time = Column(DECIMAL(10, 2))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    order = relationship("Order", back_populates="items")
    product = relationship("Product")

# Pydantic Models
class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1

class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    price_at_time: float
    product_name: str
    total_price: float
    
class CartResponse(BaseModel):
    id: int
    user_id: int
    status: str
    items: List[CartItemResponse]
    total_amount: float
    total_items: int

class CheckoutRequest(BaseModel):
    shipping_address: str

class OrderResponse(BaseModel):
    id: int
    user_id: int
    total_amount: float
    status: str
    shipping_address: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    price_at_time: float
    product_name: str
    
class OrderDetailResponse(BaseModel):
    id: int
    user_id: int
    total_amount: float
    status: str
    shipping_address: str
    created_at: datetime
    items: List[OrderItemResponse]

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper functions
def get_or_create_cart(user_id: int, db: Session) -> Cart:
    """Get active cart for user or create new one"""
    cart = db.query(Cart).filter(
        Cart.user_id == user_id, 
        Cart.status == 'active'
    ).first()
    
    if not cart:
        cart = Cart(user_id=user_id, status='active')
        db.add(cart)
        db.commit()
        db.refresh(cart)
    
    return cart

def calculate_cart_total(cart: Cart, db: Session) -> float:
    """Calculate total amount for cart"""
    total = 0
    for item in cart.items:
        total += float(item.price_at_time) * item.quantity
    return total

def get_user_id_from_request() -> int:
    """Simulate getting user ID from request - in real app would be from JWT"""
    # For demo, we'll use a random user ID from our seed data
    return random.randint(1, 5)

# Initialize Faker
fake = Faker()

# Metrics middleware
metrics_middleware = MetricsMiddleware(None, SERVICE_NAME, CLICKHOUSE_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_with_metrics(app, metrics_middleware):
        yield

# FastAPI app
app = FastAPI(
    title="E-commerce API",
    description="E-commerce API for cart, checkout, and orders",
    version="1.0.0",
    lifespan=lifespan
)

# Add metrics middleware
app.add_middleware(MetricsMiddleware, service_name=SERVICE_NAME, clickhouse_url=CLICKHOUSE_URL)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": SERVICE_NAME}

# Cart endpoints
@app.get("/cart", response_model=CartResponse)
async def get_cart(response: Response, db: Session = Depends(get_db)):
    user_id = get_user_id_from_request()
    cart = get_or_create_cart(user_id, db)
    
    # Build response
    cart_items = []
    total_amount = 0
    total_items = 0
    
    for item in cart.items:
        product = item.product
        total_price = float(item.price_at_time) * item.quantity
        total_amount += total_price
        total_items += item.quantity
        
        cart_items.append(CartItemResponse(
            id=item.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price_at_time=float(item.price_at_time),
            product_name=product.name,
            total_price=total_price
        ))
    
    # Add business metrics
    add_business_metrics(response, 
                        cart_items_count=total_items)
    
    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        status=cart.status,
        items=cart_items,
        total_amount=total_amount,
        total_items=total_items
    )

@app.post("/cart", response_model=CartResponse)
async def add_to_cart(item: CartItemCreate, response: Response, db: Session = Depends(get_db)):
    user_id = get_user_id_from_request()
    cart = get_or_create_cart(user_id, db)
    
    # Check if product exists
    product = db.query(Product).filter(Product.id == item.product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check stock
    if product.stock_quantity < item.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    
    # Check if item already in cart
    existing_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_id == item.product_id
    ).first()
    
    if existing_item:
        # Update quantity
        existing_item.quantity += item.quantity
        existing_item.price_at_time = product.price  # Update to current price
    else:
        # Add new item
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price_at_time=product.price
        )
        db.add(cart_item)
    
    cart.updated_at = datetime.utcnow()
    db.commit()
    
    # Get updated cart
    db.refresh(cart)
    
    # Calculate totals
    total_amount = calculate_cart_total(cart, db)
    total_items = sum(item.quantity for item in cart.items)
    
    # Add business metrics
    add_business_metrics(response, 
                        product_id=str(product.id),
                        category=f"category_{product.category_id}",
                        cart_items_count=total_items)
    
    # Return updated cart (simplified for this response)
    return await get_cart(response, db)

@app.put("/cart/{item_id}")
async def update_cart_item(item_id: int, quantity: int, response: Response, db: Session = Depends(get_db)):
    user_id = get_user_id_from_request()
    
    # Find cart item
    cart_item = db.query(CartItem).join(Cart).filter(
        CartItem.id == item_id,
        Cart.user_id == user_id,
        Cart.status == 'active'
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    if quantity <= 0:
        # Remove item
        db.delete(cart_item)
    else:
        # Update quantity
        product = cart_item.product
        if product.stock_quantity < quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        
        cart_item.quantity = quantity
        cart_item.price_at_time = product.price
    
    cart_item.cart.updated_at = datetime.utcnow()
    db.commit()
    
    # Add business metrics
    add_business_metrics(response, 
                        product_id=str(cart_item.product_id),
                        category=f"category_{cart_item.product.category_id}")
    
    return {"message": "Cart updated successfully"}

# Checkout endpoint
@app.post("/checkout", response_model=OrderResponse)
async def checkout(checkout_data: CheckoutRequest, response: Response, db: Session = Depends(get_db)):
    user_id = get_user_id_from_request()
    
    # Get active cart
    cart = db.query(Cart).filter(
        Cart.user_id == user_id,
        Cart.status == 'active'
    ).first()
    
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Calculate total
    total_amount = calculate_cart_total(cart, db)
    
    # Create order
    order = Order(
        user_id=user_id,
        total_amount=total_amount,
        status='pending',
        shipping_address=checkout_data.shipping_address
    )
    db.add(order)
    db.flush()  # Get order ID
    
    # Create order items and update stock
    for cart_item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            price_at_time=cart_item.price_at_time
        )
        db.add(order_item)
        
        # Update product stock
        product = cart_item.product
        product.stock_quantity -= cart_item.quantity
    
    # Mark cart as checked out
    cart.status = 'checked_out'
    cart.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(order)
    
    # Add business metrics
    add_business_metrics(response, 
                        transaction_amount=float(total_amount),
                        cart_items_count=len(cart.items))
    
    return order

# Order endpoints
@app.get("/orders", response_model=List[OrderResponse])
async def get_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    user_id = get_user_id_from_request()
    orders = db.query(Order).filter(Order.user_id == user_id).offset(skip).limit(limit).all()
    return orders

@app.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order(order_id: int, response: Response, db: Session = Depends(get_db)):
    user_id = get_user_id_from_request()
    
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == user_id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Build order items
    order_items = []
    for item in order.items:
        order_items.append(OrderItemResponse(
            id=item.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price_at_time=float(item.price_at_time),
            product_name=item.product.name
        ))
    
    # Add business metrics
    add_business_metrics(response, 
                        transaction_amount=float(order.total_amount),
                        cart_items_count=len(order.items))
    
    return OrderDetailResponse(
        id=order.id,
        user_id=order.user_id,
        total_amount=float(order.total_amount),
        status=order.status,
        shipping_address=order.shipping_address,
        created_at=order.created_at,
        items=order_items
    )

# Demo endpoints
@app.post("/demo/generate-orders")
async def generate_demo_orders(count: int = 5, db: Session = Depends(get_db)):
    """Generate demo orders for testing"""
    orders = []
    
    # Get available users and products
    users = db.query(User).filter(User.is_active == True).limit(5).all()
    products = db.query(Product).filter(Product.is_active == True).limit(10).all()
    
    if not users or not products:
        raise HTTPException(status_code=400, detail="Need users and products in database first")
    
    for _ in range(count):
        user = random.choice(users)
        
        # Create order with random products
        total_amount = 0
        order = Order(
            user_id=user.id,
            total_amount=0,  # Will calculate
            status=random.choice(['pending', 'confirmed', 'shipped']),
            shipping_address=fake.address()
        )
        db.add(order)
        db.flush()
        
        # Add 1-5 random products
        num_items = random.randint(1, 5)
        selected_products = random.sample(products, min(num_items, len(products)))
        
        for product in selected_products:
            quantity = random.randint(1, 3)
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                price_at_time=product.price
            )
            db.add(order_item)
            total_amount += float(product.price) * quantity
        
        order.total_amount = total_amount
        orders.append(order)
    
    db.commit()
    return {"message": f"Generated {count} demo orders", "count": len(orders)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
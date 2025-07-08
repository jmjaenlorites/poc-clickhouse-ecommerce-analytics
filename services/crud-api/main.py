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
SERVICE_NAME = os.getenv("SERVICE_NAME", "crud-api")

engine = create_engine(POSTGRES_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy Models
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

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    price = Column(DECIMAL(10, 2))
    category_id = Column(Integer, ForeignKey("categories.id"))
    stock_quantity = Column(Integer, default=0)
    sku = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    category = relationship("Category")

# Pydantic Models
class UserCreate(BaseModel):
    username: str
    email: str
    first_name: str
    last_name: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    category_id: int
    stock_quantity: int = 0
    sku: str

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: Optional[int] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    price: float
    category_id: int
    stock_quantity: int
    sku: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize Faker for realistic data
fake = Faker()

# Metrics middleware
metrics_middleware = MetricsMiddleware(None, SERVICE_NAME, CLICKHOUSE_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_with_metrics(app, metrics_middleware):
        yield

# FastAPI app
app = FastAPI(
    title="CRUD API",
    description="Simple CRUD API for users and products",
    version="1.0.0",
    lifespan=lifespan
)

# Add metrics middleware
app.add_middleware(MetricsMiddleware, service_name=SERVICE_NAME, clickhouse_url=CLICKHOUSE_URL)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": SERVICE_NAME}

# User endpoints
@app.get("/users", response_model=List[UserResponse])
async def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == True).offset(skip).limit(limit).all()
    return users

@app.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate, response: Response, db: Session = Depends(get_db)):
    # Check if user exists
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create user
    db_user = User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Add business metrics
    add_business_metrics(response, 
                        category="user_management")
    
    return db_user

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Product endpoints
@app.get("/products", response_model=List[ProductResponse])
async def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.is_active == True).offset(skip).limit(limit).all()
    return products

@app.post("/products", response_model=ProductResponse)
async def create_product(product: ProductCreate, response: Response, db: Session = Depends(get_db)):
    # Check if SKU exists
    if db.query(Product).filter(Product.sku == product.sku).first():
        raise HTTPException(status_code=400, detail="SKU already exists")
    
    # Create product
    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    # Get category for metrics
    category = db.query(Category).filter(Category.id == product.category_id).first()
    category_name = category.name if category else "unknown"
    
    # Add business metrics
    add_business_metrics(response, 
                        product_id=str(db_product.id),
                        category=category_name)
    
    return db_product

@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, response: Response, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get category for metrics
    category = db.query(Category).filter(Category.id == product.category_id).first()
    category_name = category.name if category else "unknown"
    
    # Add business metrics
    add_business_metrics(response, 
                        product_id=str(product.id),
                        category=category_name)
    
    return product

@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, product_update: ProductUpdate, response: Response, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Update fields
    update_data = product_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    
    # Get category for metrics
    category = db.query(Category).filter(Category.id == product.category_id).first()
    category_name = category.name if category else "unknown"
    
    # Add business metrics
    add_business_metrics(response, 
                        product_id=str(product.id),
                        category=category_name)
    
    return product

@app.delete("/products/{product_id}")
async def delete_product(product_id: int, response: Response, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Soft delete
    product.is_active = False
    product.updated_at = datetime.utcnow()
    db.commit()
    
    # Get category for metrics
    category = db.query(Category).filter(Category.id == product.category_id).first()
    category_name = category.name if category else "unknown"
    
    # Add business metrics
    add_business_metrics(response, 
                        product_id=str(product.id),
                        category=category_name)
    
    return {"message": "Product deleted successfully"}

# Demo endpoints for generating test data
@app.post("/demo/generate-users")
async def generate_demo_users(count: int = 10, db: Session = Depends(get_db)):
    """Generate demo users for testing"""
    users = []
    for _ in range(count):
        user = User(
            username=fake.user_name() + str(random.randint(1, 9999)),
            email=fake.email(),
            first_name=fake.first_name(),
            last_name=fake.last_name()
        )
        db.add(user)
        users.append(user)
    
    db.commit()
    return {"message": f"Generated {count} demo users", "count": len(users)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
import os
import time
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Response, status
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "catalog", "message": "%(message)s"}')
logger = logging.getLogger("catalog")

app = FastAPI(title="Catalog Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8002"))
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./catalog.db")
START_TIME = time.time()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class RestaurantModel(Base):
    __tablename__ = "restaurants"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    address = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    cuisine = Column(String, index=True)
    rating = Column(Float, default=4.5)
    is_open = Column(Boolean, default=True)

class MenuItemModel(Base):
    __tablename__ = "menu_items"
    id = Column(String, primary_key=True, index=True)
    restaurant_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    price_cents = Column(Integer, nullable=False)
    category = Column(String)
    is_available = Column(Boolean, default=True)

Base.metadata.create_all(bind=engine)

# Seed catalog if empty
with SessionLocal() as db:
    if not db.query(RestaurantModel).first():
        r1 = RestaurantModel(id="rest-01", name="Burger Craft & Grill", description="Juicy smash burgers, hand-cut fries and craft drinks", address="Khreshchatyk St, 15, Kyiv", latitude=50.4474, longitude=30.5222, cuisine="Burgers", rating=4.8, is_open=True)
        r2 = RestaurantModel(id="rest-02", name="Napoli Woodfire Pizza", description="Authentic Neapolitan sourdough pizza", address="Sahaidachnoho St, 28, Kyiv", latitude=50.4611, longitude=30.5189, cuisine="Pizza", rating=4.9, is_open=True)
        r3 = RestaurantModel(id="rest-03", name="Tokyo Ramen & Bowls", description="Traditional rich Tonkotsu ramen and gyoza", address="Velyka Vasylkivska St, 42, Kyiv", latitude=50.4358, longitude=30.5173, cuisine="Asian", rating=4.7, is_open=True)
        db.add_all([r1, r2, r3])

        items = [
            MenuItemModel(id="item-01", restaurant_id="rest-01", name="Double Bacon Cheeseburger", description="Black Angus beef, aged cheddar, crispy bacon", price_cents=28000, category="Burgers", is_available=True),
            MenuItemModel(id="item-02", restaurant_id="rest-01", name="Truffle Parmesan Fries", description="Crispy fries with white truffle oil and parmesan", price_cents=12000, category="Sides", is_available=True),
            MenuItemModel(id="item-03", restaurant_id="rest-01", name="Craft Cola", description="Organic craft soda with vanilla", price_cents=6500, category="Drinks", is_available=True),
            MenuItemModel(id="item-04", restaurant_id="rest-02", name="Pizza Margherita DOP", description="San Marzano tomatoes, buffalo mozzarella, fresh basil", price_cents=29500, category="Pizza", is_available=True),
            MenuItemModel(id="item-05", restaurant_id="rest-02", name="Pizza Diavola", description="Spicy calabrian salame, chili flakes", price_cents=34000, category="Pizza", is_available=True),
            MenuItemModel(id="item-06", restaurant_id="rest-02", name="Tiramisu", description="House-made savoiardi with espresso and mascarpone", price_cents=16000, category="Desserts", is_available=True),
            MenuItemModel(id="item-07", restaurant_id="rest-03", name="Tonkotsu Chashu Ramen", description="16-hour pork broth, spring noodles, tender chashu", price_cents=32000, category="Ramen", is_available=True),
            MenuItemModel(id="item-08", restaurant_id="rest-03", name="Crispy Pork Gyoza (6 pcs)", description="Pan-fried Japanese dumplings with ponzu sauce", price_cents=17500, category="Starters", is_available=True),
        ]
        db.add_all(items)
        db.commit()

class RestaurantSchema(BaseModel):
    id: str
    name: str
    description: str
    address: str
    latitude: float
    longitude: float
    cuisine: str
    rating: float
    is_open: bool

    class Config:
        from_attributes = True

class MenuItemSchema(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: str
    price_cents: int
    category: str
    is_available: bool

    class Config:
        from_attributes = True

# Probes
@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "catalog", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "READY", "service": "catalog", "database": "CONNECTED"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "NOT_READY", "service": "catalog", "database": "DISCONNECTED", "error": str(e)}

# API
@app.get("/api/v1/restaurants", response_model=List[RestaurantSchema])
def list_restaurants(cuisine: Optional[str] = None):
    with SessionLocal() as db:
        q = db.query(RestaurantModel)
        if cuisine:
            q = q.filter(RestaurantModel.cuisine.ilike(cuisine))
        return q.all()

@app.get("/api/v1/restaurants/{restaurant_id}", response_model=RestaurantSchema)
def get_restaurant(restaurant_id: str):
    with SessionLocal() as db:
        r = db.query(RestaurantModel).filter(RestaurantModel.id == restaurant_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        return r

@app.get("/api/v1/restaurants/{restaurant_id}/menu", response_model=List[MenuItemSchema])
def get_restaurant_menu(restaurant_id: str):
    with SessionLocal() as db:
        return db.query(MenuItemModel).filter(MenuItemModel.restaurant_id == restaurant_id).all()

@app.get("/api/v1/items/{item_id}", response_model=MenuItemSchema)
def get_item(item_id: str):
    with SessionLocal() as db:
        it = db.query(MenuItemModel).filter(MenuItemModel.id == item_id).first()
        if not it:
            raise HTTPException(status_code=404, detail="Item not found")
        return it

@app.get("/api/v1/items/search", response_model=List[MenuItemSchema])
def search_items(query: str, restaurant_id: Optional[str] = None):
    with SessionLocal() as db:
        q = db.query(MenuItemModel).filter(
            (MenuItemModel.name.ilike(f"%{query}%")) | (MenuItemModel.description.ilike(f"%{query}%"))
        )
        if restaurant_id:
            q = q.filter(MenuItemModel.restaurant_id == restaurant_id)
        return q.all()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

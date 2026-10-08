import os
import logging
from typing import List, Optional, Dict
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "catalog", "message": "%(message)s"}')
logger = logging.getLogger("catalog")

app = FastAPI(title="Catalog Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8002"))

class Restaurant(BaseModel):
    id: str
    name: str
    description: str
    address: str
    latitude: float
    longitude: float
    cuisine: str
    rating: float
    is_open: bool

class MenuItem(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: str
    price_cents: int
    category: str
    is_available: bool

# In-memory storage
restaurants: Dict[str, Restaurant] = {
    "rest-01": Restaurant(id="rest-01", name="Burger Craft & Grill", description="Juicy smash burgers, hand-cut fries and craft drinks", address="Khreshchatyk St, 15, Kyiv", latitude=50.4474, longitude=30.5222, cuisine="Burgers", rating=4.8, is_open=True),
    "rest-02": Restaurant(id="rest-02", name="Napoli Woodfire Pizza", description="Authentic Neapolitan sourdough pizza", address="Sahaidachnoho St, 28, Kyiv", latitude=50.4611, longitude=30.5189, cuisine="Pizza", rating=4.9, is_open=True),
    "rest-03": Restaurant(id="rest-03", name="Tokyo Ramen & Bowls", description="Traditional rich Tonkotsu ramen and gyoza", address="Velyka Vasylkivska St, 42, Kyiv", latitude=50.4358, longitude=30.5173, cuisine="Asian", rating=4.7, is_open=True),
}

menu_items: Dict[str, MenuItem] = {
    "item-01": MenuItem(id="item-01", restaurant_id="rest-01", name="Double Bacon Cheeseburger", description="Black Angus beef, aged cheddar, crispy bacon", price_cents=28000, category="Burgers", is_available=True),
    "item-02": MenuItem(id="item-02", restaurant_id="rest-01", name="Truffle Parmesan Fries", description="Crispy fries with white truffle oil and parmesan", price_cents=12000, category="Sides", is_available=True),
    "item-03": MenuItem(id="item-03", restaurant_id="rest-01", name="Craft Cola", description="Organic craft soda with vanilla", price_cents=6500, category="Drinks", is_available=True),
    "item-04": MenuItem(id="item-04", restaurant_id="rest-02", name="Pizza Margherita DOP", description="San Marzano tomatoes, buffalo mozzarella, fresh basil", price_cents=29500, category="Pizza", is_available=True),
    "item-05": MenuItem(id="item-05", restaurant_id="rest-02", name="Pizza Diavola", description="Spicy calabrian salame, chili flakes", price_cents=34000, category="Pizza", is_available=True),
    "item-06": MenuItem(id="item-06", restaurant_id="rest-02", name="Tiramisu", description="House-made savoiardi with espresso and mascarpone", price_cents=16000, category="Desserts", is_available=True),
    "item-07": MenuItem(id="item-07", restaurant_id="rest-03", name="Tonkotsu Chashu Ramen", description="16-hour pork broth, spring noodles, tender chashu", price_cents=32000, category="Ramen", is_available=True),
    "item-08": MenuItem(id="item-08", restaurant_id="rest-03", name="Crispy Pork Gyoza (6 pcs)", description="Pan-fried Japanese dumplings with ponzu sauce", price_cents=17500, category="Starters", is_available=True),
}

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "catalog"}

@app.get("/api/v1/restaurants", response_model=List[Restaurant])
def list_restaurants(cuisine: Optional[str] = None):
    res = list(restaurants.values())
    if cuisine:
        res = [r for r in res if r.cuisine.lower() == cuisine.lower()]
    return res

@app.get("/api/v1/restaurants/{restaurant_id}", response_model=Restaurant)
def get_restaurant(restaurant_id: str):
    r = restaurants.get(restaurant_id)
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return r

@app.get("/api/v1/restaurants/{restaurant_id}/menu", response_model=List[MenuItem])
def get_restaurant_menu(restaurant_id: str):
    return [it for it in menu_items.values() if it.restaurant_id == restaurant_id]

@app.get("/api/v1/items/{item_id}", response_model=MenuItem)
def get_item(item_id: str):
    it = menu_items.get(item_id)
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    return it

@app.get("/api/v1/items/search", response_model=List[MenuItem])
def search_items(query: str, restaurant_id: Optional[str] = None):
    q = query.lower()
    results = []
    for it in menu_items.values():
        if restaurant_id and it.restaurant_id != restaurant_id:
            continue
        if q in it.name.lower() or q in it.description.lower():
            results.append(it)
    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

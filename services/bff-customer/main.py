import os
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Header
import httpx
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "bff-customer", "message": "%(message)s"}')
logger = logging.getLogger("bff-customer")

app = FastAPI(title="BFF Customer API", version="1.0.0")
PORT = int(os.environ.get("PORT", "8022"))

IDENTITY_URL = os.environ.get("IDENTITY_URL", "http://localhost:8001")
CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:8002")
CART_URL = os.environ.get("CART_URL", "http://localhost:8004")
ORDER_URL = os.environ.get("ORDER_URL", "http://localhost:8014")
GEO_URL = os.environ.get("GEO_URL", "http://localhost:8008")

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AddCartItemRequest(BaseModel):
    restaurant_id: str
    item_id: str
    name: str
    price_cents: int
    quantity: int = 1

class CheckoutRequest(BaseModel):
    delivery_address: str
    delivery_lat: Optional[float] = 50.4501
    delivery_lon: Optional[float] = 30.5234
    promo_code: Optional[str] = ""
    payment_method: Optional[str] = "card"

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "bff-customer"}

# Auth
@app.post("/api/v1/auth/register")
def register(req: RegisterRequest):
    with httpx.Client(timeout=3.0) as client:
        res = client.post(f"{IDENTITY_URL}/api/v1/auth/register", json=req.model_dump())
        if res.status_code != 201:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()

@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    with httpx.Client(timeout=3.0) as client:
        res = client.post(f"{IDENTITY_URL}/api/v1/auth/login", json=req.model_dump())
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Invalid credentials")
        return res.json()

# Catalog
@app.get("/api/v1/restaurants")
def list_restaurants(cuisine: Optional[str] = None):
    with httpx.Client(timeout=3.0) as client:
        params = {"cuisine": cuisine} if cuisine else {}
        res = client.get(f"{CATALOG_URL}/api/v1/restaurants", params=params)
        return res.json()

@app.get("/api/v1/restaurants/{restaurant_id}/menu")
def get_restaurant_menu(restaurant_id: str):
    with httpx.Client(timeout=3.0) as client:
        res = client.get(f"{CATALOG_URL}/api/v1/restaurants/{restaurant_id}/menu")
        return res.json()

# Cart
@app.get("/api/v1/cart")
def get_cart(x_user_id: str = Header("default-customer")):
    with httpx.Client(timeout=3.0) as client:
        res = client.get(f"{CART_URL}/api/v1/cart/{x_user_id}")
        return res.json()

@app.post("/api/v1/cart/items")
def add_to_cart(req: AddCartItemRequest, x_user_id: str = Header("default-customer")):
    with httpx.Client(timeout=3.0) as client:
        res = client.post(f"{CART_URL}/api/v1/cart/{x_user_id}/items", json=req.model_dump())
        return res.json()

@app.delete("/api/v1/cart")
def clear_cart(x_user_id: str = Header("default-customer")):
    with httpx.Client(timeout=3.0) as client:
        res = client.delete(f"{CART_URL}/api/v1/cart/{x_user_id}")
        return res.json()

# Checkout & Tracking
@app.post("/api/v1/checkout")
def checkout(req: CheckoutRequest, x_user_id: str = Header("default-customer")):
    with httpx.Client(timeout=5.0) as client:
        # 1. Fetch cart
        cart_res = client.get(f"{CART_URL}/api/v1/cart/{x_user_id}")
        cart = cart_res.json()
        if not cart.get("items"):
            raise HTTPException(status_code=400, detail="Cart is empty")

        # 2. Place order
        order_payload = {
            "customer_id": x_user_id,
            "restaurant_id": cart["restaurant_id"],
            "items": cart["items"],
            "delivery_address": req.delivery_address,
            "delivery_lat": req.delivery_lat,
            "delivery_lon": req.delivery_lon,
            "promo_code": req.promo_code,
            "payment_method": req.payment_method,
        }
        order_res = client.post(f"{ORDER_URL}/api/v1/orders", json=order_payload)
        if order_res.status_code != 201:
            raise HTTPException(status_code=order_res.status_code, detail=order_res.text)

        # 3. Clear cart
        client.delete(f"{CART_URL}/api/v1/cart/{x_user_id}")
        return order_res.json()

@app.get("/api/v1/orders/{order_id}")
def get_order_tracking(order_id: str):
    with httpx.Client(timeout=3.0) as client:
        res = client.get(f"{ORDER_URL}/api/v1/orders/{order_id}")
        if res.status_code != 200:
            raise HTTPException(status_code=404, detail="Order not found")
        order = res.json()

        # Fetch courier live location
        courier_loc = None
        if order.get("courier_id"):
            try:
                geo_res = client.get(f"{GEO_URL}/api/v1/geo/location/{order['courier_id']}")
                if geo_res.status_code == 200:
                    courier_loc = geo_res.json()
            except Exception:
                pass
        order["courier_location"] = courier_loc
        return order

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

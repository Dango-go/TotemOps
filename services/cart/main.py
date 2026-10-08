import os
import time
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "cart", "message": "%(message)s"}')
logger = logging.getLogger("cart")

app = FastAPI(title="Cart Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8004"))

class CartItem(BaseModel):
    item_id: str
    name: str
    price_cents: int
    quantity: int

class AddItemRequest(BaseModel):
    restaurant_id: str
    item_id: str
    name: str
    price_cents: int
    quantity: Optional[int] = 1

class UpdateItemQuantityRequest(BaseModel):
    quantity: int

class CartResponse(BaseModel):
    user_id: str
    restaurant_id: str
    items: List[CartItem]
    subtotal_cents: int
    updated_at: int

# In-memory storage: user_id -> {restaurant_id, items, updated_at}
carts: Dict[str, dict] = {}

def get_or_create_cart(user_id: str, restaurant_id: str = "") -> dict:
    if user_id not in carts:
        carts[user_id] = {
            "restaurant_id": restaurant_id,
            "items": {},
            "updated_at": int(time.time()),
        }
        return carts[user_id]

    c = carts[user_id]
    if restaurant_id and c["restaurant_id"] and c["restaurant_id"] != restaurant_id:
        c["restaurant_id"] = restaurant_id
        c["items"] = {}
    elif restaurant_id and not c["restaurant_id"]:
        c["restaurant_id"] = restaurant_id
    c["updated_at"] = int(time.time())
    return c

def build_cart_response(user_id: str) -> CartResponse:
    c = get_or_create_cart(user_id)
    items_list = list(c["items"].values())
    subtotal = sum(it.quantity * it.price_cents for it in items_list)
    return CartResponse(
        user_id=user_id,
        restaurant_id=c["restaurant_id"],
        items=items_list,
        subtotal_cents=subtotal,
        updated_at=c["updated_at"],
    )

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "cart"}

@app.get("/api/v1/cart/{user_id}", response_model=CartResponse)
def get_cart(user_id: str):
    return build_cart_response(user_id)

@app.post("/api/v1/cart/{user_id}/items", response_model=CartResponse)
def add_item(user_id: str, req: AddItemRequest):
    c = get_or_create_cart(user_id, req.restaurant_id)
    if req.item_id in c["items"]:
        c["items"][req.item_id].quantity += (req.quantity or 1)
    else:
        c["items"][req.item_id] = CartItem(
            item_id=req.item_id,
            name=req.name,
            price_cents=req.price_cents,
            quantity=max(req.quantity or 1, 1),
        )
    c["updated_at"] = int(time.time())
    logger.info(f"Added item {req.item_id} to cart for user {user_id}")
    return build_cart_response(user_id)

@app.put("/api/v1/cart/{user_id}/items/{item_id}", response_model=CartResponse)
def update_quantity(user_id: str, item_id: str, req: UpdateItemQuantityRequest):
    c = get_or_create_cart(user_id)
    if req.quantity <= 0:
        c["items"].pop(item_id, None)
    elif item_id in c["items"]:
        c["items"][item_id].quantity = req.quantity
    c["updated_at"] = int(time.time())
    return build_cart_response(user_id)

@app.delete("/api/v1/cart/{user_id}/items/{item_id}", response_model=CartResponse)
def remove_item(user_id: str, item_id: str):
    c = get_or_create_cart(user_id)
    c["items"].pop(item_id, None)
    c["updated_at"] = int(time.time())
    return build_cart_response(user_id)

@app.delete("/api/v1/cart/{user_id}")
def clear_cart(user_id: str):
    carts.pop(user_id, None)
    return {"success": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

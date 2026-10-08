import os
import uuid
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "inventory", "message": "%(message)s"}')
logger = logging.getLogger("inventory")

app = FastAPI(title="Inventory Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8005"))

class StockItem(BaseModel):
    item_id: str
    quantity: int

class CheckStockRequest(BaseModel):
    restaurant_id: str
    items: List[StockItem]

class ReserveStockRequest(BaseModel):
    order_id: str
    restaurant_id: str
    items: List[StockItem]

class StockActionRequest(BaseModel):
    reservation_id: str

# Default available stocks
stock: Dict[str, int] = {
    "item-01": 50,  # Double Bacon Cheeseburger
    "item-02": 100, # Truffle Fries
    "item-03": 80,  # Craft Cola
    "item-04": 40,  # Pizza Margherita
    "item-05": 30,  # Pizza Diavola
    "item-06": 25,  # Tiramisu
    "item-07": 45,  # Ramen
    "item-08": 60,  # Gyoza
}

reservations: Dict[str, dict] = {}

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "inventory"}

@app.post("/api/v1/inventory/check")
def check_stock(req: CheckStockRequest):
    out_of_stock = []
    for it in req.items:
        avail = stock.get(it.item_id, 20)
        if avail < it.quantity:
            out_of_stock.append(it.item_id)
    return {"in_stock": len(out_of_stock) == 0, "out_of_stock_item_ids": out_of_stock}

@app.post("/api/v1/inventory/reserve")
def reserve_stock(req: ReserveStockRequest):
    for it in req.items:
        avail = stock.get(it.item_id, 20)
        if avail < it.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for item {it.item_id}")

    items_map = {}
    for it in req.items:
        stock[it.item_id] = stock.get(it.item_id, 20) - it.quantity
        items_map[it.item_id] = it.quantity

    res_id = f"res-{uuid.uuid4().hex[:8]}"
    reservations[res_id] = {
        "order_id": req.order_id,
        "items": items_map,
        "status": "RESERVED",
    }
    logger.info(f"Reserved stock for order {req.order_id}, reservation_id={res_id}")
    return {"success": True, "reservation_id": res_id}

@app.post("/api/v1/inventory/release")
def release_stock(req: StockActionRequest):
    res = reservations.get(req.reservation_id)
    if res and res["status"] == "RESERVED":
        for item_id, qty in res["items"].items():
            stock[item_id] = stock.get(item_id, 0) + qty
        res["status"] = "RELEASED"
        logger.info(f"Released reservation {req.reservation_id}")
    return {"success": True}

@app.post("/api/v1/inventory/commit")
def commit_stock(req: StockActionRequest):
    res = reservations.get(req.reservation_id)
    if res:
        res["status"] = "COMMITTED"
        logger.info(f"Committed reservation {req.reservation_id}")
    return {"success": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

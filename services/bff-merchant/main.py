import os
import time
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import httpx
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "bff-merchant", "message": "%(message)s"}')
logger = logging.getLogger("bff-merchant")

app = FastAPI(title="BFF Merchant API", version="1.0.0")
PORT = int(os.environ.get("PORT", "8020"))

CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:8002")
ORDER_URL = os.environ.get("ORDER_URL", "http://localhost:8014")

class UpdateOrderStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = ""

START_TIME = time.time()

@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "bff-merchant", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness():
    return {"status": "READY", "service": "bff-merchant"}

@app.get("/api/v1/merchant/restaurants/{restaurant_id}/menu")
def get_restaurant_menu(restaurant_id: str):
    with httpx.Client(timeout=3.0) as client:
        res = client.get(f"{CATALOG_URL}/api/v1/restaurants/{restaurant_id}/menu")
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Failed to fetch menu")
        return res.json()

@app.post("/api/v1/merchant/orders/{order_id}/status")
def update_order_status(order_id: str, req: UpdateOrderStatusRequest):
    with httpx.Client(timeout=3.0) as client:
        res = client.put(f"{ORDER_URL}/api/v1/orders/{order_id}/status", json=req.model_dump())
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()

@app.post("/api/v1/merchant/orders/{order_id}/accept")
def accept_order(order_id: str):
    return update_order_status(order_id, UpdateOrderStatusRequest(status="ACCEPTED", notes="Accepted by kitchen"))

@app.post("/api/v1/merchant/orders/{order_id}/cooking")
def start_cooking_order(order_id: str):
    return update_order_status(order_id, UpdateOrderStatusRequest(status="COOKING", notes="Chef started cooking"))

@app.post("/api/v1/merchant/orders/{order_id}/ready")
def mark_order_ready(order_id: str):
    return update_order_status(order_id, UpdateOrderStatusRequest(status="READY_FOR_PICKUP", notes="Food packed and ready for pickup"))

@app.post("/api/v1/merchant/orders/{order_id}/reject")
def reject_order(order_id: str, notes: Optional[str] = "Kitchen cannot fulfill order"):
    with httpx.Client(timeout=3.0) as client:
        res = client.post(f"{ORDER_URL}/api/v1/orders/{order_id}/cancel", json={"reason": notes})
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)


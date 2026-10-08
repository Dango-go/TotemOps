import os
import time
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "pricing", "message": "%(message)s"}')
logger = logging.getLogger("pricing")

app = FastAPI(title="Pricing Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8003"))

class OrderItemPricingInput(BaseModel):
    item_id: str
    quantity: int
    unit_price_cents: int

class CalculatePriceRequest(BaseModel):
    restaurant_id: str
    items: List[OrderItemPricingInput]
    promo_code: Optional[str] = ""
    distance_km: Optional[float] = 3.0

class PriceResponse(BaseModel):
    subtotal_cents: int
    delivery_fee_cents: int
    discount_cents: int
    surge_fee_cents: int
    total_cents: int
    surge_multiplier: float

BASE_DELIVERY_FEE_CENTS = 5000  # 50 UAH
PER_KM_FEE_CENTS = 1500         # 15 UAH/km
ACTIVE_SURGE = 1.2              # 20% surge during peak

START_TIME = time.time()

@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "pricing", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness():
    return {"status": "READY", "service": "pricing"}

@app.post("/api/v1/pricing/calculate", response_model=PriceResponse)
def calculate_order_price(req: CalculatePriceRequest):
    subtotal = sum(it.quantity * it.unit_price_cents for it in req.items)
    dist = max(req.distance_km or 1.0, 1.0)
    base_fee = int(BASE_DELIVERY_FEE_CENTS + (dist * PER_KM_FEE_CENTS))
    surge_fee = int(base_fee * (ACTIVE_SURGE - 1.0))
    delivery_fee = base_fee + surge_fee

    discount = 0
    promo = (req.promo_code or "").strip().upper()
    if promo == "TOTEM10":
        discount = int(subtotal * 0.10)
    elif promo == "WELCOME50":
        discount = 5000

    discount = min(discount, subtotal)
    total = subtotal + delivery_fee - discount

    logger.info(f"Calculated price: subtotal={subtotal}, delivery={delivery_fee}, discount={discount}, total={total}")
    return PriceResponse(
        subtotal_cents=subtotal,
        delivery_fee_cents=delivery_fee,
        discount_cents=discount,
        surge_fee_cents=surge_fee,
        total_cents=total,
        surge_multiplier=ACTIVE_SURGE,
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

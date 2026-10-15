import os
import time
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "eta", "message": "%(message)s"}')
logger = logging.getLogger("eta")

app = FastAPI(title="ETA Service", version="1.1.0")
PORT = int(os.environ.get("PORT", "8007"))

TRANSPORT_SPEEDS_KMH = {
    "PEDESTRIAN": 5.0,
    "BICYCLE": 16.0,
    "CAR": 35.0,
}

class EstimateETARequest(BaseModel):
    restaurant_id: str
    distance_km: float = 3.0
    items_count: int = 2
    transport_type: Optional[str] = "BICYCLE"

class ETAResponse(BaseModel):
    prep_time_minutes: int
    delivery_time_minutes: int
    buffer_minutes: int
    total_eta_minutes: int
    transport_type: str
    estimated_delivery_timestamp: int

START_TIME = time.time()

@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "eta", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness():
    return {"status": "READY", "service": "eta"}

@app.post("/api/v1/eta/estimate", response_model=ETAResponse)
def estimate_eta(req: EstimateETARequest):
    dist = max(req.distance_km, 0.5)
    cnt = max(req.items_count, 1)
    transport = (req.transport_type or "BICYCLE").upper()
    speed = TRANSPORT_SPEEDS_KMH.get(transport, 16.0)

    # 1. Час приготування на кухні
    prep_time = 10 + (cnt * 2)

    # 2. Час руху з урахуванням швидкості транспорту
    travel_time = max(int((dist / speed) * 60), 2)

    # 3. Буферний час (паркування, ліфт, передача пакунка)
    buffer_time = 4

    total = prep_time + travel_time + buffer_time
    now = int(time.time())

    logger.info(f"ETA calculated: dist={dist}km ({transport}), prep={prep_time}m, travel={travel_time}m, total={total}m")
    return ETAResponse(
        prep_time_minutes=prep_time,
        delivery_time_minutes=travel_time,
        buffer_minutes=buffer_time,
        total_eta_minutes=total,
        transport_type=transport,
        estimated_delivery_timestamp=now + (total * 60),
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

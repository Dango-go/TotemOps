import os
import time
import logging
from pydantic import BaseModel
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "eta", "message": "%(message)s"}')
logger = logging.getLogger("eta")

app = FastAPI(title="ETA Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8007"))

class EstimateETARequest(BaseModel):
    restaurant_id: str
    distance_km: float = 3.0
    items_count: int = 2

class ETAResponse(BaseModel):
    prep_time_minutes: int
    delivery_time_minutes: int
    total_eta_minutes: int
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
    dist = max(req.distance_km, 1.0)
    cnt = max(req.items_count, 1)

    prep_time = 10 + (cnt * 2)
    delivery_time = int(dist * 4) + 5
    total = prep_time + delivery_time
    now = int(time.time())

    logger.info(f"ETA estimated: prep={prep_time}m, delivery={delivery_time}m, total={total}m")
    return ETAResponse(
        prep_time_minutes=prep_time,
        delivery_time_minutes=delivery_time,
        total_eta_minutes=total,
        estimated_delivery_timestamp=now + (total * 60),
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

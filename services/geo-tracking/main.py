import os
import time
import logging
from typing import Dict, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "geo-tracking", "message": "%(message)s"}')
logger = logging.getLogger("geo-tracking")

app = FastAPI(title="Geo Tracking Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8008"))

class LocationUpdate(BaseModel):
    courier_id: str
    latitude: float
    longitude: float
    speed_kmh: Optional[float] = 15.0
    heading: Optional[float] = 90.0

class LocationRecord(BaseModel):
    courier_id: str
    latitude: float
    longitude: float
    speed_kmh: float
    heading: float
    updated_at: int

locations: Dict[str, LocationRecord] = {
    "courier-01": LocationRecord(courier_id="courier-01", latitude=50.4501, longitude=30.5234, speed_kmh=18.5, heading=90.0, updated_at=int(time.time())),
}

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "geo-tracking"}

@app.post("/api/v1/geo/location", response_model=LocationRecord)
def update_location(loc: LocationUpdate):
    rec = LocationRecord(
        courier_id=loc.courier_id,
        latitude=loc.latitude,
        longitude=loc.longitude,
        speed_kmh=loc.speed_kmh or 0.0,
        heading=loc.heading or 0.0,
        updated_at=int(time.time()),
    )
    locations[loc.courier_id] = rec
    return rec

@app.get("/api/v1/geo/location/{courier_id}", response_model=LocationRecord)
def get_location(courier_id: str):
    rec = locations.get(courier_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Courier location not found")
    return rec

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

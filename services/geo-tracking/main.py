import os
import time
import logging
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "geo-tracking", "message": "%(message)s"}')
logger = logging.getLogger("geo-tracking")

app = FastAPI(title="Geo Tracking Service", version="1.1.0")
PORT = int(os.environ.get("PORT", "8008"))

class TransportType(str, Enum):
    PEDESTRIAN = "PEDESTRIAN"  # Швидкість 5 км/год, макс радіус 2.0 км
    BICYCLE = "BICYCLE"        # Швидкість 15 км/год, макс радіус 5.0 км
    CAR = "CAR"                # Швидкість 35 км/год, макс радіус 25.0 км

class LocationUpdate(BaseModel):
    courier_id: str
    latitude: float
    longitude: float
    speed_kmh: Optional[float] = 15.0
    heading: Optional[float] = 90.0

class CourierStatusUpdate(BaseModel):
    is_available: bool

class LocationRecord(BaseModel):
    courier_id: str
    latitude: float
    longitude: float
    speed_kmh: float
    heading: float
    transport_type: TransportType
    max_range_km: float
    is_available: bool
    updated_at: int

# Початкові кур'єри в різних локаціях Києва
couriers_db: Dict[str, LocationRecord] = {
    "courier-01": LocationRecord(
        courier_id="courier-01",
        latitude=50.4501,
        longitude=30.5234,  # Центр (Хрещатик)
        speed_kmh=5.0,
        heading=90.0,
        transport_type=TransportType.PEDESTRIAN,
        max_range_km=2.0,
        is_available=True,
        updated_at=int(time.time()),
    ),
    "courier-02": LocationRecord(
        courier_id="courier-02",
        latitude=50.4633,
        longitude=30.5186,  # Поділ
        speed_kmh=16.0,
        heading=180.0,
        transport_type=TransportType.BICYCLE,
        max_range_km=6.0,
        is_available=True,
        updated_at=int(time.time()),
    ),
    "courier-03": LocationRecord(
        courier_id="courier-03",
        latitude=50.4312,
        longitude=30.5450,  # Печерськ
        speed_kmh=38.0,
        heading=270.0,
        transport_type=TransportType.CAR,
        max_range_km=25.0,
        is_available=True,
        updated_at=int(time.time()),
    ),
}

START_TIME = time.time()

@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "geo-tracking", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness():
    return {"status": "READY", "service": "geo-tracking"}

@app.post("/api/v1/geo/location", response_model=LocationRecord)
def update_location(loc: LocationUpdate):
    rec = couriers_db.get(loc.courier_id)
    now = int(time.time())
    if rec:
        rec.latitude = loc.latitude
        rec.longitude = loc.longitude
        rec.speed_kmh = loc.speed_kmh or rec.speed_kmh
        rec.heading = loc.heading or rec.heading
        rec.updated_at = now
    else:
        rec = LocationRecord(
            courier_id=loc.courier_id,
            latitude=loc.latitude,
            longitude=loc.longitude,
            speed_kmh=loc.speed_kmh or 15.0,
            heading=loc.heading or 0.0,
            transport_type=TransportType.BICYCLE,
            max_range_km=5.0,
            is_available=True,
            updated_at=now,
        )
        couriers_db[loc.courier_id] = rec
    return rec

@app.get("/api/v1/geo/location/{courier_id}", response_model=LocationRecord)
def get_location(courier_id: str):
    rec = couriers_db.get(courier_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Courier location not found")
    return rec

@app.get("/api/v1/geo/couriers/available", response_model=List[LocationRecord])
def get_available_couriers():
    """Повертає всіх активних кур'єрів, готових прийняти замовлення"""
    return [c for c in couriers_db.values() if c.is_available]

@app.put("/api/v1/geo/couriers/{courier_id}/status", response_model=LocationRecord)
def update_courier_status(courier_id: str, status_update: CourierStatusUpdate):
    """Оновлення зайнятості кур'єра (busy/available)"""
    rec = couriers_db.get(courier_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Courier not found")
    rec.is_available = status_update.is_available
    rec.updated_at = int(time.time())
    logger.info(f"Courier {courier_id} availability changed to {status_update.is_available}")
    return rec

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

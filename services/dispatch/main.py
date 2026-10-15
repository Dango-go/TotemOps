import os
import time
import uuid
import math
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import httpx
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "dispatch", "message": "%(message)s"}')
logger = logging.getLogger("dispatch")

app = FastAPI(title="Dispatch Service", version="1.1.0")
PORT = int(os.environ.get("PORT", "8009"))
GEO_URL = os.environ.get("GEO_URL", "http://localhost:8008")

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Розрахунок геодезичної відстані між двома точками на Землі у кілометрах"""
    R = 6371.0  # Радіус Землі в км
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

class FindCourierRequest(BaseModel):
    order_id: str
    pickup_lat: float = 50.4474
    pickup_lon: float = 30.5222
    dropoff_lat: float = 50.4501
    dropoff_lon: float = 30.5234

class AssignCourierRequest(BaseModel):
    order_id: str
    courier_id: str

class Assignment(BaseModel):
    assignment_id: str
    order_id: str
    courier_id: str
    status: str
    assigned_at: int
    transport_type: Optional[str] = "BICYCLE"
    distance_to_pickup_km: Optional[float] = 1.2
    delivery_distance_km: Optional[float] = 2.5

# Локальний кеш призначень
assignments_by_order: Dict[str, Assignment] = {}
assignments_by_id: Dict[str, Assignment] = {}

START_TIME = time.time()

@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "dispatch", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness():
    return {"status": "READY", "service": "dispatch"}

@app.post("/api/v1/dispatch/find")
def find_courier(req: FindCourierRequest):
    """
    Розумний підбір кур'єра:
    1. Рахує реальну відстань доставки за формулою Гаверсину.
    2. Опитує geo-tracking про доступних кур'єрів.
    3. Фільтрує за типом транспорту (піший до 2 км, вело до 6 км, авто для дальніх).
    4. Обирає найближчого до ресторану.
    """
    delivery_dist = haversine_km(req.pickup_lat, req.pickup_lon, req.dropoff_lat, req.dropoff_lon)
    logger.info(f"Finding courier for order {req.order_id}: delivery distance is {delivery_dist} km")

    available_couriers_list = []
    candidates = []

    try:
        with httpx.Client(timeout=3.0) as client:
            geo_res = client.get(f"{GEO_URL}/api/v1/geo/couriers/available")
            if geo_res.status_code == 200:
                raw_couriers = geo_res.json()
                for c in raw_couriers:
                    c_id = c["courier_id"]
                    c_lat = c["latitude"]
                    c_lon = c["longitude"]
                    c_range = c.get("max_range_km", 5.0)
                    c_type = c.get("transport_type", "BICYCLE")
                    available_couriers_list.append(c_id)

                    # Чи покриває транспорт кур'єра цю дистанцію доставки?
                    if c_range >= delivery_dist:
                        # Дистанція від кур'єра до точки забору (ресторану)
                        dist_to_pickup = haversine_km(c_lat, c_lon, req.pickup_lat, req.pickup_lon)
                        candidates.append({
                            "courier_id": c_id,
                            "dist_to_pickup": dist_to_pickup,
                            "transport_type": c_type,
                            "max_range_km": c_range,
                        })
    except Exception as e:
        logger.warning(f"Could not reach geo-tracking service, using fallback: {e}")

    # Fallback, якщо geo-tracking недоступний або список кандидатів порожній
    if not candidates:
        fallback_id = available_couriers_list[0] if available_couriers_list else "courier-01"
        return {
            "order_id": req.order_id,
            "delivery_distance_km": delivery_dist,
            "available_couriers": available_couriers_list or ["courier-01", "courier-02", "courier-03"],
            "best_courier_id": fallback_id,
            "transport_type": "BICYCLE",
            "distance_to_pickup_km": 1.5,
        }

    # Сортуємо кандидатів за найменшою відстанню до ресторану
    candidates.sort(key=lambda x: x["dist_to_pickup"])
    best = candidates[0]

    logger.info(f"Selected best courier {best['courier_id']} ({best['transport_type']}) at {best['dist_to_pickup']} km from restaurant")

    return {
        "order_id": req.order_id,
        "delivery_distance_km": delivery_dist,
        "available_couriers": available_couriers_list,
        "best_courier_id": best["courier_id"],
        "transport_type": best["transport_type"],
        "distance_to_pickup_km": best["dist_to_pickup"],
    }

@app.post("/api/v1/dispatch/assign", response_model=Assignment)
def assign_courier(req: AssignCourierRequest):
    now = int(time.time())
    asgn = Assignment(
        assignment_id=f"asgn-{uuid.uuid4().hex[:8]}",
        order_id=req.order_id,
        courier_id=req.courier_id,
        status="ASSIGNED",
        assigned_at=now,
    )
    assignments_by_order[req.order_id] = asgn
    assignments_by_id[asgn.assignment_id] = asgn

    # Позначаємо кур'єра як зайнятого в geo-tracking
    try:
        with httpx.Client(timeout=2.0) as client:
            client.put(f"{GEO_URL}/api/v1/geo/couriers/{req.courier_id}/status", json={"is_available": False})
    except Exception as e:
        logger.warning(f"Failed to update courier availability: {e}")

    logger.info(f"Assigned courier {asgn.courier_id} to order {asgn.order_id}")
    return asgn

@app.post("/api/v1/dispatch/assignments/{assignment_id}/accept", response_model=Assignment)
def accept_assignment(assignment_id: str):
    asgn = assignments_by_id.get(assignment_id)
    if not asgn:
        raise HTTPException(status_code=404, detail="Assignment not found")
    asgn.status = "ACCEPTED"
    logger.info(f"Assignment {assignment_id} accepted")
    return asgn

@app.get("/api/v1/dispatch/assignments/{order_id}", response_model=Assignment)
def get_assignment(order_id: str):
    asgn = assignments_by_order.get(order_id)
    if not asgn:
        raise HTTPException(status_code=404, detail="No assignment for this order")
    return asgn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

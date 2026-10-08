import os
import time
import uuid
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "dispatch", "message": "%(message)s"}')
logger = logging.getLogger("dispatch")

app = FastAPI(title="Dispatch Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8009"))

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

available_couriers: List[str] = ["courier-01", "courier-02", "courier-03"]
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
    best = available_couriers[0] if available_couriers else None
    return {
        "order_id": req.order_id,
        "available_couriers": available_couriers,
        "best_courier_id": best,
    }

@app.post("/api/v1/dispatch/assign", response_model=Assignment)
def assign_courier(req: AssignCourierRequest):
    asgn = Assignment(
        assignment_id=f"asgn-{uuid.uuid4().hex[:8]}",
        order_id=req.order_id,
        courier_id=req.courier_id,
        status="ASSIGNED",
        assigned_at=int(time.time()),
    )
    assignments_by_order[req.order_id] = asgn
    assignments_by_id[asgn.assignment_id] = asgn
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

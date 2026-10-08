import os
import time
import logging
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
import httpx
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "bff-courier", "message": "%(message)s"}')
logger = logging.getLogger("bff-courier")

app = FastAPI(title="BFF Courier API", version="1.0.0")
PORT = int(os.environ.get("PORT", "8021"))

DISPATCH_URL = os.environ.get("DISPATCH_URL", "http://localhost:8009")
GEO_URL = os.environ.get("GEO_URL", "http://localhost:8008")
ORDER_URL = os.environ.get("ORDER_URL", "http://localhost:8014")

class AcceptAssignmentRequest(BaseModel):
    assignment_id: str
    courier_id: str

class MarkDeliveredRequest(BaseModel):
    order_id: str

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "bff-courier"}

@app.post("/api/v1/courier/assignments/accept")
def accept_assignment(req: AcceptAssignmentRequest):
    with httpx.Client(timeout=3.0) as client:
        res = client.post(f"{DISPATCH_URL}/api/v1/dispatch/assignments/{req.assignment_id}/accept")
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()

@app.post("/api/v1/courier/orders/delivered")
def mark_delivered(req: MarkDeliveredRequest):
    with httpx.Client(timeout=3.0) as client:
        res = client.put(f"{ORDER_URL}/api/v1/orders/{req.order_id}/status", json={"status": "DELIVERED"})
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()

@app.websocket("/ws/location")
async def websocket_location(websocket: WebSocket):
    await websocket.accept()
    logger.info("Courier connected via WebSocket")
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            while True:
                data = await websocket.receive_json()
                await client.post(f"{GEO_URL}/api/v1/geo/location", json={
                    "courier_id": data.get("courier_id", "courier-01"),
                    "latitude": data.get("latitude", 50.4501),
                    "longitude": data.get("longitude", 30.5234),
                    "speed_kmh": data.get("speed_kmh", 15.0),
                    "heading": data.get("heading", 90.0),
                })
                await websocket.send_json({"status": "ACK", "timestamp": int(time.time())})
        except WebSocketDisconnect:
            logger.info("Courier disconnected from WebSocket")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

import os
import time
import uuid
import logging
from typing import Dict, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "notification", "message": "%(message)s"}')
logger = logging.getLogger("notification")

app = FastAPI(title="Notification Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8011"))

class SendNotificationRequest(BaseModel):
    recipient_id: str
    channel: Optional[str] = "PUSH"
    title: str
    body: str

class NotificationRecord(BaseModel):
    notification_id: str
    recipient_id: str
    channel: str
    title: str
    body: str
    status: str
    timestamp: int

notifications: Dict[str, NotificationRecord] = {}

START_TIME = time.time()

@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "notification", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness():
    return {"status": "READY", "service": "notification"}

@app.post("/api/v1/notifications/send", response_model=NotificationRecord)
def send_notification(req: SendNotificationRequest):
    n_id = f"notif-{uuid.uuid4().hex[:8]}"
    n = NotificationRecord(
        notification_id=n_id,
        recipient_id=req.recipient_id,
        channel=req.channel or "PUSH",
        title=req.title,
        body=req.body,
        status="DELIVERED",
        timestamp=int(time.time()),
    )
    notifications[n_id] = n
    logger.info(f"Sent {n.channel} notification to {n.recipient_id}: '{n.title}'")
    return n

@app.get("/api/v1/notifications/{notification_id}", response_model=NotificationRecord)
def get_notification(notification_id: str):
    n = notifications.get(notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    return n

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

import os
import time
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "analytics-sink", "message": "%(message)s"}')
logger = logging.getLogger("analytics-sink")

app = FastAPI(title="Analytics Sink Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8013"))

class AnalyticsEvent(BaseModel):
    event_type: str
    source_service: str
    entity_id: str
    payload: Optional[dict] = None
    timestamp: Optional[int] = None

events_store: List[AnalyticsEvent] = []

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "analytics-sink"}

@app.post("/api/v1/analytics/events")
def ingest_event(event: AnalyticsEvent):
    if not event.timestamp:
        event.timestamp = int(time.time())
    events_store.append(event)
    logger.info(f"Ingested event: {event.event_type} from {event.source_service}")
    return {"accepted": True}

@app.post("/api/v1/analytics/events/batch")
def batch_ingest_events(events: List[AnalyticsEvent]):
    now = int(time.time())
    for e in events:
        if not e.timestamp:
            e.timestamp = now
        events_store.append(e)
    logger.info(f"Batch ingested {len(events)} events")
    return {"accepted_count": len(events)}

@app.get("/api/v1/analytics/events", response_model=List[AnalyticsEvent])
def list_events():
    return events_store

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

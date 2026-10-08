import os
import time
import json
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, Response, status
from sqlalchemy import create_engine, Column, String, Integer, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "analytics-sink", "message": "%(message)s"}')
logger = logging.getLogger("analytics-sink")

app = FastAPI(title="Analytics Sink Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8013"))
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./analytics.db")
START_TIME = time.time()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AnalyticsEventModel(Base):
    __tablename__ = "analytics_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, index=True, nullable=False)
    source_service = Column(String, index=True, nullable=False)
    entity_id = Column(String, index=True, nullable=False)
    payload_json = Column(Text, nullable=True)
    timestamp = Column(Integer, nullable=False)

Base.metadata.create_all(bind=engine)

class AnalyticsEvent(BaseModel):
    event_type: str
    source_service: str
    entity_id: str
    payload: Optional[dict] = None
    timestamp: Optional[int] = None

# Probes
@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "analytics-sink", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "READY", "service": "analytics-sink", "database": "CONNECTED"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "NOT_READY", "service": "analytics-sink", "database": "DISCONNECTED", "error": str(e)}

# API
@app.post("/api/v1/analytics/events")
def ingest_event(event: AnalyticsEvent):
    ts = event.timestamp or int(time.time())
    payload_str = json.dumps(event.payload) if event.payload else "{}"
    with SessionLocal() as db:
        rec = AnalyticsEventModel(
            event_type=event.event_type,
            source_service=event.source_service,
            entity_id=event.entity_id,
            payload_json=payload_str,
            timestamp=ts,
        )
        db.add(rec)
        db.commit()
    logger.info(f"Ingested event into DB: {event.event_type} from {event.source_service}")
    return {"accepted": True}

@app.post("/api/v1/analytics/events/batch")
def batch_ingest_events(events: List[AnalyticsEvent]):
    now = int(time.time())
    with SessionLocal() as db:
        for e in events:
            ts = e.timestamp or now
            payload_str = json.dumps(e.payload) if e.payload else "{}"
            db.add(AnalyticsEventModel(
                event_type=e.event_type,
                source_service=e.source_service,
                entity_id=e.entity_id,
                payload_json=payload_str,
                timestamp=ts,
            ))
        db.commit()
    logger.info(f"Batch ingested {len(events)} events into DB")
    return {"accepted_count": len(events)}

@app.get("/api/v1/analytics/events")
def list_events(limit: int = 50):
    with SessionLocal() as db:
        records = db.query(AnalyticsEventModel).order_by(AnalyticsEventModel.id.desc()).limit(limit).all()
        return [
            {
                "event_type": r.event_type,
                "source_service": r.source_service,
                "entity_id": r.entity_id,
                "payload": json.loads(r.payload_json) if r.payload_json else {},
                "timestamp": r.timestamp,
            }
            for r in records
        ]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

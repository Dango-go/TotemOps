import os
import time
import uuid
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Response, status
from sqlalchemy import create_engine, Column, String, Integer, text
from sqlalchemy.orm import declarative_base, sessionmaker
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "payment", "message": "%(message)s"}')
logger = logging.getLogger("payment")

app = FastAPI(title="Payment Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8006"))
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./payment.db")
START_TIME = time.time()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PaymentModel(Base):
    __tablename__ = "payments"
    payment_id = Column(String, primary_key=True, index=True)
    order_id = Column(String, index=True, nullable=False)
    customer_id = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String, default="UAH")
    status = Column(String, nullable=False)  # AUTHORIZED, CAPTURED, REFUNDED
    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(Integer, nullable=False)

Base.metadata.create_all(bind=engine)

class AuthorizePaymentRequest(BaseModel):
    order_id: str
    customer_id: str
    amount_cents: int
    currency: Optional[str] = "UAH"
    idempotency_key: Optional[str] = None
    payment_method: Optional[str] = "card"

class PaymentSchema(BaseModel):
    payment_id: str
    order_id: str
    customer_id: str
    amount_cents: int
    currency: str
    status: str
    idempotency_key: Optional[str] = None
    created_at: int

    class Config:
        from_attributes = True

# Probes
@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "payment", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "READY", "service": "payment", "database": "CONNECTED"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "NOT_READY", "service": "payment", "database": "DISCONNECTED", "error": str(e)}

# API
@app.post("/api/v1/payments/authorize", response_model=PaymentSchema)
def authorize_payment(req: AuthorizePaymentRequest):
    if req.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    with SessionLocal() as db:
        if req.idempotency_key:
            existing = db.query(PaymentModel).filter(PaymentModel.idempotency_key == req.idempotency_key).first()
            if existing:
                logger.info(f"Returning idempotent payment {existing.payment_id}")
                return existing

        p = PaymentModel(
            payment_id=f"pay-{uuid.uuid4().hex[:8]}",
            order_id=req.order_id,
            customer_id=req.customer_id,
            amount_cents=req.amount_cents,
            currency=req.currency or "UAH",
            status="AUTHORIZED",
            idempotency_key=req.idempotency_key,
            created_at=int(time.time()),
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        logger.info(f"Payment authorized in DB: {p.payment_id}, amount={p.amount_cents} cents")
        return p

@app.post("/api/v1/payments/{payment_id}/capture", response_model=PaymentSchema)
def capture_payment(payment_id: str):
    with SessionLocal() as db:
        p = db.query(PaymentModel).filter(PaymentModel.payment_id == payment_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Payment not found")
        if p.status != "AUTHORIZED":
            raise HTTPException(status_code=400, detail=f"Cannot capture payment with status {p.status}")

        p.status = "CAPTURED"
        db.commit()
        db.refresh(p)
        logger.info(f"Payment captured in DB: {payment_id}")
        return p

class ChargePaymentRequest(BaseModel):
    order_id: str
    customer_id: str
    amount_cents: int
    currency: Optional[str] = "UAH"
    payment_method: Optional[str] = "card"
    idempotency_key: Optional[str] = None

@app.post("/api/v1/payments/charge", response_model=PaymentSchema)
def charge_payment(req: ChargePaymentRequest):
    if req.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    with SessionLocal() as db:
        if req.idempotency_key:
            existing = db.query(PaymentModel).filter(PaymentModel.idempotency_key == req.idempotency_key).first()
            if existing:
                logger.info(f"Returning idempotent charge {existing.payment_id}")
                return existing

        p = PaymentModel(
            payment_id=f"pay-{uuid.uuid4().hex[:8]}",
            order_id=req.order_id,
            customer_id=req.customer_id,
            amount_cents=req.amount_cents,
            currency=req.currency or "UAH",
            status="CAPTURED",
            idempotency_key=req.idempotency_key,
            created_at=int(time.time()),
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        logger.info(f"Payment charged directly in DB: {p.payment_id}, amount={p.amount_cents} cents")
        return p


@app.post("/api/v1/payments/{payment_id}/refund", response_model=PaymentSchema)
def refund_payment(payment_id: str):
    with SessionLocal() as db:
        p = db.query(PaymentModel).filter(PaymentModel.payment_id == payment_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Payment not found")

        p.status = "REFUNDED"
        db.commit()
        db.refresh(p)
        logger.info(f"Payment refunded in DB: {payment_id}")
        return p

@app.get("/api/v1/payments/{payment_id}", response_model=PaymentSchema)
def get_payment(payment_id: str):
    with SessionLocal() as db:
        p = db.query(PaymentModel).filter(PaymentModel.payment_id == payment_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Payment not found")
        return p

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

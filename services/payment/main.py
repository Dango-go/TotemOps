import os
import time
import uuid
import logging
from typing import Dict, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "payment", "message": "%(message)s"}')
logger = logging.getLogger("payment")

app = FastAPI(title="Payment Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8006"))

class AuthorizePaymentRequest(BaseModel):
    order_id: str
    customer_id: str
    amount_cents: int
    currency: Optional[str] = "UAH"
    idempotency_key: Optional[str] = None
    payment_method: Optional[str] = "card"

class PaymentRecord(BaseModel):
    payment_id: str
    order_id: str
    customer_id: str
    amount_cents: int
    currency: str
    status: str
    idempotency_key: Optional[str] = None
    created_at: int

payments: Dict[str, PaymentRecord] = {}
idempotency_cache: Dict[str, PaymentRecord] = {}

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "payment"}

@app.post("/api/v1/payments/authorize", response_model=PaymentRecord)
def authorize_payment(req: AuthorizePaymentRequest):
    if req.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    if req.idempotency_key and req.idempotency_key in idempotency_cache:
        logger.info(f"Returning cached payment for idempotency_key {req.idempotency_key}")
        return idempotency_cache[req.idempotency_key]

    p = PaymentRecord(
        payment_id=f"pay-{uuid.uuid4().hex[:8]}",
        order_id=req.order_id,
        customer_id=req.customer_id,
        amount_cents=req.amount_cents,
        currency=req.currency or "UAH",
        status="AUTHORIZED",
        idempotency_key=req.idempotency_key,
        created_at=int(time.time()),
    )
    payments[p.payment_id] = p
    if req.idempotency_key:
        idempotency_cache[req.idempotency_key] = p

    logger.info(f"Payment authorized: {p.payment_id}, amount={p.amount_cents} cents")
    return p

@app.post("/api/v1/payments/{payment_id}/capture", response_model=PaymentRecord)
def capture_payment(payment_id: str):
    p = payments.get(payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    if p.status != "AUTHORIZED":
        raise HTTPException(status_code=400, detail=f"Cannot capture payment with status {p.status}")

    p.status = "CAPTURED"
    logger.info(f"Payment captured: {payment_id}")
    return p

@app.post("/api/v1/payments/{payment_id}/refund", response_model=PaymentRecord)
def refund_payment(payment_id: str):
    p = payments.get(payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")

    p.status = "REFUNDED"
    logger.info(f"Payment refunded: {payment_id}")
    return p

@app.get("/api/v1/payments/{payment_id}", response_model=PaymentRecord)
def get_payment(payment_id: str):
    p = payments.get(payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    return p

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

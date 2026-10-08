import os
import time
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "fraud", "message": "%(message)s"}')
logger = logging.getLogger("fraud")

app = FastAPI(title="Fraud Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8010"))

class RiskEvaluationRequest(BaseModel):
    user_id: str
    order_id: str
    amount_cents: int
    payment_method: Optional[str] = "card"
    ip_address: Optional[str] = "127.0.0.1"

class RiskEvaluationResponse(BaseModel):
    is_allowed: bool
    risk_score: float
    decision: str
    risk_factors: List[str]

START_TIME = time.time()

@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "fraud", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness():
    return {"status": "READY", "service": "fraud"}

@app.post("/api/v1/fraud/evaluate", response_model=RiskEvaluationResponse)
def evaluate_risk(req: RiskEvaluationRequest):
    risk_score = 0.05
    factors = []

    if req.amount_cents > 1000000:  # > 10,000 UAH
        risk_score += 0.4
        factors.append("HIGH_TRANSACTION_AMOUNT")

    if (req.payment_method or "").lower() in ("crypto", "unverified_card"):
        risk_score += 0.35
        factors.append("UNVERIFIED_PAYMENT_METHOD")

    if risk_score >= 0.7:
        decision = "REJECT"
        is_allowed = False
    elif risk_score >= 0.4:
        decision = "CHALLENGE"
        is_allowed = True
    else:
        decision = "ALLOW"
        is_allowed = True

    logger.info(f"Risk evaluation for order {req.order_id}: score={risk_score:.2f}, decision={decision}")
    return RiskEvaluationResponse(
        is_allowed=is_allowed,
        risk_score=risk_score,
        decision=decision,
        risk_factors=factors,
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

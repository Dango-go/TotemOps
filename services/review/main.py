import os
import time
import uuid
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Response, status
from sqlalchemy import create_engine, Column, String, Integer, text
from sqlalchemy.orm import declarative_base, sessionmaker
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "review", "message": "%(message)s"}')
logger = logging.getLogger("review")

app = FastAPI(title="Review Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8012"))
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./review.db")
START_TIME = time.time()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ReviewModel(Base):
    __tablename__ = "reviews"
    review_id = Column(String, primary_key=True, index=True)
    order_id = Column(String, index=True, nullable=False)
    user_id = Column(String, nullable=False)
    restaurant_id = Column(String, index=True, nullable=True)
    courier_id = Column(String, index=True, nullable=True)
    rating = Column(Integer, nullable=False)
    comment = Column(String, default="")
    created_at = Column(Integer, nullable=False)

Base.metadata.create_all(bind=engine)

class CreateReviewRequest(BaseModel):
    order_id: str
    user_id: str
    restaurant_id: Optional[str] = None
    courier_id: Optional[str] = None
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = ""

class ReviewSchema(BaseModel):
    review_id: str
    order_id: str
    user_id: str
    restaurant_id: Optional[str] = None
    courier_id: Optional[str] = None
    rating: int
    comment: str
    created_at: int

    class Config:
        from_attributes = True

class ReviewSummary(BaseModel):
    target_id: str
    average_rating: float
    total_reviews: int
    reviews: List[ReviewSchema]

# Probes
@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "review", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "READY", "service": "review", "database": "CONNECTED"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "NOT_READY", "service": "review", "database": "DISCONNECTED", "error": str(e)}

# API
@app.post("/api/v1/reviews", response_model=ReviewSchema)
def create_review(req: CreateReviewRequest):
    r_id = f"rev-{uuid.uuid4().hex[:8]}"
    r = ReviewModel(
        review_id=r_id,
        order_id=req.order_id,
        user_id=req.user_id,
        restaurant_id=req.restaurant_id,
        courier_id=req.courier_id,
        rating=req.rating,
        comment=req.comment or "",
        created_at=int(time.time()),
    )
    with SessionLocal() as db:
        db.add(r)
        db.commit()
        db.refresh(r)
    logger.info(f"Saved review {r_id} to DB, rating={r.rating}")
    return r

@app.get("/api/v1/reviews/restaurant/{restaurant_id}", response_model=ReviewSummary)
def get_restaurant_reviews(restaurant_id: str):
    with SessionLocal() as db:
        matched = db.query(ReviewModel).filter(ReviewModel.restaurant_id == restaurant_id).all()
        avg = sum(r.rating for r in matched) / len(matched) if matched else 5.0
        return ReviewSummary(
            target_id=restaurant_id,
            average_rating=round(avg, 2),
            total_reviews=len(matched),
            reviews=matched,
        )

@app.get("/api/v1/reviews/courier/{courier_id}", response_model=ReviewSummary)
def get_courier_reviews(courier_id: str):
    with SessionLocal() as db:
        matched = db.query(ReviewModel).filter(ReviewModel.courier_id == courier_id).all()
        avg = sum(r.rating for r in matched) / len(matched) if matched else 5.0
        return ReviewSummary(
            target_id=courier_id,
            average_rating=round(avg, 2),
            total_reviews=len(matched),
            reviews=matched,
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

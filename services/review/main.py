import os
import time
import uuid
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "review", "message": "%(message)s"}')
logger = logging.getLogger("review")

app = FastAPI(title="Review Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8012"))

class CreateReviewRequest(BaseModel):
    order_id: str
    user_id: str
    restaurant_id: Optional[str] = None
    courier_id: Optional[str] = None
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = ""

class Review(BaseModel):
    review_id: str
    order_id: str
    user_id: str
    restaurant_id: Optional[str]
    courier_id: Optional[str]
    rating: int
    comment: str
    created_at: int

class ReviewSummary(BaseModel):
    target_id: str
    average_rating: float
    total_reviews: int
    reviews: List[Review]

reviews_store: List[Review] = []

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "review"}

@app.post("/api/v1/reviews", response_model=Review)
def create_review(req: CreateReviewRequest):
    rev = Review(
        review_id=f"rev-{uuid.uuid4().hex[:8]}",
        order_id=req.order_id,
        user_id=req.user_id,
        restaurant_id=req.restaurant_id,
        courier_id=req.courier_id,
        rating=req.rating,
        comment=req.comment or "",
        created_at=int(time.time()),
    )
    reviews_store.append(rev)
    logger.info(f"Created review {rev.review_id} for order {rev.order_id}, rating={rev.rating}")
    return rev

@app.get("/api/v1/reviews/restaurant/{restaurant_id}", response_model=ReviewSummary)
def get_restaurant_reviews(restaurant_id: str):
    matched = [r for r in reviews_store if r.restaurant_id == restaurant_id]
    avg = sum(r.rating for r in matched) / len(matched) if matched else 5.0
    return ReviewSummary(
        target_id=restaurant_id,
        average_rating=round(avg, 2),
        total_reviews=len(matched),
        reviews=matched
    )

@app.get("/api/v1/reviews/courier/{courier_id}", response_model=ReviewSummary)
def get_courier_reviews(courier_id: str):
    matched = [r for r in reviews_store if r.courier_id == courier_id]
    avg = sum(r.rating for r in matched) / len(matched) if matched else 5.0
    return ReviewSummary(
        target_id=courier_id,
        average_rating=round(avg, 2),
        total_reviews=len(matched),
        reviews=matched
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

import os
import time
import uuid
import logging
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Response, status
from sqlalchemy import create_engine, Column, String, Integer, text
from sqlalchemy.orm import declarative_base, sessionmaker
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "inventory", "message": "%(message)s"}')
logger = logging.getLogger("inventory")

app = FastAPI(title="Inventory Service", version="1.0.0")
PORT = int(os.environ.get("PORT", "8005"))
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./inventory.db")
START_TIME = time.time()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class StockItemModel(Base):
    __tablename__ = "stock_items"
    item_id = Column(String, primary_key=True, index=True)
    quantity = Column(Integer, nullable=False, default=20)

class ReservationModel(Base):
    __tablename__ = "reservations"
    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, index=True, nullable=False)
    restaurant_id = Column(String, nullable=False)
    status = Column(String, nullable=False)  # RESERVED, COMMITTED, RELEASED
    created_at = Column(Integer, nullable=False)

class ReservationItemModel(Base):
    __tablename__ = "reservation_items"
    id = Column(String, primary_key=True)
    reservation_id = Column(String, index=True, nullable=False)
    item_id = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)

Base.metadata.create_all(bind=engine)

# Seed stock if empty
with SessionLocal() as db:
    if not db.query(StockItemModel).first():
        initial_stock = [
            StockItemModel(item_id="item-01", quantity=50),
            StockItemModel(item_id="item-02", quantity=100),
            StockItemModel(item_id="item-03", quantity=80),
            StockItemModel(item_id="item-04", quantity=40),
            StockItemModel(item_id="item-05", quantity=30),
            StockItemModel(item_id="item-06", quantity=25),
            StockItemModel(item_id="item-07", quantity=45),
            StockItemModel(item_id="item-08", quantity=60),
        ]
        db.add_all(initial_stock)
        db.commit()

class StockItem(BaseModel):
    item_id: str
    quantity: int

class CheckStockRequest(BaseModel):
    restaurant_id: str
    items: List[StockItem]

class ReserveStockRequest(BaseModel):
    order_id: str
    restaurant_id: str
    items: List[StockItem]

class StockActionRequest(BaseModel):
    reservation_id: str

# Probes
@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "inventory", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "READY", "service": "inventory", "database": "CONNECTED"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "NOT_READY", "service": "inventory", "database": "DISCONNECTED", "error": str(e)}

# API
@app.post("/api/v1/inventory/check")
def check_stock(req: CheckStockRequest):
    with SessionLocal() as db:
        out_of_stock = []
        for it in req.items:
            stock_record = db.query(StockItemModel).filter(StockItemModel.item_id == it.item_id).first()
            avail = stock_record.quantity if stock_record else 20
            if avail < it.quantity:
                out_of_stock.append(it.item_id)
        return {"in_stock": len(out_of_stock) == 0, "out_of_stock_item_ids": out_of_stock}

@app.post("/api/v1/inventory/reserve")
def reserve_stock(req: ReserveStockRequest):
    with SessionLocal() as db:
        # Check all items first
        for it in req.items:
            stock_record = db.query(StockItemModel).filter(StockItemModel.item_id == it.item_id).first()
            avail = stock_record.quantity if stock_record else 20
            if avail < it.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for item {it.item_id}")

        res_id = f"res-{uuid.uuid4().hex[:8]}"
        res = ReservationModel(
            id=res_id,
            order_id=req.order_id,
            restaurant_id=req.restaurant_id,
            status="RESERVED",
            created_at=int(time.time()),
        )
        db.add(res)

        for it in req.items:
            stock_record = db.query(StockItemModel).filter(StockItemModel.item_id == it.item_id).first()
            if not stock_record:
                stock_record = StockItemModel(item_id=it.item_id, quantity=20)
                db.add(stock_record)
            stock_record.quantity -= it.quantity

            db.add(ReservationItemModel(
                id=f"ri-{uuid.uuid4().hex[:8]}",
                reservation_id=res_id,
                item_id=it.item_id,
                quantity=it.quantity,
            ))

        db.commit()
        logger.info(f"Reserved stock in DB for order {req.order_id}, reservation_id={res_id}")
        return {"success": True, "reservation_id": res_id}

@app.post("/api/v1/inventory/release")
def release_stock(req: StockActionRequest):
    with SessionLocal() as db:
        res = db.query(ReservationModel).filter(ReservationModel.id == req.reservation_id).first()
        if res and res.status == "RESERVED":
            items = db.query(ReservationItemModel).filter(ReservationItemModel.reservation_id == req.reservation_id).all()
            for it in items:
                stock_record = db.query(StockItemModel).filter(StockItemModel.item_id == it.item_id).first()
                if stock_record:
                    stock_record.quantity += it.quantity
            res.status = "RELEASED"
            db.commit()
            logger.info(f"Released reservation {req.reservation_id} in DB")
    return {"success": True}

@app.post("/api/v1/inventory/commit")
def commit_stock(req: StockActionRequest):
    with SessionLocal() as db:
        res = db.query(ReservationModel).filter(ReservationModel.id == req.reservation_id).first()
        if res:
            res.status = "COMMITTED"
            db.commit()
            logger.info(f"Committed reservation {req.reservation_id} in DB")
    return {"success": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

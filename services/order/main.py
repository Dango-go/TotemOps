import os
import time
import uuid
import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Response, status
from sqlalchemy import create_engine, Column, String, Integer, Float, text
from sqlalchemy.orm import declarative_base, sessionmaker
import httpx
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "order", "message": "%(message)s"}')
logger = logging.getLogger("order")

app = FastAPI(title="Order Service", version="1.1.0")
PORT = int(os.environ.get("PORT", "8014"))
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./order.db")
START_TIME = time.time()

# Downstream URLs
PRICING_URL = os.environ.get("PRICING_URL", "http://localhost:8003")
FRAUD_URL = os.environ.get("FRAUD_URL", "http://localhost:8010")
INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://localhost:8005")
PAYMENT_URL = os.environ.get("PAYMENT_URL", "http://localhost:8006")
DISPATCH_URL = os.environ.get("DISPATCH_URL", "http://localhost:8009")
NOTIFICATION_URL = os.environ.get("NOTIFICATION_URL", "http://localhost:8011")
ANALYTICS_URL = os.environ.get("ANALYTICS_URL", "http://localhost:8013")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class OrderModel(Base):
    __tablename__ = "orders"
    order_id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, index=True, nullable=False)
    restaurant_id = Column(String, nullable=False)
    subtotal_cents = Column(Integer, nullable=False)
    delivery_fee_cents = Column(Integer, nullable=False)
    discount_cents = Column(Integer, default=0)
    total_cents = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="PAID")
    delivery_address = Column(String, nullable=False)
    delivery_lat = Column(Float, nullable=False)
    delivery_lon = Column(Float, nullable=False)
    courier_id = Column(String, nullable=True)
    cancellation_reason = Column(String, nullable=True)
    refund_amount_cents = Column(Integer, default=0)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)

class OrderItemModel(Base):
    __tablename__ = "order_items"
    id = Column(String, primary_key=True)
    order_id = Column(String, index=True, nullable=False)
    item_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)

Base.metadata.create_all(bind=engine)

ALLOWED_TRANSITIONS = {
    "CREATED": ["PAID", "CANCELLED"],
    "PAID": ["ACCEPTED", "COOKING", "READY_FOR_PICKUP", "CANCELLED"],
    "ACCEPTED": ["COOKING", "READY_FOR_PICKUP", "CANCELLED"],
    "COOKING": ["READY_FOR_PICKUP", "CANCELLED"],
    "READY_FOR_PICKUP": ["PICKED_UP"],
    "PICKED_UP": ["DELIVERED"],
    "DELIVERED": [],
    "CANCELLED": []
}

class OrderItem(BaseModel):
    item_id: str
    name: str
    quantity: int
    price_cents: int

    class Config:
        from_attributes = True

class CreateOrderRequest(BaseModel):
    customer_id: str
    restaurant_id: str
    items: List[OrderItem]
    delivery_address: str
    delivery_lat: Optional[float] = 50.4501
    delivery_lon: Optional[float] = 30.5234
    promo_code: Optional[str] = ""
    payment_method: Optional[str] = "card"
    idempotency_key: Optional[str] = None

class UpdateOrderStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = ""

class CancelOrderRequest(BaseModel):
    reason: Optional[str] = "Customer requested cancellation"

class CancelOrderResponse(BaseModel):
    order_id: str
    status: str
    refund_amount_cents: int
    refund_percentage: int
    reason: str

class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    restaurant_id: str
    items: List[OrderItem]
    subtotal_cents: int
    delivery_fee_cents: int
    discount_cents: int
    total_cents: int
    status: str
    delivery_address: str
    delivery_lat: float
    delivery_lon: float
    courier_id: Optional[str] = None
    cancellation_reason: Optional[str] = None
    refund_amount_cents: Optional[int] = 0
    created_at: int
    updated_at: int

    class Config:
        from_attributes = True

# Probes
@app.get("/healthz")
def liveness():
    return {"status": "SERVING", "service": "order", "uptime_seconds": int(time.time() - START_TIME)}

@app.get("/readyz")
def readiness(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "READY", "service": "order", "database": "CONNECTED"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "NOT_READY", "service": "order", "database": "DISCONNECTED", "error": str(e)}

# API
@app.post("/api/v1/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(req: CreateOrderRequest):
    order_id = f"ord-{uuid.uuid4().hex[:8]}"
    logger.info(f"Orchestrating order creation: {order_id} for customer {req.customer_id}")

    with httpx.Client(timeout=4.0) as client:
        # 1. Pricing
        subtotal = sum(it.quantity * it.price_cents for it in req.items)
        delivery_fee = 6500
        discount = 0
        total = subtotal + delivery_fee
        try:
            p_res = client.post(f"{PRICING_URL}/api/v1/pricing/calculate", json={
                "restaurant_id": req.restaurant_id,
                "items": [{"item_id": it.item_id, "quantity": it.quantity, "unit_price_cents": it.price_cents} for it in req.items],
                "promo_code": req.promo_code,
                "distance_km": 3.5,
            })
            if p_res.status_code == 200:
                p_data = p_res.json()
                subtotal = p_data["subtotal_cents"]
                delivery_fee = p_data["delivery_fee_cents"]
                discount = p_data["discount_cents"]
                total = p_data["total_cents"]
        except Exception as e:
            logger.warning(f"Pricing service fallback: {e}")

        # 2. Fraud check
        try:
            f_res = client.post(f"{FRAUD_URL}/api/v1/fraud/evaluate", json={
                "user_id": req.customer_id,
                "order_id": order_id,
                "amount_cents": total,
                "payment_method": req.payment_method or "card",
                "ip_address": "127.0.0.1",
            })
            if f_res.status_code == 200 and f_res.json().get("decision") == "REJECT":
                raise HTTPException(status_code=400, detail="Order rejected by fraud detection")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Fraud service fallback: {e}")

        # 3. Reserve inventory
        try:
            inv_res = client.post(f"{INVENTORY_URL}/api/v1/inventory/reserve", json={
                "order_id": order_id,
                "restaurant_id": req.restaurant_id,
                "items": [{"item_id": it.item_id, "quantity": it.quantity} for it in req.items],
            })
            if inv_res.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Inventory reservation failed: {inv_res.text}")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Inventory service fallback: {e}")


        # 4. Process Payment
        try:
            pay_res = client.post(f"{PAYMENT_URL}/api/v1/payments/charge", json={
                "order_id": order_id,
                "customer_id": req.customer_id,
                "amount_cents": total,
                "payment_method": req.payment_method or "card",
            })
            if pay_res.status_code not in (200, 201):
                raise HTTPException(status_code=400, detail="Payment processing failed")
            logger.info(f"Payment authorized for order {order_id}")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Payment service fallback: {e}")

        # 5. Dispatch Courier with smart matching
        courier_id = "courier-01"
        try:
            disp_res = client.post(f"{DISPATCH_URL}/api/v1/dispatch/find", json={
                "order_id": order_id,
                "pickup_lat": 50.4474,
                "pickup_lon": 30.5222,
                "dropoff_lat": req.delivery_lat or 50.4501,
                "dropoff_lon": req.delivery_lon or 30.5234,
            })
            if disp_res.status_code == 200:
                best = disp_res.json().get("best_courier_id")
                if best:
                    courier_id = best
                    client.post(f"{DISPATCH_URL}/api/v1/dispatch/assign", json={
                        "order_id": order_id,
                        "courier_id": courier_id,
                    })
        except Exception as e:
            logger.warning(f"Dispatch service fallback: {e}")

        # 6. Notification
        try:
            client.post(f"{NOTIFICATION_URL}/api/v1/notifications/send", json={
                "recipient_id": req.customer_id,
                "channel": "PUSH",
                "title": "Order Placed Successfully",
                "body": f"Your order {order_id} has been confirmed!",
            })
        except Exception as e:
            logger.warning(f"Notification service fallback: {e}")

        # 7. Analytics Sink
        try:
            client.post(f"{ANALYTICS_URL}/api/v1/analytics/events", json={
                "event_type": "order.created",
                "source_service": "order",
                "entity_id": order_id,
                "payload": {"total_cents": total, "customer_id": req.customer_id},
            })
        except Exception as e:
            logger.warning(f"Analytics sink fallback: {e}")

    now = int(time.time())
    with SessionLocal() as db:
        order_model = OrderModel(
            order_id=order_id,
            customer_id=req.customer_id,
            restaurant_id=req.restaurant_id,
            subtotal_cents=subtotal,
            delivery_fee_cents=delivery_fee,
            discount_cents=discount,
            total_cents=total,
            status="PAID",
            delivery_address=req.delivery_address,
            delivery_lat=req.delivery_lat or 50.4501,
            delivery_lon=req.delivery_lon or 30.5234,
            courier_id=courier_id,
            cancellation_reason=None,
            refund_amount_cents=0,
            created_at=now,
            updated_at=now,
        )
        db.add(order_model)

        for it in req.items:
            db.add(OrderItemModel(
                id=f"oi-{uuid.uuid4().hex[:8]}",
                order_id=order_id,
                item_id=it.item_id,
                name=it.name,
                quantity=it.quantity,
                price_cents=it.price_cents,
            ))
        db.commit()

    return OrderResponse(
        order_id=order_id,
        customer_id=req.customer_id,
        restaurant_id=req.restaurant_id,
        items=req.items,
        subtotal_cents=subtotal,
        delivery_fee_cents=delivery_fee,
        discount_cents=discount,
        total_cents=total,
        status="PAID",
        delivery_address=req.delivery_address,
        delivery_lat=req.delivery_lat or 50.4501,
        delivery_lon=req.delivery_lon or 30.5234,
        courier_id=courier_id,
        cancellation_reason=None,
        refund_amount_cents=0,
        created_at=now,
        updated_at=now,
    )

@app.get("/api/v1/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str):
    with SessionLocal() as db:
        o = db.query(OrderModel).filter(OrderModel.order_id == order_id).first()
        if not o:
            raise HTTPException(status_code=404, detail="Order not found")
        items = db.query(OrderItemModel).filter(OrderItemModel.order_id == order_id).all()
        return OrderResponse(
            order_id=o.order_id,
            customer_id=o.customer_id,
            restaurant_id=o.restaurant_id,
            items=[OrderItem(item_id=it.item_id, name=it.name, quantity=it.quantity, price_cents=it.price_cents) for it in items],
            subtotal_cents=o.subtotal_cents,
            delivery_fee_cents=o.delivery_fee_cents,
            discount_cents=o.discount_cents,
            total_cents=o.total_cents,
            status=o.status,
            delivery_address=o.delivery_address,
            delivery_lat=o.delivery_lat,
            delivery_lon=o.delivery_lon,
            courier_id=o.courier_id,
            cancellation_reason=o.cancellation_reason,
            refund_amount_cents=o.refund_amount_cents,
            created_at=o.created_at,
            updated_at=o.updated_at,
        )

@app.put("/api/v1/orders/{order_id}/status", response_model=OrderResponse)
def update_order_status(order_id: str, req: UpdateOrderStatusRequest):
    with SessionLocal() as db:
        o = db.query(OrderModel).filter(OrderModel.order_id == order_id).first()
        if not o:
            raise HTTPException(status_code=404, detail="Order not found")
        
        target_status = req.status.upper()
        allowed = ALLOWED_TRANSITIONS.get(o.status, [])
        if target_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid state transition: cannot move order from '{o.status}' to '{target_status}'. Allowed: {allowed}"
            )

        o.status = target_status
        o.updated_at = int(time.time())
        db.commit()
        db.refresh(o)

        items = db.query(OrderItemModel).filter(OrderItemModel.order_id == order_id).all()
        logger.info(f"Order {order_id} status updated in DB to {target_status}")
        return OrderResponse(
            order_id=o.order_id,
            customer_id=o.customer_id,
            restaurant_id=o.restaurant_id,
            items=[OrderItem(item_id=it.item_id, name=it.name, quantity=it.quantity, price_cents=it.price_cents) for it in items],
            subtotal_cents=o.subtotal_cents,
            delivery_fee_cents=o.delivery_fee_cents,
            discount_cents=o.discount_cents,
            total_cents=o.total_cents,
            status=o.status,
            delivery_address=o.delivery_address,
            delivery_lat=o.delivery_lat,
            delivery_lon=o.delivery_lon,
            courier_id=o.courier_id,
            cancellation_reason=o.cancellation_reason,
            refund_amount_cents=o.refund_amount_cents,
            created_at=o.created_at,
            updated_at=o.updated_at,
        )

@app.post("/api/v1/orders/{order_id}/cancel", response_model=CancelOrderResponse)
def cancel_order(order_id: str, req: CancelOrderRequest):
    """
    Бізнес-правила скасування замовлення та повернення коштів:
    - Якщо PAID або ACCEPTED: 100% повернення (кухня ще не витратила інгредієнти).
    - Якщо COOKING: 50% повернення (50% утримує ресторан за зіпсовані продукти).
    - Якщо READY_FOR_PICKUP, PICKED_UP або DELIVERED: скасування заборонено.
    """
    with SessionLocal() as db:
        o = db.query(OrderModel).filter(OrderModel.order_id == order_id).first()
        if not o:
            raise HTTPException(status_code=404, detail="Order not found")

        if o.status in ["CANCELLED", "DELIVERED"]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel order in status '{o.status}'")

        if o.status in ["READY_FOR_PICKUP", "PICKED_UP"]:
            raise HTTPException(status_code=400, detail="Cannot cancel order: food is already prepared or courier is on the way")

        # Розрахунок повернення коштів
        if o.status in ["CREATED", "PAID", "ACCEPTED"]:
            refund_pct = 100
            refund_cents = o.total_cents
        elif o.status == "COOKING":
            refund_pct = 50
            refund_cents = int(o.total_cents * 0.5)
        else:
            refund_pct = 0
            refund_cents = 0

        o.status = "CANCELLED"
        o.cancellation_reason = req.reason or "Customer cancellation"
        o.refund_amount_cents = refund_cents
        o.updated_at = int(time.time())
        db.commit()

        # Звільняємо кур'єра, якщо він уже був призначений
        if o.courier_id:
            try:
                with httpx.Client(timeout=2.0) as client:
                    client.put(f"http://localhost:8008/api/v1/geo/couriers/{o.courier_id}/status", json={"is_available": True})
            except Exception as e:
                logger.warning(f"Failed to free courier on order cancel: {e}")

        # Відправляємо пуш клієнту про скасування
        try:
            with httpx.Client(timeout=2.0) as client:
                client.post(f"{NOTIFICATION_URL}/api/v1/notifications/send", json={
                    "recipient_id": o.customer_id,
                    "channel": "PUSH",
                    "title": "Замовлення скасовано",
                    "body": f"Ваше замовлення {order_id} скасовано. Повернено: {refund_cents / 100:.2f} грн ({refund_pct}%)",
                })
        except Exception as e:
            logger.warning(f"Failed to send cancellation notification: {e}")

        logger.info(f"Order {order_id} cancelled with {refund_pct}% refund ({refund_cents} cents)")
        return CancelOrderResponse(
            order_id=order_id,
            status="CANCELLED",
            refund_amount_cents=refund_cents,
            refund_percentage=refund_pct,
            reason=o.cancellation_reason,
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

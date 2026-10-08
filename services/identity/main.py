import os
import time
import uuid
import logging
import bcrypt
import jwt
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, status, Response
from sqlalchemy import create_engine, Column, String, Integer, text
from sqlalchemy.orm import declarative_base, sessionmaker
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "identity", "message": "%(message)s"}')
logger = logging.getLogger("identity")

app = FastAPI(title="Identity Service", version="1.0.0")

PORT = int(os.environ.get("PORT", "8001"))
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-2026")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./identity.db")

START_TIME = time.time()

# Database Setup
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserModel(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="customer")
    created_at = Column(Integer, nullable=False)

Base.metadata.create_all(bind=engine)

def hash_password(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def check_password(pwd: str, hashed: str) -> bool:
    return bcrypt.checkpw(pwd.encode("utf-8"), hashed.encode("utf-8"))

# Seed test accounts if empty
with SessionLocal() as db:
    for email, pwd, name, role in [
        ("customer@totem.ops", "password123", "Alice Customer", "customer"),
        ("courier@totem.ops", "password123", "Bob Courier", "courier"),
        ("merchant@totem.ops", "password123", "Charlie Merchant", "merchant"),
    ]:
        if not db.query(UserModel).filter(UserModel.email == email).first():
            db.add(UserModel(
                id=f"usr-{uuid.uuid4().hex[:8]}",
                email=email,
                password_hash=hash_password(pwd),
                full_name=name,
                role=role,
                created_at=int(time.time()),
            ))
    db.commit()

# Schemas
class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: Optional[str] = "customer"

class LoginRequest(BaseModel):
    email: str
    password: str

class VerifyTokenRequest(BaseModel):
    token: str

# Probes
@app.get("/healthz")
def liveness():
    return {
        "status": "SERVING",
        "service": "identity",
        "uptime_seconds": int(time.time() - START_TIME)
    }

@app.get("/readyz")
def readiness(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "READY", "service": "identity", "database": "CONNECTED"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "NOT_READY", "service": "identity", "database": "DISCONNECTED", "error": str(e)}

# API
@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    with SessionLocal() as db:
        if db.query(UserModel).filter(UserModel.email == req.email).first():
            raise HTTPException(status_code=400, detail="User already exists")

        user_id = f"usr-{uuid.uuid4().hex[:8]}"
        u = UserModel(
            id=user_id,
            email=req.email,
            password_hash=hash_password(req.password),
            full_name=req.full_name,
            role=req.role or "customer",
            created_at=int(time.time()),
        )
        db.add(u)
        db.commit()
        logger.info(f"Registered user in DB: {u.email} ({u.role})")
        return {"user_id": u.id, "email": u.email, "role": u.role}

@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    with SessionLocal() as db:
        u = db.query(UserModel).filter(UserModel.email == req.email).first()
        if not u or not check_password(req.password, u.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        payload = {
            "sub": u.id,
            "email": u.email,
            "role": u.role,
            "exp": int(time.time()) + 86400,
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        logger.info(f"User logged in from DB: {u.email}")
        return {
            "access_token": token,
            "token_type": "Bearer",
            "user_id": u.id,
            "role": u.role,
        }

@app.post("/api/v1/auth/verify")
def verify(req: VerifyTokenRequest):
    try:
        payload = jwt.decode(req.token, JWT_SECRET, algorithms=["HS256"])
        return {
            "valid": True,
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role"),
        }
    except Exception:
        return {"valid": False}

@app.get("/api/v1/users/{user_id}")
def get_user(user_id: str):
    with SessionLocal() as db:
        u = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "user_id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "created_at": u.created_at,
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

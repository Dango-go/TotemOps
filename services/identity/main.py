import os
import time
import uuid
import logging
import bcrypt
import jwt
from typing import Optional, Dict
from pydantic import BaseModel, EmailStr
from fastapi import FastAPI, HTTPException, status
import uvicorn

logging.basicConfig(level=logging.INFO, format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "identity", "message": "%(message)s"}')
logger = logging.getLogger("identity")

app = FastAPI(title="Identity Service", version="1.0.0")

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-2026")
PORT = int(os.environ.get("PORT", "8001"))

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

class UserRecord(BaseModel):
    user_id: str
    email: str
    password_hash: str
    full_name: str
    role: str
    created_at: int

# In-memory storage
users_by_email: Dict[str, UserRecord] = {}
users_by_id: Dict[str, UserRecord] = {}

def hash_password(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def check_password(pwd: str, hashed: str) -> bool:
    return bcrypt.checkpw(pwd.encode("utf-8"), hashed.encode("utf-8"))

# Pre-seed default test accounts
for email, pwd, name, role in [
    ("customer@totem.ops", "password123", "Alice Customer", "customer"),
    ("courier@totem.ops", "password123", "Bob Courier", "courier"),
    ("merchant@totem.ops", "password123", "Charlie Merchant", "merchant"),
]:
    u_id = f"usr-{uuid.uuid4().hex[:8]}"
    u = UserRecord(
        user_id=u_id,
        email=email,
        password_hash=hash_password(pwd),
        full_name=name,
        role=role,
        created_at=int(time.time()),
    )
    users_by_email[email] = u
    users_by_id[u_id] = u

@app.get("/healthz")
def healthz():
    return {"status": "SERVING", "service": "identity"}

@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    if req.email in users_by_email:
        raise HTTPException(status_code=400, detail="User already exists")

    u_id = f"usr-{uuid.uuid4().hex[:8]}"
    u = UserRecord(
        user_id=u_id,
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role=req.role or "customer",
        created_at=int(time.time()),
    )
    users_by_email[u.email] = u
    users_by_id[u_id] = u
    logger.info(f"Registered user: {u.email} ({u.role})")
    return {"user_id": u.user_id, "email": u.email, "role": u.role}

@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    u = users_by_email.get(req.email)
    if not u or not check_password(req.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    payload = {
        "sub": u.user_id,
        "email": u.email,
        "role": u.role,
        "exp": int(time.time()) + 86400,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    logger.info(f"User logged in: {u.email}")
    return {
        "access_token": token,
        "token_type": "Bearer",
        "user_id": u.user_id,
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
    u = users_by_id.get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": u.user_id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "created_at": u.created_at,
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

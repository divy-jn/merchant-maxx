from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import hashlib
import uuid
import time

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple in-memory user store (swap with Supabase later for production)
users_db = {}
sessions_db = {}

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "customer"  # "customer" or "merchant"

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    session_id: str
    user_id: str
    name: str
    email: str
    role: str

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    """Register a new user (customer or merchant)"""
    if req.email in users_db:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    user_id = str(uuid.uuid4())[:8]
    users_db[req.email] = {
        "user_id": user_id,
        "name": req.name,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "role": req.role,
        "created_at": time.time()
    }
    
    session_id = str(uuid.uuid4())
    sessions_db[session_id] = {"user_id": user_id, "email": req.email, "role": req.role, "name": req.name}
    
    return AuthResponse(session_id=session_id, user_id=user_id, name=req.name, email=req.email, role=req.role)

@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Login and get a session ID"""
    user = users_db.get(req.email)
    if not user or user["password_hash"] != hash_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    session_id = str(uuid.uuid4())
    sessions_db[session_id] = {
        "user_id": user["user_id"], 
        "email": user["email"], 
        "role": user["role"], 
        "name": user["name"]
    }
    
    return AuthResponse(
        session_id=session_id, user_id=user["user_id"], 
        name=user["name"], email=user["email"], role=user["role"]
    )

@router.get("/me")
async def get_me(session_id: str):
    """Get current user info from session"""
    session = sessions_db.get(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session

def get_user_from_session(session_id: str) -> Optional[dict]:
    """Helper used by other routes to validate session"""
    return sessions_db.get(session_id)

# Seed a demo user on import
demo_id = str(uuid.uuid4())[:8]
users_db["demo@merchantmaxx.com"] = {
    "user_id": demo_id,
    "name": "Demo Customer",
    "email": "demo@merchantmaxx.com",
    "password_hash": hash_password("demo123"),
    "role": "customer",
    "created_at": time.time()
}

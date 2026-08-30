from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
import bcrypt
import jwt
from datetime import datetime, timedelta
from config import settings
from utils.supabase_client import supabase
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "customer"

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    token: str
    user_id: str
    name: str
    email: str
    role: str

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")
    return encoded_jwt

@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest):
    """Register a new user (customer or merchant)"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    # Check if user exists
    existing = supabase.table("users").select("id").eq("email", req.email).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    user_data = {
        "name": req.name,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "role": req.role
    }
    
    res = supabase.table("users").insert(user_data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create user")
        
    user = res.data[0]
    
    token = create_access_token({
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "name": user["name"]
    })
    
    return AuthResponse(
        token=token, 
        user_id=user["id"], 
        name=user["name"], 
        email=user["email"], 
        role=user["role"]
    )

@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    """Login and get a JWT token"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    res = supabase.table("users").select("*").eq("email", req.email).execute()
    if not res.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    user = res.data[0]
    
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token({
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "name": user["name"]
    })
    
    return AuthResponse(
        token=token, 
        user_id=user["id"], 
        name=user["name"], 
        email=user["email"], 
        role=user["role"]
    )

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info from JWT"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid or missing session token")
    return current_user

def get_user_from_session(token: str) -> Optional[dict]:
    """Helper used by other routes to validate session token manually if needed"""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except:
        return None

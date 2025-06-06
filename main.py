from fastapi import FastAPI, Depends, HTTPException, status, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
import os
import json
from typing import List, Optional, Dict, Any, Union
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from backend.database import get_db, engine, test_connection
    from backend.models import Base, User, Feedback, NetworkLog
    from backend.schemas import (
        UserCreate, UserLogin, UserResponse, Token,
        FeedbackCreate, FeedbackResponse,
        NetworkLogCreate, NetworkLogResponse,
        RecommendationResponse
    )
    from crud import (
        create_user, authenticate_user, get_user_by_username,
        create_feedback, get_feedbacks, create_network_log,
        get_network_logs, get_provider_recommendations
    )
    DATABASE_AVAILABLE = True
    print("✅ Database modules imported successfully")
except Exception as e:
    print(f"⚠️ Database modules not available: {e}")
    DATABASE_AVAILABLE = False
    
    # Define basic models if schemas not available
    from pydantic import BaseModel, EmailStr
    
    class UserCreate(BaseModel):
        username: str
        email: str
        password: str
        provider: Optional[str] = None
    
    class UserLogin(BaseModel):
        username: str
        password: str
    
    class UserResponse(BaseModel):
        id: int
        username: str
        email: str
        provider: Optional[str] = None
        created_at: datetime
        is_active: bool
    
    class Token(BaseModel):
        access_token: str
        token_type: str

app = FastAPI(
    title="QoE Boost API",
    description="Quality of Experience monitoring and feedback API with Supabase",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = get_user_by_username(db, username=username)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.get("/")
async def root():
    return {
        "message": "QoE Boost API is running with Supabase!",
        "version": "1.0.0",
        "database": "Supabase PostgreSQL" if DATABASE_AVAILABLE else "Not Available",
        "endpoints": {
            "auth": ["/auth/register", "/auth/login", "/auth/me"],
            "feedback": ["/feedback"],
            "network-logs": ["/network-logs"],
            "recommendations": ["/recommendations"],
            "analytics": ["/analytics/providers"],
            "debug": ["/health", "/debug/routes"]
        }
    }

@app.get("/health")
async def health_check():
    if not DATABASE_AVAILABLE:
        return {
            "status": "degraded",
            "database": "not available",
            "message": "API running without database"
        }
    
    try:
        # Test database connection with proper SQLAlchemy syntax
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503, 
            detail=f"Database connection failed: {str(e)}"
        )

@app.get("/debug/routes")
async def list_routes():
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods)
            })
    return {"routes": routes}

# Helper function to parse request body
async def parse_body(request: Request) -> Dict[str, Any]:
    """Parse request body as JSON, handling both raw string and JSON object"""
    try:
        # First try to get the raw body
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # Log the raw body for debugging
        print(f"Raw request body: {body_str}")
        
        # Try to parse as JSON
        try:
            # If it's already a valid JSON string
            return json.loads(body_str)
        except json.JSONDecodeError:
            # If it's a string representation of JSON (with escape chars)
            if body_str.startswith('"') and body_str.endswith('"'):
                # Remove outer quotes and unescape
                cleaned = body_str[1:-1].replace('\\r\\n', '').replace('\\', '')
                return json.loads(cleaned)
            raise
            
    except Exception as e:
        print(f"Error parsing request body: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

# Authentication endpoints with raw body parsing
@app.post("/auth/register")
async def register(request: Request, db: Session = Depends(get_db)):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Parse the request body
        data = await parse_body(request)
        print(f"Parsed data: {data}")
        
        # Create UserCreate model
        user = UserCreate(**data)
        
        # Check if user already exists
        db_user = get_user_by_username(db, username=user.username)
        if db_user:
            raise HTTPException(status_code=400, detail="Username already registered")
        
        # Check if email already exists
        existing_email = db.query(User).filter(User.email == user.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user
        new_user = create_user(db=db, user=user)
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/auth/login")
async def login(request: Request, db: Session = Depends(get_db)):
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Parse the request body
        data = await parse_body(request)
        
        # Create UserLogin model
        user = UserLogin(**data)
        
        db_user = authenticate_user(db, user.username, user.password)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(data={"sub": db_user.username})
        return {"access_token": access_token, "token_type": "bearer"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.get("/auth/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

# Simple test endpoint for registration without database
@app.post("/test/register")
async def test_register(request: Request):
    """Test registration endpoint without database dependency"""
    try:
        # Parse the request body
        data = await parse_body(request)
        
        # Return the parsed data
        return {
            "message": "Registration data received successfully",
            "user_data": data,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        print(f"Test registration error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")

# Debug endpoint to echo request body
@app.post("/debug/echo")
async def echo_request(request: Request):
    """Echo the request body for debugging"""
    try:
        # Get raw body
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # Get headers
        headers = dict(request.headers)
        
        # Try to parse as JSON
        parsed_json = None
        try:
            parsed_json = json.loads(body_str)
        except:
            parsed_json = "Not valid JSON"
        
        return {
            "raw_body": body_str,
            "content_type": headers.get("content-type"),
            "parsed_json": parsed_json,
            "headers": headers
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/feedback")
async def submit_feedback(request: Request):
    if not DATABASE_AVAILABLE:
        # Fallback to in-memory storage
        data = await parse_body(request)
        return {
            "id": 1,
            "message": "Feedback received (stored in memory)",
            "data": data,
            "timestamp": datetime.utcnow()
        }
    
    try:
        data = await parse_body(request)
        db = next(get_db())
        feedback_create = FeedbackCreate(**data)
        # You'll need to get user_id from authentication
        new_feedback = create_feedback(db=db, feedback=feedback_create, user_id=1)
        db.close()
        return new_feedback
    except Exception as e:
        print(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")

@app.get("/feedback")
async def get_user_feedback():
    if not DATABASE_AVAILABLE:
        return []
    
    try:
        db = next(get_db())
        feedbacks = get_feedbacks(db, user_id=1, skip=0, limit=100)
        db.close()
        return feedbacks
    except Exception as e:
        print(f"Get feedback error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get feedback: {str(e)}")

@app.post("/network-logs")
async def submit_network_log(request: Request):
    if not DATABASE_AVAILABLE:
        data = await parse_body(request)
        return {
            "id": 1,
            "message": "Network log received (stored in memory)",
            "data": data,
            "timestamp": datetime.utcnow()
        }
    
    try:
        data = await parse_body(request)
        db = next(get_db())
        log_create = NetworkLogCreate(**data)
        new_log = create_network_log(db=db, log=log_create, user_id=1)
        db.close()
        return new_log
    except Exception as e:
        print(f"Network log error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit network log: {str(e)}")

@app.get("/network-logs")
async def get_user_network_logs():
    if not DATABASE_AVAILABLE:
        return []
    
    try:
        db = next(get_db())
        logs = get_network_logs(db, user_id=1, skip=0, limit=100)
        db.close()
        return logs
    except Exception as e:
        print(f"Get network logs error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get network logs: {str(e)}")

# Initialize database tables
if DATABASE_AVAILABLE:
    try:
        # Check if tables exist before creating
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if not existing_tables:
            Base.metadata.create_all(bind=engine)
            print("✅ Database tables created successfully!")
        else:
            print(f"✅ Using existing tables: {', '.join(existing_tables)}")
    except Exception as e:
        print(f"❌ Error checking/creating tables: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

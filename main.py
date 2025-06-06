from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os

from backend import crud, models, schemas
from backend.database import SessionLocal, engine, get_db

# Load environment variables
load_dotenv()

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="QoE Boost API",
    description="API for Quality of Experience Boost mobile application",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "QoE Boost API is running", "status": "healthy"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint to verify database connection"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "message": "API and database are working properly"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )

# User endpoints
@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@app.post("/auth/login", response_model=schemas.Token)
def login_user(user_login: schemas.UserLogin, db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, user_login.username, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    # For simplicity, returning a basic token structure
    # In production, use proper JWT tokens
    return {"access_token": f"token_{user.id}", "token_type": "bearer"}

# Feedback endpoints
@app.post("/feedback/", response_model=schemas.FeedbackResponse)
def create_feedback(feedback: schemas.FeedbackCreate, user_id: int, db: Session = Depends(get_db)):
    return crud.create_feedback(db=db, feedback=feedback, user_id=user_id)

@app.get("/feedback/")
def get_feedbacks(user_id: int = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_feedbacks(db, user_id=user_id, skip=skip, limit=limit)

# Network Log endpoints
@app.post("/network-logs/", response_model=schemas.NetworkLogResponse)
def create_network_log(log: schemas.NetworkLogCreate, user_id: int, db: Session = Depends(get_db)):
    return crud.create_network_log(db=db, log=log, user_id=user_id)

@app.get("/network-logs/")
def get_network_logs(user_id: int = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_network_logs(db, user_id=user_id, skip=skip, limit=limit)

# Recommendations endpoint
@app.get("/recommendations/")
def get_recommendations(location: str, db: Session = Depends(get_db)):
    return crud.get_provider_recommendations(db, location=location)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

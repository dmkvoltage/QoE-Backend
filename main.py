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
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.get("/users/{user_id}", response_model=schemas.User)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# Network metrics endpoints
@app.post("/network-metrics/", response_model=schemas.NetworkMetrics)
def create_network_metrics(
    metrics: schemas.NetworkMetricsCreate, 
    db: Session = Depends(get_db)
):
    return crud.create_network_metrics(db=db, metrics=metrics)

@app.get("/network-metrics/{user_id}")
def get_user_network_metrics(user_id: int, db: Session = Depends(get_db)):
    return crud.get_network_metrics_by_user(db, user_id=user_id)

# Feedback endpoints
@app.post("/feedback/", response_model=schemas.Feedback)
def create_feedback(feedback: schemas.FeedbackCreate, db: Session = Depends(get_db)):
    return crud.create_feedback(db=db, feedback=feedback)

@app.get("/feedback/{user_id}")
def get_user_feedback(user_id: int, db: Session = Depends(get_db)):
    return crud.get_feedback_by_user(db, user_id=user_id)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

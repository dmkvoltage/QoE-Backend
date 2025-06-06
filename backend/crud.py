from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from passlib.context import CryptContext
from models import User, Feedback, NetworkLog
from schemas import UserCreate, FeedbackCreate, NetworkLogCreate
from typing import List, Optional
import statistics

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# User CRUD operations
def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        provider=user.provider
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# Feedback CRUD operations
def create_feedback(db: Session, feedback: FeedbackCreate, user_id: int):
    db_feedback = Feedback(**feedback.dict(), user_id=user_id)
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback

def get_feedbacks(db: Session, user_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(Feedback)
    if user_id:
        query = query.filter(Feedback.user_id == user_id)
    return query.offset(skip).limit(limit).all()

# Network Log CRUD operations
def create_network_log(db: Session, log: NetworkLogCreate, user_id: int):
    db_log = NetworkLog(**log.dict(), user_id=user_id)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_network_logs(db: Session, user_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(NetworkLog)
    if user_id:
        query = query.filter(NetworkLog.user_id == user_id)
    return query.order_by(desc(NetworkLog.timestamp)).offset(skip).limit(limit).all()

# Recommendation logic
def get_provider_recommendations(db: Session, location: str):
    # Get all network logs for the specified location
    logs = db.query(NetworkLog).filter(
        NetworkLog.location.ilike(f"%{location}%")
    ).all()
    
    if not logs:
        return []
    
    # Group by carrier and calculate metrics
    carrier_metrics = {}
    
    for log in logs:
        if log.carrier not in carrier_metrics:
            carrier_metrics[log.carrier] = {
                'download_speeds': [],
                'upload_speeds': [],
                'latencies': [],
                'signal_strengths': [],
                'total_samples': 0
            }
        
        metrics = carrier_metrics[log.carrier]
        metrics['total_samples'] += 1
        
        if log.download_speed:
            metrics['download_speeds'].append(log.download_speed)
        if log.upload_speed:
            metrics['upload_speeds'].append(log.upload_speed)
        if log.latency:
            metrics['latencies'].append(log.latency)
        if log.signal_strength:
            metrics['signal_strengths'].append(log.signal_strength)
    
    # Calculate recommendations
    recommendations = []
    
    for carrier, metrics in carrier_metrics.items():
        if metrics['total_samples'] < 3:  # Need minimum samples
            continue
            
        # Calculate averages
        avg_download = statistics.mean(metrics['download_speeds']) if metrics['download_speeds'] else 0
        avg_upload = statistics.mean(metrics['upload_speeds']) if metrics['upload_speeds'] else 0
        avg_latency = statistics.mean(metrics['latencies']) if metrics['latencies'] else 999
        avg_signal = statistics.mean(metrics['signal_strengths']) if metrics['signal_strengths'] else -100
        
        # Calculate score (higher is better)
        # Normalize metrics and combine them
        download_score = min(avg_download / 100, 1.0) * 40  # Max 40 points
        upload_score = min(avg_upload / 50, 1.0) * 20       # Max 20 points
        latency_score = max(0, (200 - avg_latency) / 200) * 25  # Max 25 points (lower latency is better)
        signal_score = max(0, (avg_signal + 120) / 70) * 15     # Max 15 points (higher signal is better)
        
        total_score = download_score + upload_score + latency_score + signal_score
        
        # Generate recommendation reason
        reasons = []
        if avg_download > 50:
            reasons.append("excellent download speeds")
        elif avg_download > 25:
            reasons.append("good download speeds")
        
        if avg_latency < 50:
            reasons.append("low latency")
        elif avg_latency < 100:
            reasons.append("moderate latency")
        
        if avg_signal > -70:
            reasons.append("strong signal coverage")
        elif avg_signal > -85:
            reasons.append("decent signal coverage")
        
        recommendation_reason = f"Recommended for {', '.join(reasons) if reasons else 'basic connectivity'}"
        
        recommendations.append({
            'carrier': carrier,
            'score': round(total_score, 2),
            'avg_download_speed': round(avg_download, 2),
            'avg_upload_speed': round(avg_upload, 2),
            'avg_latency': round(avg_latency, 2),
            'avg_signal_strength': round(avg_signal, 2),
            'total_samples': metrics['total_samples'],
            'recommendation_reason': recommendation_reason
        })
    
    # Sort by score (highest first)
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    return recommendations

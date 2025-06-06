from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to get the connection string from environment, with fallbacks
DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL")

if not DATABASE_URL:
    # Fallback: construct from individual components
    SUPABASE_HOST = os.getenv("SUPABASE_HOST", "")
    SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD", "08200108dyekrane")
    SUPABASE_PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF", "tlcbimopgpcaxgehncey")
    
    if SUPABASE_HOST:
        DATABASE_URL = f"postgresql://postgres:{SUPABASE_PASSWORD}@{SUPABASE_HOST}:5432/postgres"
    else:
        # Default to direct connection format
        DATABASE_URL = f"postgresql://postgres:{SUPABASE_PASSWORD}@db.{SUPABASE_PROJECT_REF}.supabase.co:5432/postgres"

print(f"🔗 Using database URL: {DATABASE_URL}")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    echo=False  # Set to True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_connection():
    """Test the database connection"""
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

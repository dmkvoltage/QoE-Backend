"""
Setup script for Supabase database
Run this script to create all necessary tables in your Supabase database
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from .database import Base, engine
from . import models

# Load environment variables
load_dotenv()

def create_tables():
    """Create all tables in the Supabase database"""
    try:
        print("🚀 Setting up Supabase database...")
        
        # Test connection first
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected to PostgreSQL: {version}")
        
        # Create all tables
        print("📋 Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ All tables created successfully!")
        
        # Verify tables were created
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"📊 Created tables: {', '.join(tables)}")
        
        print("🎉 Supabase setup completed successfully!")
        
    except Exception as e:
        print(f"❌ Error setting up Supabase: {str(e)}")
        print("💡 Make sure your Supabase credentials are correct in the .env file")

if __name__ == "__main__":
    create_tables()

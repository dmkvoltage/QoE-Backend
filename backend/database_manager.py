"""
Database Manager for handling table creation, migrations, and schema updates safely
"""
from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.exc import SQLAlchemyError
from .database import engine, Base
import .models
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.inspector = inspect(self.engine)
        
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database"""
        try:
            return table_name in self.inspector.get_table_names()
        except Exception as e:
            logger.error(f"Error checking if table {table_name} exists: {e}")
            return False
    
    def get_existing_tables(self) -> list:
        """Get list of all existing tables"""
        try:
            return self.inspector.get_table_names()
        except Exception as e:
            logger.error(f"Error getting existing tables: {e}")
            return []
    
    def get_table_columns(self, table_name: str) -> list:
        """Get columns for a specific table"""
        try:
            if self.table_exists(table_name):
                columns = self.inspector.get_columns(table_name)
                return [col['name'] for col in columns]
            return []
        except Exception as e:
            logger.error(f"Error getting columns for table {table_name}: {e}")
            return []
    
    def create_missing_tables(self):
        """Create only tables that don't exist"""
        try:
            logger.info("🔍 Checking for missing tables...")
            
            # Get all table names that should exist (from models)
            expected_tables = []
            for table in Base.metadata.tables.values():
                expected_tables.append(table.name)
            
            existing_tables = self.get_existing_tables()
            missing_tables = [table for table in expected_tables if table not in existing_tables]
            
            if missing_tables:
                logger.info(f"📋 Creating missing tables: {missing_tables}")
                
                # Create only missing tables
                for table_name in missing_tables:
                    table = Base.metadata.tables[table_name]
                    table.create(self.engine, checkfirst=True)
                    logger.info(f"✅ Created table: {table_name}")
                
                logger.info("🎉 All missing tables created successfully!")
            else:
                logger.info("✅ All tables already exist, no action needed")
                
        except Exception as e:
            logger.error(f"❌ Error creating missing tables: {e}")
            raise
    
    def verify_table_schema(self, table_name: str) -> dict:
        """Verify if table schema matches the model definition"""
        try:
            if not self.table_exists(table_name):
                return {"exists": False, "schema_match": False, "missing_columns": []}
            
            existing_columns = self.get_table_columns(table_name)
            
            # Get expected columns from model
            if table_name in Base.metadata.tables:
                model_table = Base.metadata.tables[table_name]
                expected_columns = [col.name for col in model_table.columns]
                
                missing_columns = [col for col in expected_columns if col not in existing_columns]
                extra_columns = [col for col in existing_columns if col not in expected_columns]
                
                return {
                    "exists": True,
                    "schema_match": len(missing_columns) == 0 and len(extra_columns) == 0,
                    "missing_columns": missing_columns,
                    "extra_columns": extra_columns,
                    "existing_columns": existing_columns,
                    "expected_columns": expected_columns
                }
            
            return {"exists": True, "schema_match": False, "error": "Model not found"}
            
        except Exception as e:
            logger.error(f"Error verifying schema for table {table_name}: {e}")
            return {"exists": False, "schema_match": False, "error": str(e)}
    
    def add_missing_columns(self, table_name: str):
        """Add missing columns to existing table"""
        try:
            schema_info = self.verify_table_schema(table_name)
            
            if schema_info.get("missing_columns"):
                logger.info(f"🔧 Adding missing columns to {table_name}: {schema_info['missing_columns']}")
                
                # This is a simplified approach - in production, use Alembic for complex migrations
                model_table = Base.metadata.tables[table_name]
                
                for column_name in schema_info["missing_columns"]:
                    column = model_table.columns[column_name]
                    column_type = column.type.compile(self.engine.dialect)
                    
                    # Build ALTER TABLE statement
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    
                    # Add default value if column is not nullable
                    if not column.nullable and column.default is None:
                        if 'VARCHAR' in str(column_type) or 'TEXT' in str(column_type):
                            alter_sql += " DEFAULT ''"
                        elif 'INTEGER' in str(column_type) or 'NUMERIC' in str(column_type):
                            alter_sql += " DEFAULT 0"
                        elif 'BOOLEAN' in str(column_type):
                            alter_sql += " DEFAULT FALSE"
                        elif 'TIMESTAMP' in str(column_type):
                            alter_sql += " DEFAULT CURRENT_TIMESTAMP"
                    
                    with self.engine.connect() as conn:
                        conn.execute(text(alter_sql))
                        conn.commit()
                        logger.info(f"✅ Added column {column_name} to {table_name}")
                
        except Exception as e:
            logger.error(f"❌ Error adding missing columns to {table_name}: {e}")
            raise
    
    def safe_initialize_database(self):
        """Safely initialize database with existing table checks"""
        try:
            logger.info("🚀 Starting safe database initialization...")
            
            # Test connection first
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("✅ Database connection successful")
            
            # Get current state
            existing_tables = self.get_existing_tables()
            logger.info(f"📊 Found existing tables: {existing_tables}")
            
            # Create missing tables only
            self.create_missing_tables()
            
            # Verify and update schema for existing tables
            for table_name in existing_tables:
                if table_name in Base.metadata.tables:
                    schema_info = self.verify_table_schema(table_name)
                    logger.info(f"🔍 Schema check for {table_name}: {schema_info}")
                    
                    if not schema_info.get("schema_match") and schema_info.get("missing_columns"):
                        logger.info(f"🔧 Updating schema for {table_name}")
                        self.add_missing_columns(table_name)
            
            logger.info("🎉 Database initialization completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            return False
    
    def get_database_info(self) -> dict:
        """Get comprehensive database information"""
        try:
            info = {
                "connection_status": "connected",
                "existing_tables": self.get_existing_tables(),
                "table_details": {}
            }
            
            for table_name in info["existing_tables"]:
                info["table_details"][table_name] = {
                    "columns": self.get_table_columns(table_name),
                    "schema_info": self.verify_table_schema(table_name)
                }
            
            return info
            
        except Exception as e:
            return {
                "connection_status": "failed",
                "error": str(e),
                "existing_tables": [],
                "table_details": {}
            }

# Global database manager instance
db_manager = DatabaseManager()

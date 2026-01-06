from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL from environment variable
DB_URL = os.getenv("DATABASE_URL")

SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
    "poolclass": NullPool,
    "echo": True,
}

# Create Engine
engine = create_engine(
    DB_URL,
    **SQLALCHEMY_ENGINE_OPTIONS,
    connect_args={"charset": "utf8mb4"},
    pool_recycle=3600,
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)

# Base class for models
Base = declarative_base()

def get_db():
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Flow_Id(Base):
    __tablename__ = "flow_id"

    id = Column(String(36), primary_key=True, index=True)  # UUID as string
    customer_id = Column(Integer, index=True, nullable=False)
    feature = Column(JSON, nullable=True)  # Array of strings stored as JSON
    phone_number = Column(String(20), nullable=False)
    expiry = Column(DateTime, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
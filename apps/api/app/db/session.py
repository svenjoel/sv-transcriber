from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import DB_URL

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

from app.db.models import Base

def init_db():
    Base.metadata.create_all(bind=engine)

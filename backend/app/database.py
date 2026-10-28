from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
pool_options = {} if settings.database_url.startswith("sqlite") else {
    "pool_size": 5,
    "max_overflow": 5,
    "pool_recycle": 1800,
    "pool_timeout": 20,
}
engine = create_engine(
    settings.database_url, pool_pre_ping=True, connect_args=connect_args, **pool_options
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

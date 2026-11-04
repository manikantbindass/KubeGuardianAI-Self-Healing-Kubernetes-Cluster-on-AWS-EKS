from collections.abc import Generator

from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from kubesentinel_api.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    str(settings.database_url),
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=1800,
    pool_timeout=3,
    connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
redis_client: Redis = Redis.from_url(
    str(settings.redis_url), decode_responses=True, socket_connect_timeout=2, socket_timeout=3
)


def get_db() -> Generator[Session]:
    with SessionLocal() as session:
        yield session


def get_redis() -> Redis:
    return redis_client

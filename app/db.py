from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, JSON, Float, Integer, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings

def now():
    return datetime.now(timezone.utc).timestamp()

engine = create_engine(settings.database_url, connect_args={'check_same_thread': False} if settings.database_url.startswith('sqlite') else {}, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass
class Event(Base):
    __tablename__ = 'events'
    __table_args__ = (UniqueConstraint('source_id', 'event_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(100))
    event_id: Mapped[str] = mapped_column(String(100))
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    actor_id: Mapped[str] = mapped_column(String(100))
    asset_id: Mapped[str] = mapped_column(String(100))
    event_time: Mapped[str] = mapped_column(String(50))
    command: Mapped[str] = mapped_column(Text)
    exit_code: Mapped[int | None]
    received_at: Mapped[float] = mapped_column(Float, default=now)
class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_pk: Mapped[int] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    claim_token: Mapped[str] = mapped_column(String(50), default='')
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)
class Alert(Base):
    __tablename__ = 'alerts'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_pk: Mapped[int] = mapped_column(unique=True)
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON)
    analysis: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default='open')
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[float] = mapped_column(Float, default=now)

def init_db():
    Base.metadata.create_all(engine)

def asdict(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}

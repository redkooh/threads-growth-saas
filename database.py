"""SaaS Database — SQLAlchemy models + SQLite (dev) / PostgreSQL (prod)."""
import os, json
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, Float, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import StaticPool

DB_TYPE = os.environ.get("SAAS_DB_TYPE", "sqlite")

if DB_TYPE == "postgresql":
    DB_USER = os.environ.get("SAAS_DB_USER", "saas_user")
    DB_PASS = os.environ.get("SAAS_DB_PASS", "")
    DB_HOST = os.environ.get("SAAS_DB_HOST", "/tmp")
    DB_PORT = os.environ.get("SAAS_DB_PORT", "5432")
    DB_NAME = os.environ.get("SAAS_DB_NAME", "threads_saas")
    if DB_HOST == "/tmp":
        DB_URL = f"postgresql://{DB_USER}:{DB_PASS}@/{DB_NAME}?host={DB_HOST}"
    else:
        DB_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(DB_URL, pool_size=10, max_overflow=20)
else:
    DB_PATH = os.environ.get("SAAS_DB", os.path.join(os.path.dirname(__file__) or ".", "saas.db"))
    DB_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), default="")
    password_hash = Column(String(255), nullable=False)
    plan = Column(String(50), default="starter")  # starter, growth, agency
    status = Column(String(50), default="active")  # active, canceled, paused
    stripe_customer_id = Column(String(255), default="")
    email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(255), default="")
    reset_token = Column(String(255), default="")
    reset_token_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    trial_expires_at = Column(DateTime, nullable=True)
    accounts = relationship("Account", back_populates="user", cascade="all, delete")


class UsernameLock(Base):
    """Permanent lock: once a Threads username is connected, it's locked forever across ALL users.
    Even if the account is deleted, the username remains locked.
    """
    __tablename__ = "username_locks"
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False, index=True)  # e.g. "cristiano"
    locked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # who owns it
    locked_at = Column(DateTime, default=datetime.utcnow)


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    username = Column(String(255), default="", unique=True)  # unique across all users — one account per username
    display_name = Column(String(255), default="")
    bio = Column(String(500), default="")
    link = Column(String(500), default="")
    ds_user_id = Column(String(100), default="")
    niche = Column(String(100), default="general")
    cookies_encrypted = Column(Text, default="")
    proxy = Column(String(500), default="")
    active = Column(Boolean, default=True)

    # ── Target Settings ──
    target_threads = Column(Integer, default=6)
    target_replies = Column(Integer, default=10)
    target_follows = Column(Integer, default=5)
    target_dms = Column(Integer, default=2)

    # ── Daily Limits (caps) ──
    max_threads = Column(Integer, default=8)
    max_replies = Column(Integer, default=15)
    max_follows = Column(Integer, default=10)
    max_dms = Column(Integer, default=5)
    sleep_hours_start = Column(Integer, default=2)
    sleep_hours_end = Column(Integer, default=8)

    # ── Content Style ──
    content_style = Column(String(50), default="auto")
    vibe = Column(String(100), default="")
    post_tone = Column(String(50), default="friendly")
    post_length = Column(String(20), default="auto")
    post_format = Column(String(20), default="text")
    topic_keywords = Column(Text, default="")
    avoid_topics = Column(Text, default="")
    links_enabled = Column(Boolean, default=False)

    # ── Writing Style ──
    writing_style = Column(Text, default="")

    # ── Audience Targeting ──
    target_niche = Column(String(200), default="")
    target_locations = Column(Text, default="")
    target_follower_min = Column(Integer, default=0)
    target_follower_max = Column(Integer, default=1000000)

    # ── Account Tags ──
    account_tags = Column(Text, default="[]")

    # ── Reply Strategy ──
    reply_keywords = Column(Text, default="")
    reply_tone = Column(String(50), default="auto")
    reply_length = Column(String(20), default="auto")
    viral_threshold = Column(Integer, default=0)

    # ── Follow Strategy ──
    follow_source = Column(String(50), default="niche_search")

    # ── Stats (reset daily) ──
    today_threads = Column(Integer, default=0)
    today_replies = Column(Integer, default=0)
    today_follows = Column(Integer, default=0)
    today_dms = Column(Integer, default=0)
    last_reset_date = Column(String(10), default="")  # YYYY-MM-DD — set by scheduler on daily reset
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="accounts")
    schedules = relationship("Schedule", back_populates="account", cascade="all, delete")


class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    slot_name = Column(String(50), default="slot-1")
    hour_utc = Column(Integer, default=11)
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    last_status = Column(String(50), default="never")
    post_type = Column(String(20), default="thread")
    account = relationship("Account", back_populates="schedules")


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    thread_code = Column(String(255), default="")
    post_type = Column(String(50), default="thread")
    content_preview = Column(String(500), default="")
    posted_at = Column(DateTime, default=datetime.utcnow)
    likes = Column(Integer, default=0)
    replies = Column(Integer, default=0)


class ContentPreset(Base):
    __tablename__ = "content_presets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    settings_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    action = Column(String(50), nullable=False)
    detail = Column(String(500), default="")
    thread_code = Column(String(255), default="")
    posted_at = Column(DateTime, default=datetime.utcnow, index=True)
    account = relationship("Account")


def init_db():
    Base.metadata.create_all(engine)
    return engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_account_limit(plan: str) -> int:
    return {"owner": 999, "starter": 1, "growth": 3, "agency": 15}.get(plan, 1)


def get_daily_limit(plan: str) -> int:
    return {"owner": 99999, "starter": 60, "growth": 60, "agency": 60}.get(plan, 60)

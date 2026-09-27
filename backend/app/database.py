"""SQLite persistence for fruit guidance content."""
import os
from pathlib import Path
from sqlalchemy import create_engine, ForeignKey, String, Text, Integer, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_DB_PATH = os.environ.get("DATABASE_URL") or os.environ.get("SQLITE_DB_PATH")
if ENV_DB_PATH:
    if ENV_DB_PATH.startswith("sqlite:///"):
        DATABASE_URL = ENV_DB_PATH
    else:
        DATABASE_URL = f"sqlite:///{ENV_DB_PATH}"
else:
    DB_FOLDER = Path(os.environ.get("SQLITE_DB_DIR", str(BASE_DIR)))
    try:
        DB_FOLDER.mkdir(parents=True, exist_ok=True)
    except Exception:
        DB_FOLDER = Path("/tmp")
    DATABASE_URL = f"sqlite:///{DB_FOLDER / 'fruit_quality.db'}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class Fruit(Base):
    __tablename__ = "fruits"
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    benefits: Mapped[str] = mapped_column(Text, default="[]")
    harms: Mapped[str] = mapped_column(Text, default="[]")
    disposal_tip: Mapped[str] = mapped_column(Text, default="Seal spoiled fruit in a bag and place it in organic waste.")
    sample_image: Mapped[str | None] = mapped_column(String(500), nullable=True)

class FruitNotebook(Base):
    __tablename__ = "fruit_notebook"
    fruit_name: Mapped[str] = mapped_column(ForeignKey("fruits.name", ondelete="CASCADE"), primary_key=True)
    highlight: Mapped[str] = mapped_column(String(255))
    benefits: Mapped[str] = mapped_column(Text, default="[]")
    good_combinations: Mapped[str] = mapped_column(Text, default="[]")
    bad_combinations: Mapped[str] = mapped_column(Text, default="[]")
    overconsumption_risk: Mapped[str] = mapped_column(Text, default="")
    rotten_fruit_harms: Mapped[str] = mapped_column(Text, default="[]")
    safe_disposal_tip: Mapped[str] = mapped_column(Text, default="")
    storage_tip: Mapped[str] = mapped_column(Text, default="")
    shelf_life_days: Mapped[str] = mapped_column(Text, default="{}")
    nutrition_facts: Mapped[str] = mapped_column(Text, default="{}")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="customer", index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class PasswordReset(Base):
    __tablename__ = "password_resets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    used: Mapped[bool] = mapped_column(default=False)

class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    fruit: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float]
    ripeness_stage: Mapped[str] = mapped_column(String(30), default="ripe")
    shelf_life_estimate: Mapped[str] = mapped_column(String(40), default="2-4 days")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class BatchScan(Base):
    __tablename__ = "batch_scans"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    total: Mapped[int] = mapped_column(Integer)
    fresh_count: Mapped[int] = mapped_column(Integer, default=0)
    rotten_count: Mapped[int] = mapped_column(Integer, default=0)
    not_recognized_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class BatchScanItem(Base):
    __tablename__ = "batch_scan_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batch_scans.batch_id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    fruit: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float, default=0)
    ripeness_stage: Mapped[str] = mapped_column(String(30), default="not_recognized")
    shelf_life_estimate: Mapped[str] = mapped_column(String(40), default="-")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        migrations = [
            ("users", "role", "VARCHAR(20) DEFAULT 'customer'"),
            ("predictions", "ripeness_stage", "VARCHAR(30) DEFAULT 'ripe'"),
            ("predictions", "shelf_life_estimate", "VARCHAR(40) DEFAULT '2-4 days'"),
            ("fruit_notebook", "shelf_life_days", "TEXT DEFAULT '{}'"),
            ("fruit_notebook", "nutrition_facts", "TEXT DEFAULT '{}'"),
        ]
        for table, column, definition in migrations:
            existing = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            if not any(row[1] == column for row in existing):
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        connection.exec_driver_sql("UPDATE users SET role = 'customer' WHERE role IS NULL")
        
        # Create password_resets table if it doesn't exist
        connection.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_password_resets_token ON password_resets(token)")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_password_resets_user_id ON password_resets(user_id)")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

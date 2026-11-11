"""Operational SQL store; historical ML JSON is a separate read-only source."""
import os
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")
DB_PATH = BASE_DIR / 'lucy.db'
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DB_PATH}')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
HOSTED = bool(os.getenv('VERCEL')) or os.getenv('APP_ENV') == 'production'
if HOSTED and not DATABASE_URL.startswith('postgresql+psycopg://'):
    raise RuntimeError('Hosted Lucy requires durable PostgreSQL via DATABASE_URL; SQLite is local only')
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False, 'timeout': 30}} if DATABASE_URL.startswith('sqlite:') else {}))
if engine.dialect.name == 'sqlite':
    @event.listens_for(engine, 'connect')
    def sqlite_settings(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        try:
            # Phase 0 serializes operational writes, including idempotency checks.
            # PostgreSQL uses a transaction-scoped cross-instance lock.
            if engine.dialect.name == 'sqlite':
                db.execute(text('BEGIN IMMEDIATE'))
            else:
                db.execute(text('SELECT pg_advisory_xact_lock(202611110)'))
            yield db
            db.commit()
        except Exception as exc:
            db.rollback()
            rejected = getattr(exc, 'audit_failure', None)
            if rejected:
                from .domain_models import AuditEvent, Mission
                # Do not attach invalid/untrusted foreign references to the ledger.
                if rejected['mission_id'] and db.get(Mission, rejected['mission_id']) is None:
                    rejected['mission_id'] = None
                db.add(AuditEvent(**rejected))
                db.commit()
            raise

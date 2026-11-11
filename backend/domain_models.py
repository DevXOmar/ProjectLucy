"""Version 1 operational schema. All monetary state is integer paise."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Integer, JSON, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return str(uuid4())

class Record:
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    created_at: Mapped[str] = mapped_column(String, default=now)

class SchemaVersion(Base):
    __tablename__ = 'lucy_schema_version'
    version: Mapped[int] = mapped_column(primary_key=True)

class Mission(Record, Base):
    __tablename__ = 'missions'
    requester_id: Mapped[int] = mapped_column(ForeignKey('customers.id'))
    goal: Mapped[str]
    requirements: Mapped[dict] = mapped_column(JSON)
    budget_paise: Mapped[int]
    deadline: Mapped[str | None]
    authorization_scope: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default='CREATED')
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)

class MissionTask(Record, Base):
    __tablename__ = 'mission_tasks'
    mission_id: Mapped[str] = mapped_column(ForeignKey('missions.id'))
    agent_id: Mapped[str]
    task_type: Mapped[str]
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default='CREATED')
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)

class MerchantOffer(Record, Base):
    __tablename__ = 'merchant_offers'
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'))
    product_id: Mapped[str]
    title: Mapped[str]
    kind: Mapped[str]
    price_paise: Mapped[int]
    currency: Mapped[str] = mapped_column(default='INR')
    expires_at: Mapped[str]
    terms: Mapped[dict] = mapped_column(JSON)
    simulated: Mapped[bool] = mapped_column(default=True)

class Inventory(Record, Base):
    __tablename__ = 'inventory'
    offer_id: Mapped[str] = mapped_column(ForeignKey('merchant_offers.id'), unique=True)
    available: Mapped[int]
    __table_args__ = (CheckConstraint('available >= 0'),)

class Order(Record, Base):
    __tablename__ = 'orders'
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'))
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'))
    mission_id: Mapped[str | None] = mapped_column(ForeignKey('missions.id'))
    total_paise: Mapped[int]
    currency: Mapped[str] = mapped_column(default='INR')
    status: Mapped[str] = mapped_column(default='DRAFT')

class OrderItem(Record, Base):
    __tablename__ = 'order_items'
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'))
    offer_id: Mapped[str] = mapped_column(ForeignKey('merchant_offers.id'))
    quantity: Mapped[int]
    unit_price_paise: Mapped[int]

class Reservation(Record, Base):
    __tablename__ = 'reservations'
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'))
    offer_id: Mapped[str] = mapped_column(ForeignKey('merchant_offers.id'))
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'))
    quantity: Mapped[int]
    expires_at: Mapped[str]
    status: Mapped[str] = mapped_column(default='ACTIVE')

class Approval(Record, Base):
    __tablename__ = 'approvals'
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'))
    amount_paise: Mapped[int]
    status: Mapped[str] = mapped_column(default='REQUESTED')
    decided_at: Mapped[str | None]

class PaymentSession(Record, Base):
    __tablename__ = 'payment_sessions'
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'))
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchants.id'))
    order_id: Mapped[str | None] = mapped_column(ForeignKey('orders.id'), unique=True)
    amount_paise: Mapped[int]
    currency: Mapped[str] = mapped_column(default='INR')
    status: Mapped[str] = mapped_column(default='CREATED')
    mode: Mapped[str] = mapped_column(default='DEMO_SIMULATED')
    externally_verified: Mapped[bool] = mapped_column(default=False)
    refund_status: Mapped[str] = mapped_column(default='NONE')
    dispute_status: Mapped[str] = mapped_column(default='NONE')

class PaymentEvent(Record, Base):
    __tablename__ = 'payment_events'
    session_id: Mapped[str] = mapped_column(ForeignKey('payment_sessions.id'))
    event_key: Mapped[str] = mapped_column(unique=True)
    from_status: Mapped[str]
    to_status: Mapped[str]
    provenance: Mapped[str] = mapped_column(default='DEMO_SIMULATED')

class AuditEvent(Record, Base):
    __tablename__ = 'audit_events'
    actor: Mapped[str]
    specialist: Mapped[str]
    mission_id: Mapped[str | None] = mapped_column(ForeignKey('missions.id'))
    action: Mapped[str]
    inputs: Mapped[dict] = mapped_column(JSON)
    outputs: Mapped[dict] = mapped_column(JSON)
    approval_state: Mapped[str]
    verification: Mapped[str]

class Idempotency(Record, Base):
    __tablename__ = 'idempotency'
    actor: Mapped[str]
    key: Mapped[str]
    action: Mapped[str]
    fingerprint: Mapped[str]
    result: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('actor', 'key'),)

class DemoRedemption(Record, Base):
    __tablename__ = 'demo_redemptions'
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'))
    points: Mapped[int]
    offer: Mapped[str]

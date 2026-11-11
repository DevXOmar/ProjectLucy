from typing import Literal
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)

class MissionIn(Contract):
    goal: str = Field(min_length=3, max_length=2000)
    requirements: dict = Field(default_factory=dict)
    budget_paise: int = Field(gt=0, le=100_000_000, strict=True)
    deadline: datetime | None = None
    @field_validator('requirements')
    @classmethod
    def valid_requirements(cls, value):
        products = value.get('products', [])
        if not isinstance(products, list) or len(products) > 50:
            raise ValueError('products must be a list of at most 50 product requirements')
        seen = set()
        for product in products:
            if not isinstance(product, dict) or set(product) != {'product_id', 'quantity'}:
                raise ValueError('Each product requires product_id and quantity')
            if not isinstance(product['product_id'], str) or not product['product_id'] or product['product_id'] in seen:
                raise ValueError('Product IDs must be unique non-empty strings')
            if type(product['quantity']) is not int or not 0 < product['quantity'] <= 1000:
                raise ValueError('Product quantities must be integers in 1..1000')
            seen.add(product['product_id'])
        return value
    @field_validator('deadline')
    @classmethod
    def valid_deadline(cls, value):
        if value and (value.tzinfo is None or value <= datetime.now(timezone.utc)):
            raise ValueError('Deadline must be a future timezone-aware timestamp')
        return value

class OrderLine(Contract):
    offer_id: str
    quantity: int = Field(gt=0, le=1000, strict=True)

class OrderIn(Contract):
    merchant_id: int = Field(gt=0, strict=True)
    mission_id: str | None = None
    items: list[OrderLine] = Field(min_length=1, max_length=20)

class ReserveIn(Contract):
    order_id: str
    ttl_seconds: int = Field(default=600, ge=30, le=900)

class OrderRef(Contract):
    order_id: str

class PaymentIn(Contract):
    merchant_id: int = Field(gt=0, strict=True)
    amount_paise: int = Field(gt=0, le=100_000_000, strict=True)
    currency: Literal['INR'] = 'INR'
    order_id: str | None = None

class Decision(Contract):
    approve: bool

class PaymentTransition(Contract):
    status: Literal['CONFIRMED', 'FAILED', 'CANCELLED']
    event_key: str = Field(min_length=8, max_length=150)

class MissionTransition(Contract):
    status: Literal['CREATED','PLANNING','AWAITING_APPROVAL','EXECUTING','REPLANNING','VERIFYING','COMPLETED','BLOCKED','FAILED','CANCELLED']

class TaskIn(Contract):
    agent_id: str
    task_type: str
    dependencies: list[str] = Field(default_factory=list)

class PricingIn(Contract):
    sku: str = Field(min_length=1, max_length=200)
    action: Literal['accept'] = 'accept'

class RedemptionIn(Contract):
    offer: str = Field(min_length=1, max_length=200)
    points: int = Field(gt=0, strict=True)

class PaymentOut(Contract):
    id: str
    created_at: str
    customer_id: int
    merchant_id: int
    order_id: str | None
    amount_paise: int
    currency: str
    status: str
    mode: str
    externally_verified: bool
    refund_status: str
    dispute_status: str

class OrderOut(Contract):
    id: str
    created_at: str
    customer_id: int
    merchant_id: int
    mission_id: str | None
    total_paise: int
    currency: str
    status: str
    items: list[dict] = Field(default_factory=list)

class OfferOut(Contract):
    id: str
    created_at: str
    merchant_id: int
    product_id: str
    title: str
    kind: str
    price_paise: int
    currency: str
    expires_at: str
    terms: dict
    simulated: bool
    available: int

class MissionOut(Contract):
    goal: str
    requirements: dict
    budget_paise: int
    deadline: str | None
    id: str
    created_at: str
    requester_id: int
    authorization_scope: dict
    status: str
    evidence_refs: list

class ReservationOut(Contract):
    id: str
    order_id: str
    offer_id: str
    customer_id: int
    quantity: int
    expires_at: str
    status: str
    created_at: str

class ApprovalOut(Contract):
    id: str
    order_id: str
    customer_id: int
    amount_paise: int
    status: str
    decided_at: str | None
    created_at: str

class TaskProgress(Contract):
    status: Literal['EXECUTING','BLOCKED','COMPLETED','FAILED','CANCELLED']
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)

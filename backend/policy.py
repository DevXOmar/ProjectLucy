import os
from dataclasses import dataclass
from fastapi import Header, HTTPException
from .database import HOSTED

@dataclass(frozen=True)
class Actor:
    role: str
    id: int
    @property
    def key(self):
        return f'{self.role}:{self.id}'
    def customer(self, customer_id=None):
        if self.role != 'customer' or (customer_id is not None and self.id != customer_id):
            raise HTTPException(403, 'Customer authorization required')
    def merchant(self, merchant_id):
        if self.role != 'merchant' or self.id != merchant_id:
            raise HTTPException(403, 'Merchant authorization required')
    def record(self, record):
        expected = record.customer_id if self.role == 'customer' else record.merchant_id
        if self.id != expected:
            raise HTTPException(403, 'Record is outside identity scope')

def identity(x_demo_role: str = Header(default=''), x_demo_id: int = Header(default=0)):
    enabled = os.getenv('LUCY_DEMO_AUTH', 'false' if HOSTED else 'true') == 'true'
    if not enabled:
        raise HTTPException(403, 'Demo identity is disabled; deploy behind authentication before enabling mutations')
    if x_demo_role not in ('customer', 'merchant') or x_demo_id <= 0:
        raise HTTPException(401, 'Explicit X-Demo-Role and X-Demo-Id headers required')
    return Actor(x_demo_role, x_demo_id)

def idempotency_key(idempotency_key: str = Header(min_length=8, max_length=150)):
    return idempotency_key

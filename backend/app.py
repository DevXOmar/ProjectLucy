from __future__ import annotations

import json
from pathlib import Path

# Vercel and `uvicorn app:app --app-dir backend` may load this file as a
# top-level module. Register the adjacent package so domain imports stay shared.
if not __package__:
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location('backend', Path(__file__).with_name('__init__.py'), submodule_search_locations=[str(Path(__file__).parent)])
    package = importlib.util.module_from_spec(spec)
    sys.modules.setdefault('backend', package)
    spec.loader.exec_module(sys.modules['backend'])
    sys.modules.setdefault('backend.app', sys.modules[__name__])
    __package__ = 'backend'

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from .database import get_db, HOSTED, SessionLocal
from .domain_models import PaymentSession, PaymentEvent, AuditEvent, DemoRedemption
from .fixtures import initialize
from .policy import identity, idempotency_key
from .commerce import router
from . import services as service, contracts
from contextlib import asynccontextmanager
import os
import logging
from fastapi.middleware.cors import CORSMiddleware

try:
    from .upi import is_valid_vpa, payment_intents
except ImportError:
    from upi import is_valid_vpa, payment_intents

DATA_PATH = Path(__file__).resolve().parent / "data" / "precomputed.json"
DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))

@asynccontextmanager
async def lifespan(app):
    initialize(DATA)
    yield

app = FastAPI(title="Project Lucy API", lifespan=lifespan)
app.include_router(router)

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": str(exc.status_code), "message": exc.detail}})

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION", "message": "Invalid request", "details": [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]}})

@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    logging.getLogger(__name__).exception("Operational database failure")
    return JSONResponse(status_code=503, content={"error": {"code": "DATABASE", "message": "Database unavailable; retry with the same idempotency key"}})
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('LUCY_CORS_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def find_customer(customer_id: int) -> dict:
    customer = next((item for item in DATA["customers"] if item["id"] == customer_id), None)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def find_merchant(merchant_id: int) -> dict:
    merchant = next((item for item in DATA["merchants"] if item["id"] == merchant_id), None)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return merchant


def transaction_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda item: item["timestamp"], reverse=True)[:100]


def relationship_for(customer_id: int, merchant_id: int) -> dict:
    cached = DATA["ml"]["relationships"].get(f"{customer_id}:{merchant_id}")
    if cached:
        return cached
    customer = find_customer(customer_id)
    merchant = find_merchant(merchant_id)
    rows = [item for item in DATA["transactions"] if item["customer_id"] == customer_id and item["merchant_id"] == merchant_id]
    last_visit = max((item["timestamp"] for item in rows), default=None)
    return {
        "customer_id": customer_id,
        "merchant_id": merchant_id,
        "customer_name": customer["name"],
        "merchant_name": merchant["name"],
        "visit_count": len(rows),
        "tier": "New" if len(rows) < 3 else "Level 1 Regular" if len(rows) < 8 else "Level 2 Regular" if len(rows) < 15 else "VIP",
        "next_tier_threshold": 3 if len(rows) < 3 else 8 if len(rows) < 8 else 15 if len(rows) < 15 else None,
        "visits_to_next_tier": max(0, (3 if len(rows) < 3 else 8 if len(rows) < 8 else 15 if len(rows) < 15 else len(rows)) - len(rows)),
        "p_alive": 0,
        "predicted_clv": 0,
        "postpaid_eligible": False,
        "last_visit_date": last_visit[:10] if last_visit else None,
        "days_since_last_visit": None,
    }


def reward_for(customer_id: int, db) -> dict:
    reward = DATA["ml"]["rewards"].get(str(customer_id))
    if not reward:
        raise HTTPException(status_code=404, detail="Reward offer not found")
    result = dict(reward)
    redeemed = sum(item.points for item in db.scalars(select(DemoRedemption).where(DemoRedemption.customer_id == customer_id)))
    earned = sum(item.amount_paise // 1000 for item in db.scalars(select(PaymentSession).where(PaymentSession.customer_id == customer_id, PaymentSession.status == "CONFIRMED")))
    result["points_balance"] = max(0, int(reward["points_balance"]) + earned - redeemed)
    result["redeemed_points"] = redeemed
    result["source"] = "Historical demo points + simulated confirmed payment points - demo redemptions"
    return result


@app.get("/health")
def health(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "ok": True, "precomputed_at": DATA["ml"]["recomputed_at"], "ml_timings": DATA["ml"]["timings"]}


@app.post("/recompute")
def recompute():
    return {"recomputed_at": DATA["ml"]["recomputed_at"], "timings": DATA["ml"]["timings"], "source": "precomputed snapshot"}


@app.get("/stats")
def demo_stats():
    return DATA["stats"]


@app.get("/customers")
def list_customers():
    return DATA["customers"]


@app.get("/merchants")
def list_merchants():
    return DATA["merchants"]


@app.get("/customers/{customer_id}")
def get_customer(customer_id: int):
    return find_customer(customer_id)


@app.get("/merchants/{merchant_id}")
def get_merchant(merchant_id: int):
    return find_merchant(merchant_id)


@app.get("/merchants/{merchant_id}/transactions")
def merchant_transactions(merchant_id: int, db=Depends(get_db), actor=Depends(identity)):
    actor.merchant(merchant_id)
    find_merchant(merchant_id)
    return transaction_rows([item for item in DATA["transactions"] if item["merchant_id"] == merchant_id] + operational_transactions(db, merchant_id=merchant_id))


@app.get("/customers/{customer_id}/transactions")
def customer_transactions(customer_id: int, db=Depends(get_db), actor=Depends(identity)):
    actor.customer(customer_id)
    find_customer(customer_id)
    return transaction_rows([item for item in DATA["transactions"] if item["customer_id"] == customer_id] + operational_transactions(db, customer_id=customer_id))


@app.get("/relationship/{customer_id}/{merchant_id}")
def relationship(customer_id: int, merchant_id: int):
    return relationship_for(customer_id, merchant_id)


@app.get("/merchant/{merchant_id}/pulse")
def merchant_pulse(merchant_id: int):
    find_merchant(merchant_id)
    result = DATA["ml"]["pulses"].get(str(merchant_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Pulse not found")
    return result


@app.get("/merchant/{merchant_id}/pricing")
def merchant_pricing(merchant_id: int):
    find_merchant(merchant_id)
    result = DATA["ml"]["pricing"].get(str(merchant_id), [])
    return result


@app.get('/merchant/{merchant_id}/pricing/actions')
def pricing_actions(merchant_id: int, db=Depends(get_db), actor=Depends(identity)):
    actor.merchant(merchant_id)
    rows = db.scalars(select(AuditEvent).where(AuditEvent.actor == actor.key, AuditEvent.action == 'accept_pricing', AuditEvent.verification == 'RECORDED'))
    return [event.outputs for event in rows]


@app.post("/merchant/{merchant_id}/pricing/actions")
def accept_pricing_action(merchant_id: int, payload: contracts.PricingIn, db=Depends(get_db), actor=Depends(identity), key=Depends(idempotency_key)):
    actor.merchant(merchant_id)
    find_merchant(merchant_id)
    if payload.sku not in {p['sku'] for p in DATA['ml']['pricing'].get(str(merchant_id), [])}:
        raise HTTPException(422, 'Unknown merchant SKU')
    return service.mutate(db, actor, key, 'accept_pricing', {'merchant_id': merchant_id, **payload.model_dump()},
        lambda: {'ok': True, 'merchant_id': merchant_id, **payload.model_dump(), 'effect': 'Demo recommendation recorded; offer prices unchanged'})


@app.get("/merchants/{merchant_id}/upi-intent")
def merchant_upi_intent(merchant_id: int, amount: float = 0, note: str | None = None):
    merchant = find_merchant(merchant_id)
    txn_note = note or f"Lucy demo preview to {merchant['name']}"
    intents = payment_intents(merchant["vpa"], merchant["name"], max(0.0, amount), txn_note)
    return {
        "merchantId": merchant["id"],
        "payeeVpa": merchant["vpa"],
        "payeeVpaValid": is_valid_vpa(merchant["vpa"]),
        "payeeName": merchant["name"],
        "txnAmount": {"value": f"{max(0.0, amount):.2f}", "currency": "INR"},
        "previewOnly": True, "liveHandoffAllowed": False, "recipientProvenance": "SYNTHETIC",
        "txnNote": txn_note,
        "paytmIntent": intents["paytm_intent"],
        "upiIntent": intents["upi_intent"],
    }


@app.get("/rewards/{customer_id}/multiplier")
def reward_multiplier(customer_id: int, db=Depends(get_db), actor=Depends(identity)):
    actor.customer(customer_id)
    find_customer(customer_id)
    return reward_for(customer_id, db)


@app.post("/rewards/{customer_id}/redeem")
def redeem_reward(customer_id: int, payload: contracts.RedemptionIn, db=Depends(get_db), actor=Depends(identity), key=Depends(idempotency_key)):
    actor.customer(customer_id)
    def run():
        reward = reward_for(customer_id, db)
        if reward['points_balance'] < payload.points:
            raise HTTPException(409, 'Not enough demo points')
        db.add(DemoRedemption(customer_id=customer_id, **payload.model_dump()))
        db.flush()
        return {'ok': True, 'reward': reward_for(customer_id, db)}
    return service.mutate(db, actor, key, 'redeem_reward', payload.model_dump(), run)


@app.get("/merchant/{merchant_id}/rewards")
def merchant_rewards(merchant_id: int):
    find_merchant(merchant_id)
    result = DATA["ml"]["merchant_rewards"].get(str(merchant_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Merchant rewards summary not found")
    return result


@app.get("/merchant/{merchant_id}/loan-readiness")
def loan_readiness(merchant_id: int):
    find_merchant(merchant_id)
    result = DATA["ml"]["loans"].get(str(merchant_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Loan readiness not found")
    return result


def operational_transactions(db, customer_id=None, merchant_id=None):
    query = select(PaymentSession).where(PaymentSession.status == 'CONFIRMED')
    if customer_id is not None:
        query = query.where(PaymentSession.customer_id == customer_id)
    if merchant_id is not None:
        query = query.where(PaymentSession.merchant_id == merchant_id)
    return [{'id': p.id, 'customer_id': p.customer_id, 'merchant_id': p.merchant_id,
             'customer_name': find_customer(p.customer_id)['name'], 'merchant_name': find_merchant(p.merchant_id)['name'],
             'timestamp': db.scalar(select(PaymentEvent.created_at).where(PaymentEvent.session_id == p.id, PaymentEvent.to_status == 'CONFIRMED')), 'amount': p.amount_paise / 100, 'provenance': 'DEMO_SIMULATED',
             'items': [{'sku': 'Demo simulated payment', 'quantity': 1, 'unit_price': p.amount_paise / 100}]} for p in db.scalars(query)]

@app.get('/customers/{customer_id}/wallet')
def demo_wallet(customer_id: int, db=Depends(get_db), actor=Depends(identity)):
    actor.customer(customer_id)
    find_customer(customer_id)
    spent = sum(p.amount_paise for p in db.scalars(select(PaymentSession).where(PaymentSession.customer_id == customer_id, PaymentSession.status == 'CONFIRMED')))
    return {'currency': 'INR', 'opening_demo_paise': 750000, 'simulated_spend_paise': spent,
            'display_balance_paise': 750000 - spent, 'source': 'Illustrative demo allowance minus confirmed simulated payments; not stored money'}

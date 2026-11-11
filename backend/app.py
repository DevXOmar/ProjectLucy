from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:
    from .upi import is_valid_vpa, payment_intents
except ImportError:
    from upi import is_valid_vpa, payment_intents

DATA_PATH = Path(__file__).resolve().parent / "data" / "precomputed.json"
ORIGINAL_DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
DATA = copy.deepcopy(ORIGINAL_DATA)

app = FastAPI(title="Paytm Grow API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://paytm-grow.vercel.app",
    ],
    allow_origin_regex=r"(https?://localhost(:\d+)?|https?://127\.0\.0\.1(:\d+)?|https://.*\.vercel\.app)$",
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


def reward_for(customer_id: int) -> dict:
    reward = DATA["ml"]["rewards"].get(str(customer_id))
    if not reward:
        raise HTTPException(status_code=404, detail="Reward offer not found")
    result = dict(reward)
    redeemed = sum(item["points"] for item in DATA.get("redemptions", []) if item["customer_id"] == customer_id)
    result["points_balance"] = max(0, int(reward["points_balance"]) - redeemed)
    result["redeemed_points"] = redeemed
    return result


@app.get("/health")
def health():
    return {"status": "ok", "ok": True, "precomputed_at": DATA["ml"]["recomputed_at"], "ml_timings": DATA["ml"]["timings"]}


@app.post("/recompute")
def recompute():
    return {"recomputed_at": DATA["ml"]["recomputed_at"], "timings": DATA["ml"]["timings"], "source": "precomputed snapshot"}


@app.post("/reset-demo")
def reset_demo():
    global DATA
    DATA = copy.deepcopy(ORIGINAL_DATA)
    return {"ok": True, "reset": True, "source": "precomputed snapshot"}


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
def merchant_transactions(merchant_id: int):
    find_merchant(merchant_id)
    return transaction_rows([item for item in DATA["transactions"] if item["merchant_id"] == merchant_id])


@app.get("/customers/{customer_id}/transactions")
def customer_transactions(customer_id: int):
    find_customer(customer_id)
    return transaction_rows([item for item in DATA["transactions"] if item["customer_id"] == customer_id])


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


@app.post("/merchant/{merchant_id}/pricing/actions")
def accept_pricing_action(merchant_id: int, payload: dict):
    find_merchant(merchant_id)
    action = {"merchant_id": merchant_id, "sku": payload.get("sku", "unknown SKU"), "action": payload.get("action", "accept")}
    DATA.setdefault("pricing_actions", []).append(action)
    return {"ok": True, **action}


@app.get("/merchants/{merchant_id}/upi-intent")
def merchant_upi_intent(merchant_id: int, amount: float = 0, note: str | None = None):
    merchant = find_merchant(merchant_id)
    txn_note = note or f"Paytm Grow payment to {merchant['name']}"
    intents = payment_intents(merchant["vpa"], merchant["name"], max(0.0, amount), txn_note)
    return {
        "merchantId": merchant["id"],
        "payeeVpa": merchant["vpa"],
        "payeeVpaValid": is_valid_vpa(merchant["vpa"]),
        "payeeName": merchant["name"],
        "txnAmount": {"value": f"{max(0.0, amount):.2f}", "currency": "INR"},
        "txnNote": txn_note,
        "paytmIntent": intents["paytm_intent"],
        "upiIntent": intents["upi_intent"],
    }


@app.post("/payments")
def create_payment(payload: dict):
    customer_id = int(payload.get("customerId") or payload.get("customer_id") or 0)
    merchant_id = int(payload.get("merchantId") or payload.get("merchant_id") or 0)
    customer = find_customer(customer_id)
    merchant = find_merchant(merchant_id)
    raw_amount = payload.get("txnAmount", payload.get("amount", 0))
    if isinstance(raw_amount, dict):
        raw_amount = raw_amount.get("value", 0)
    amount = round(float(raw_amount or 0), 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    next_id = max((item["id"] for item in DATA["transactions"]), default=0) + 1
    txn_date = datetime.now().replace(microsecond=0).isoformat()
    transaction = {
        "id": next_id,
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "merchant_id": merchant_id,
        "merchant_name": merchant["name"],
        "timestamp": txn_date,
        "amount": amount,
        "items": [{"sku": "QR payment", "quantity": 1, "unit_price": amount}],
    }
    DATA["transactions"].append(transaction)
    order_id = f"PG-{merchant_id}-{next_id:06d}"
    txn_note = str(payload.get("txnNote") or f"Paytm Grow payment to {merchant['name']}")
    intents = payment_intents(merchant["vpa"], merchant["name"], amount, txn_note, order_id=order_id)
    return {
        "ok": True,
        "payment": {
            "orderId": order_id,
            "merchantId": merchant_id,
            "customerId": customer_id,
            "txnId": next_id,
            "txnAmount": {"value": f"{amount:.2f}", "currency": "INR"},
            "txnDate": txn_date,
            "txnStatus": "TXN_SUCCESS",
            "respCode": "01",
            "respMsg": "Txn Success",
            "paymentMode": "UPI",
            "payerVpa": customer["vpa"],
            "payeeVpa": merchant["vpa"],
            "payeeName": merchant["name"],
            "txnNote": txn_note,
            "paytmIntent": intents["paytm_intent"],
            "upiIntent": intents["upi_intent"],
        },
        "transaction": transaction,
        "relationship": relationship_for(customer_id, merchant_id),
    }


@app.get("/rewards/{customer_id}/multiplier")
def reward_multiplier(customer_id: int):
    find_customer(customer_id)
    return reward_for(customer_id)


@app.post("/rewards/{customer_id}/redeem")
def redeem_reward(customer_id: int, payload: dict):
    points = int(payload.get("points", 0))
    if points <= 0:
        raise HTTPException(status_code=400, detail="Points must be greater than zero")
    reward = reward_for(customer_id)
    if reward["points_balance"] < points:
        raise HTTPException(status_code=400, detail="Not enough points")
    DATA.setdefault("redemptions", []).append({"customer_id": customer_id, "offer": str(payload.get("offer", "Wallet reward")), "points": points})
    return {"ok": True, "offer": payload.get("offer", "Wallet reward"), "points_redeemed": points, "reward": reward_for(customer_id)}


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

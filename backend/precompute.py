from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import joinedload

try:
    from .database import SessionLocal
    from .ml_engine import ml_engine
    from .models import Customer, DemoPlatformPrice, Merchant, MerchantSkuPrice, Transaction
    from .seed import seed
    from .upi import payment_intents
except ImportError:
    from database import SessionLocal
    from ml_engine import ml_engine
    from models import Customer, DemoPlatformPrice, Merchant, MerchantSkuPrice, Transaction
    from seed import seed
    from upi import payment_intents

DATA_PATH = Path(__file__).resolve().parent / "data" / "precomputed.json"


def serialize_transaction(transaction: Transaction) -> dict:
    return {
        "id": transaction.id,
        "customer_id": transaction.customer_id,
        "customer_name": transaction.customer.name,
        "merchant_id": transaction.merchant_id,
        "merchant_name": transaction.merchant.name,
        "timestamp": transaction.timestamp.isoformat(),
        "amount": round(transaction.amount, 2),
        "items": [
            {"sku": item.sku, "quantity": item.quantity, "unit_price": item.unit_price}
            for item in transaction.items
        ],
    }


def export_snapshot() -> None:
    seed()
    db = SessionLocal()
    try:
        ml_result = ml_engine.recompute(db)
        customers = db.query(Customer).options(joinedload(Customer.home_merchant)).order_by(Customer.id).all()
        merchants = db.query(Merchant).options(joinedload(Merchant.prices)).order_by(Merchant.id).all()
        transactions = (
            db.query(Transaction)
            .options(joinedload(Transaction.customer), joinedload(Transaction.merchant), joinedload(Transaction.items))
            .order_by(Transaction.id)
            .all()
        )
        platforms = db.query(DemoPlatformPrice).order_by(DemoPlatformPrice.id).all()
        customer_rows = [
            {
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone,
                "locality": customer.locality,
                "vpa": customer.vpa,
                "home_merchant_id": customer.home_merchant_id,
                "home_merchant_name": customer.home_merchant.name if customer.home_merchant else None,
                "churned": customer.churned,
            }
            for customer in customers
        ]
        merchant_rows = [
            {
                "id": merchant.id,
                "name": merchant.name,
                "category": merchant.category,
                "locality": merchant.locality,
                "vpa": merchant.vpa,
                "prices": [{"sku": price.sku, "price": price.price} for price in merchant.prices],
            }
            for merchant in merchants
        ]
        tx_rows = [serialize_transaction(transaction) for transaction in transactions]
        cache = ml_engine.cache
        relationships = {f"{customer_id}:{merchant_id}": value for (customer_id, merchant_id), value in cache.relationships.items()}
        snapshot = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "customers": customer_rows,
            "merchants": merchant_rows,
            "transactions": tx_rows,
            "demo_platform_prices": [
                {"sku": row.sku, "platform": row.platform, "price": row.price, "was_price": row.was_price}
                for row in platforms
            ],
            "ml": {
                "recomputed_at": cache.recomputed_at,
                "timings": cache.timings,
                "relationships": relationships,
                "call_lists": {str(key): value for key, value in cache.call_lists.items()},
                "pulses": {str(key): value for key, value in cache.pulses.items()},
                "pricing": {str(key): value for key, value in cache.pricing.items()},
                "rewards": {str(key): value for key, value in cache.rewards.items()},
                "merchant_rewards": {str(key): value for key, value in cache.merchant_rewards.items()},
                "loans": {str(key): value for key, value in cache.loans.items()},
            },
            "upi_examples": [
                {
                    "merchantId": merchant.id,
                    "payeeVpa": merchant.vpa,
                    "payeeName": merchant.name,
                    "txnAmount": {"value": "120.00", "currency": "INR"},
                    **payment_intents(merchant.vpa, merchant.name, 120, f"Paytm Grow payment to {merchant.name}", order_id=f"PG-{merchant.id}-EXAMPLE"),
                }
                for merchant in merchants[:5]
            ],
            "stats": {
                "merchants": len(merchants),
                "customers": len(customers),
                "categories": len({merchant.category for merchant in merchants}),
                "transactions": len(transactions),
                "category_names": sorted({merchant.category for merchant in merchants}),
                "history_months": 6,
            },
            "ml_result": ml_result,
        }
    finally:
        db.close()
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(snapshot, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {DATA_PATH} ({DATA_PATH.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    export_snapshot()

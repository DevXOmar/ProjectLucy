from __future__ import annotations

import os
import random
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func, inspect

try:
    from .database import Base, SessionLocal, engine
    from .models import Customer, DemoPlatformPrice, Merchant, MerchantSkuPrice, Transaction, TransactionItem
    from .upi import is_valid_vpa, payment_intents, vpa_for_customer, vpa_for_merchant
except ImportError:
    from database import Base, SessionLocal, engine
    from models import Customer, DemoPlatformPrice, Merchant, MerchantSkuPrice, Transaction, TransactionItem
    from upi import is_valid_vpa, payment_intents, vpa_for_customer, vpa_for_merchant

SEED = 20260821
START_DATE = datetime(2026, 2, 1, 9, 0)
END_DATE = datetime(2026, 7, 31, 22, 0)

LOCALITIES = [
    "Madhapur",
    "Kondapur",
    "Gachibowli",
    "Manikonda",
    "Banjara Hills",
    "Himayatnagar",
    "Kukatpally",
    "Nallagandla",
    "Ameerpet",
    "Begumpet",
]

# Six merchant categories, four merchants each. The relationship engine is
# category-agnostic; only the SKU/service list changes per category.
MERCHANTS = [
    ("Sharma Kirana Store", "Kirana"),
    ("Sri Lakshmi General Stores", "Kirana"),
    ("Fresh Basket Mini Mart", "Kirana"),
    ("Hyderabad Daily Needs", "Kirana"),
    ("Sai Ram Medicals", "Chemist"),
    ("Health First Pharmacy", "Chemist"),
    ("Wellness Corner Chemist", "Chemist"),
    ("Green Cross Medicos", "Chemist"),
    ("Style Street Salon", "Salon"),
    ("Urban Trim Studio", "Salon"),
    ("Glow Up Beauty Hub", "Salon"),
    ("Royal Cuts Family Salon", "Salon"),
    ("Charminar FMCG Supply", "Distributor"),
    ("Deccan Wholesale Depot", "Distributor"),
    ("QuickStock Traders", "Distributor"),
    ("Pearl City Distribution", "Distributor"),
    ("Deccan Sports Corner", "Sports Shop"),
    ("Champion Sports House", "Sports Shop"),
    ("PlayOn Sports Depot", "Sports Shop"),
    ("Golconda Fitness Store", "Sports Shop"),
    ("Nizam Fashion House", "Clothing Shop"),
    ("Trend Loom Clothing", "Clothing Shop"),
    ("Charminar Cloth Mart", "Clothing Shop"),
    ("Silk Route Apparel", "Clothing Shop"),
]

# Category-norm prices in INR. Salon entries are services (a price per service,
# no unit), everything else is a stocked SKU.
BASE_SKUS = {
    "Kirana": {
        "Amul milk 1L": 68,
        "Tata Salt 1kg": 28,
        "Maggi 12-pack": 168,
        "Parachute coconut oil 200ml": 92,
        "Colgate 100g": 72,
        "Aashirvaad atta 5kg": 245,
        "Surf Excel 1kg": 132,
        "Good Day biscuits": 35,
        "Red Label tea 250g": 145,
    },
    "Chemist": {
        "Paracetamol strip": 30,
        "Band-aid box": 60,
        "Hand sanitizer 100ml": 75,
        "Thermometer": 240,
        "Multivitamin strip": 155,
        "ORS sachet": 22,
    },
    "Salon": {
        "Haircut": 220,
        "Shave": 90,
        "Head massage": 250,
        "Basic facial": 620,
    },
    "Distributor": {
        "Bulk cooking oil 15L": 2450,
        "Rice 25kg bag": 1650,
        "Wheat flour 25kg bag": 1080,
        "Sugar 25kg bag": 1120,
    },
    "Sports Shop": {
        "Cricket bat": 2200,
        "Badminton racket": 1250,
        "Football": 850,
        "Yoga mat": 720,
        "Gym gloves": 480,
    },
    "Clothing Shop": {
        "Cotton t-shirt": 450,
        "Jeans": 1350,
        "Kurta": 890,
        "Formal shirt": 1050,
        "Saree": 1850,
    },
}

# Fictional comparison platforms invented for this prototype. These are NOT real
# companies and the prices below are illustrative demo pricing, not live data.
# The Market Match view labels them as illustrative and keeps every pricing
# recommendation driven by the real peer-network benchmark instead.
DEMO_PLATFORMS = ["ZipKart", "SpeedBasket", "CityMart Express", "QuickHive"]

FIRST_NAMES = [
    "Aarav",
    "Vivaan",
    "Aditya",
    "Saanvi",
    "Diya",
    "Ananya",
    "Rohan",
    "Priya",
    "Kiran",
    "Meera",
    "Ishaan",
    "Nisha",
]
LAST_NAMES = ["Reddy", "Sharma", "Khan", "Patel", "Iyer", "Gupta", "Rao", "Naidu", "Verma", "Das"]


def reset_db() -> None:
    from pathlib import Path
    operational_path = Path(__file__).resolve().parent / 'lucy.db'
    if os.getenv('LUCY_REBUILD_HISTORY') != 'true' or engine.dialect.name != 'sqlite' or Path(engine.url.database).resolve() == operational_path or inspect(engine).has_table('lucy_schema_version'):
        raise RuntimeError('Historical rebuild requires LUCY_REBUILD_HISTORY=true and a separate SQLite DATABASE_URL; use operational reset for the demo')
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def festival_multiplier(day: datetime) -> float:
    festivals = [
        datetime(2026, 3, 19),
        datetime(2026, 6, 17),
        datetime(2026, 7, 10),
    ]
    return 1.8 if any(abs((day.date() - fest.date()).days) <= 2 for fest in festivals) else 1.0


def day_multiplier(day: datetime) -> float:
    weekend = 1.28 if day.weekday() >= 5 else 1.0
    salary = 1.35 if day.day in (1, 2, 3) else 1.0
    return weekend * salary * festival_multiplier(day)


def choose_visit(day: datetime, rhythm: int, churn_date: datetime | None, rng: random.Random) -> bool:
    if churn_date and day > churn_date + timedelta(days=21):
        return False
    taper = 0.28 if churn_date and day > churn_date else 1.0
    probability = min(0.82, (1 / rhythm) * day_multiplier(day) * taper)
    return rng.random() < probability


def seed_demo_platform_prices(db, rng: random.Random) -> int:
    """Seed illustrative demo pricing, not live data.

    One price per (SKU, fictional platform) pair, computed once here as a small
    randomised offset around the category-norm price and then cached in SQLite so
    the comparison view is stable across reloads.
    """
    rows = 0
    for skus in BASE_SKUS.values():
        for sku, base_price in skus.items():
            for platform in DEMO_PLATFORMS:
                price = round(base_price * rng.uniform(0.88, 1.14), 2)
                was_price = round(price * rng.uniform(1.06, 1.22), 2)
                db.add(DemoPlatformPrice(sku=sku, platform=platform, price=price, was_price=was_price))
                rows += 1
    return rows


def seed() -> None:
    rng = random.Random(SEED)
    reset_db()
    db = SessionLocal()
    try:
        merchants: list[Merchant] = []
        used_vpas: set[str] = set()
        for idx, (name, category) in enumerate(MERCHANTS, start=1):
            vpa = vpa_for_merchant(name)
            if vpa in used_vpas:
                vpa = vpa_for_merchant(name, unique_hint=idx)
            used_vpas.add(vpa)
            merchant = Merchant(
                id=idx,
                name=name,
                category=category,
                locality=LOCALITIES[(idx - 1) % len(LOCALITIES)],
                vpa=vpa,
            )
            db.add(merchant)
            merchants.append(merchant)
            merchant_bias = rng.uniform(0.85, 1.15)
            for sku, base_price in BASE_SKUS[category].items():
                price = round(base_price * merchant_bias * rng.uniform(0.97, 1.03), 2)
                db.add(MerchantSkuPrice(merchant=merchant, sku=sku, price=price))

        platform_rows = seed_demo_platform_prices(db, rng)
        db.flush()

        customers: list[Customer] = []
        customer_profiles: dict[int, dict] = {}
        churn_cutoff = int(400 * 0.15)
        churn_ids = set(rng.sample(range(1, 401), churn_cutoff))
        for customer_id in range(1, 401):
            home = rng.choice(merchants)
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            customer = Customer(
                id=customer_id,
                name=name,
                phone=f"+91 9{rng.randrange(100000000, 999999999)}",
                locality=home.locality,
                vpa=vpa_for_customer(name, customer_id),
                home_merchant_id=home.id,
                churned=customer_id in churn_ids,
            )
            db.add(customer)
            customers.append(customer)
            # Secondary merchants are drawn across all categories, so a customer's
            # history can mix a kirana, a chemist and a salon.
            secondaries = rng.sample([m for m in merchants if m.id != home.id], rng.randint(0, 2))
            rhythm = rng.choices([3, 5, 7, 14, 30], weights=[20, 28, 26, 18, 8], k=1)[0]
            churn_date = rng.choice([datetime(2026, 4, 10), datetime(2026, 5, 12), datetime(2026, 6, 8)]) if customer_id in churn_ids else None
            customer_profiles[customer_id] = {
                "merchants": [home] + secondaries,
                "rhythm": rhythm,
                "churn_date": churn_date,
            }

        db.flush()

        transaction_id = 1
        day = START_DATE
        while day <= END_DATE:
            for customer in customers:
                profile = customer_profiles[customer.id]
                if not choose_visit(day, profile["rhythm"], profile["churn_date"], rng):
                    continue
                merchant = rng.choices(profile["merchants"], weights=[78, 16, 6][: len(profile["merchants"])], k=1)[0]
                prices = list(merchant.prices)
                basket_size = rng.choices([1, 2, 3, 4, 5], weights=[28, 34, 22, 11, 5], k=1)[0]
                basket = rng.sample(prices, min(basket_size, len(prices)))
                hour = rng.choices([9, 12, 18, 20], weights=[18, 22, 36, 24], k=1)[0]
                timestamp = day.replace(hour=hour, minute=rng.randrange(0, 60), second=0)
                transaction = Transaction(
                    id=transaction_id,
                    customer_id=customer.id,
                    merchant_id=merchant.id,
                    timestamp=timestamp,
                    amount=0,
                )
                total = 0.0
                db.add(transaction)
                for price in basket:
                    qty = rng.choices([1, 2, 3], weights=[72, 22, 6], k=1)[0]
                    total += price.price * qty
                    db.add(
                        TransactionItem(
                            transaction=transaction,
                            sku=price.sku,
                            quantity=qty,
                            unit_price=price.price,
                        )
                    )
                transaction.amount = round(total, 2)
                transaction_id += 1
            day += timedelta(days=1)

        db.commit()

        total = db.query(func.count(Transaction.id)).scalar() or 0
        first_tx = db.query(func.min(Transaction.timestamp)).scalar()
        last_tx = db.query(func.max(Transaction.timestamp)).scalar()
        by_day = Counter()
        for (timestamp,) in db.query(Transaction.timestamp).all():
            by_day["weekend" if timestamp.weekday() >= 5 else "weekday"] += 1
        weekend_days = sum(1 for i in range((END_DATE.date() - START_DATE.date()).days + 1) if (START_DATE + timedelta(days=i)).weekday() >= 5)
        weekday_days = ((END_DATE.date() - START_DATE.date()).days + 1) - weekend_days
        weekend_avg = by_day["weekend"] / weekend_days
        weekday_avg = by_day["weekday"] / weekday_days
        ratio = weekend_avg / weekday_avg
        by_category = Counter(merchant.category for merchant in merchants)
        print("Historical seed complete for Project Lucy")
        print(f"Total transactions: {total}")
        print(f"Date range: {first_tx.date()} to {last_tx.date()}")
        print(f"Weekend vs weekday volume ratio: {ratio:.2f}x")
        print(f"Churn count: {len(churn_ids)} customers")
        print(f"Merchants: {len(merchants)} across {len(by_category)} categories -> {dict(by_category)}")
        print(f"Illustrative demo platform prices seeded: {platform_rows} rows across {len(DEMO_PLATFORMS)} demo platforms")

        # Preview synthetic UPI syntax; these are not authorized payment destinations.
        print("Synthetic UPI syntax previews (no live handoff):")
        for merchant in (merchants[0], merchants[8], merchants[16]):
            intents = payment_intents(
                merchant.vpa,
                merchant.name,
                120.0,
                f"Lucy synthetic preview to {merchant.name}",
                order_id="LUCY-DEMO-0001",
            )
            print(f"  {merchant.name} [{merchant.category}] vpa_valid={is_valid_vpa(merchant.vpa)}")
            print(f"    {intents['paytm_intent']}")
            print(f"    {intents['upi_intent']}")
        invalid = [merchant.name for merchant in merchants if not is_valid_vpa(merchant.vpa)]
        print(f"Merchant VPAs failing the NPCI handle format: {invalid or 'none'}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

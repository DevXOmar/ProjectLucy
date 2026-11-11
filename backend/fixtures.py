"""Deterministic operational fixtures; never recompute the ML snapshot."""
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from .models import Customer, Merchant
from .domain_models import SchemaVersion, MerchantOffer, Inventory

# Fixed future windows keep reset predictable. Expiry is enforced by services.
EXPIRY = '2027-12-31T23:59:59+00:00'
OFFERS = [
    ('projector-buy', 17, 'projector-01', 'Projector purchase', 'PURCHASE', 1800000, 2, {}),
    ('projector-rent', 17, 'projector-rental-01', 'Movie night projector rental', 'RENTAL', 90000, 1,
     {'window_start': '2026-11-01T00:00:00+00:00', 'window_end': EXPIRY, 'duration_hours': 24, 'return_required': True, 'deposit_paise': 0, 'condition': 'Merchant-attested working unit; return next day'}),
    ('snacks-surplus', 1, 'snack-box', 'Eligible sealed snack box', 'SURPLUS', 7000, 10,
     {'merchant_attested': True, 'sealed': True, 'eligible_until': EXPIRY}),
    ('drinks-ten', 2, 'drink-bottle', 'Drinks group quantity offer', 'PURCHASE', 6000, 30,
     {'min_quantity': 10, 'quantity_price_threshold': 10}),
]

def seed_operational(db, snapshot):
    for m in snapshot['merchants']:
        if not db.get(Merchant, m['id']):
            db.add(Merchant(id=m['id'], name=m['name'], category=m['category'], locality=m['locality'], vpa=m['vpa']))
    db.flush()
    for c in snapshot['customers']:
        if not db.get(Customer, c['id']):
            db.add(Customer(**{k: c[k] for k in ['id','name','phone','locality','vpa','home_merchant_id','churned']}))
    db.flush()
    for id, mid, product, title, kind, price, count, terms in OFFERS:
        if not db.get(MerchantOffer, id):
            db.add(MerchantOffer(id=id, merchant_id=mid, product_id=product, title=title, kind=kind, price_paise=price,
                                 expires_at=EXPIRY, terms={'permitted_customer_ids': [6,7], 'merchant_consent': True, **terms}))
            db.flush()
            db.add(Inventory(id=f'stock-{id}', offer_id=id, available=count))
    if not db.get(SchemaVersion, 1):
        db.add(SchemaVersion(version=1))

def initialize(snapshot):
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            connection.execute(text('BEGIN IMMEDIATE'))
        else:
            connection.execute(text('SELECT pg_advisory_xact_lock(202611110)'))
        Base.metadata.create_all(connection)
        with Session(bind=connection) as db:
            versions = list(db.scalars(select(SchemaVersion.version)))
            if any(v != 1 for v in versions):
                raise RuntimeError('Unsupported operational schema version; explicit migration required')
            seed_operational(db, snapshot)
            db.flush()

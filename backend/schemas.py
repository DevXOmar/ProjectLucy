from datetime import datetime

from pydantic import BaseModel


class SkuPriceOut(BaseModel):
    sku: str
    price: float


class MerchantOut(BaseModel):
    id: int
    name: str
    category: str
    locality: str
    # Synthetic demo VPA; preview only, never an authorized payment destination.
    vpa: str = ""
    prices: list[SkuPriceOut] = []


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str
    locality: str
    vpa: str = ""
    home_merchant_id: int
    home_merchant_name: str | None = None
    churned: bool


class TransactionItemOut(BaseModel):
    sku: str
    quantity: int
    unit_price: float


class TransactionOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    merchant_id: int
    merchant_name: str
    timestamp: datetime
    amount: float
    items: list[TransactionItemOut]


class DemoStatsOut(BaseModel):
    """Real counts from the local seed data, used by the landing page stats strip."""

    merchants: int
    customers: int
    categories: int
    transactions: int
    category_names: list[str] = []
    history_months: int = 6

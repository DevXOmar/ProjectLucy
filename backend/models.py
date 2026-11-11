from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from .database import Base
except ImportError:
    from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    locality: Mapped[str] = mapped_column(String, nullable=False)
    # Synthetic demo payer handle; not payment credentials.
    vpa: Mapped[str] = mapped_column(String, nullable=False, default="")
    home_merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    churned: Mapped[bool] = mapped_column(default=False)

    home_merchant = relationship("Merchant", back_populates="home_customers")
    transactions = relationship("Transaction", back_populates="customer")


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    locality: Mapped[str] = mapped_column(String, nullable=False)
    # Synthetic demo handle. Structural validity does not authorize payment.
    vpa: Mapped[str] = mapped_column(String, nullable=False, default="")

    home_customers = relationship("Customer", back_populates="home_merchant")
    prices = relationship("MerchantSkuPrice", back_populates="merchant")
    transactions = relationship("Transaction", back_populates="merchant")


class MerchantSkuPrice(Base):
    __tablename__ = "merchant_sku_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    merchant = relationship("Merchant", back_populates="prices")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    timestamp: Mapped[DateTime] = mapped_column(DateTime, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    customer = relationship("Customer", back_populates="transactions")
    merchant = relationship("Merchant", back_populates="transactions")
    items = relationship("TransactionItem", back_populates="transaction")


class TransactionItem(Base):
    __tablename__ = "transaction_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)

    transaction = relationship("Transaction", back_populates="items")


class RewardRedemption(Base):
    __tablename__ = "reward_redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    offer: Mapped[str] = mapped_column(String, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[DateTime] = mapped_column(DateTime, index=True)


class DemoPlatformPrice(Base):
    """Illustrative demo pricing, not live data.

    ZipKart, SpeedBasket, CityMart Express and QuickHive are fictional platforms
    invented for this prototype. Their prices are seeded offsets around the
    category-norm price for each SKU so the Market Match comparison view has
    something to rank. They are never used by the pricing recommendation logic,
    which reads only the real peer-network benchmark.
    """

    __tablename__ = "demo_platform_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String, nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    was_price: Mapped[float] = mapped_column(Float, nullable=False)

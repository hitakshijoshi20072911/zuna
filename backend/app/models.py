from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Table, Column, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


wishlist_items = Table(
    "wishlist_items",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    products: Mapped[list["Product"]] = relationship(back_populates="owner")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    maker: Mapped[str] = mapped_column(String(120))
    seller: Mapped[str] = mapped_column(String(160))
    region: Mapped[str] = mapped_column(String(100), default="India")
    price: Mapped[int] = mapped_column(Integer)
    cost: Mapped[int] = mapped_column(Integer, default=0)
    image: Mapped[str] = mapped_column(String(500))
    offers: Mapped[bool] = mapped_column(Boolean, default=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    tags: Mapped[str] = mapped_column(Text, default="")
    added_order: Mapped[int] = mapped_column(Integer, default=0)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    age: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text)
    story: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User | None] = relationship(back_populates="products")


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    offered_price: Mapped[int] = mapped_column(Integer)
    counter_price: Mapped[int | None] = mapped_column(Integer)
    accepted_price: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    product: Mapped[Product] = relationship()
    events: Mapped[list["OfferEvent"]] = relationship(back_populates="offer", cascade="all, delete-orphan", order_by="OfferEvent.created_at")


class OfferEvent(Base):
    __tablename__ = "offer_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    offer: Mapped[Offer] = relationship(back_populates="events")
    actor: Mapped[User] = relationship()


class CollaborationOpportunity(Base):
    __tablename__ = "collaboration_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(100), default="")
    collaboration_type: Mapped[str] = mapped_column(String(100))
    brief: Mapped[str] = mapped_column(Text)
    terms: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    product: Mapped[Product] = relationship()
    seller: Mapped[User | None] = relationship()


class CollaborationRequest(Base):
    __tablename__ = "collaboration_requests"
    __table_args__ = (UniqueConstraint("opportunity_id", "creator_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("collaboration_opportunities.id", ondelete="CASCADE"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    opportunity: Mapped[CollaborationOpportunity] = relationship()
    creator: Mapped[User] = relationship()


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("collaboration_requests.id", ondelete="CASCADE"), unique=True)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    request: Mapped[CollaborationRequest] = relationship()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), unique=True)
    referral_id: Mapped[int | None] = mapped_column(ForeignKey("referrals.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    payment_status: Mapped[str] = mapped_column(String(24), default="pending")
    payment_method: Mapped[str | None] = mapped_column(String(20), default="razorpay")
    size: Mapped[str | None] = mapped_column(String(30))
    delivery_name: Mapped[str | None] = mapped_column(String(100))
    delivery_phone: Mapped[str | None] = mapped_column(String(30))
    delivery_address: Mapped[str | None] = mapped_column(Text)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    offer: Mapped[Offer] = relationship()
    referral: Mapped[Referral | None] = relationship()


class ProductOrder(Base):
    __tablename__ = "product_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    payment_method: Mapped[str] = mapped_column(String(20))
    payment_status: Mapped[str] = mapped_column(String(24), default="pending")
    size: Mapped[str | None] = mapped_column(String(30))
    delivery_name: Mapped[str] = mapped_column(String(100))
    delivery_phone: Mapped[str] = mapped_column(String(30))
    delivery_address: Mapped[str] = mapped_column(Text)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    product: Mapped[Product] = relationship()

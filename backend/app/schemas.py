from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in {"buyer", "seller", "creator"}:
            raise ValueError("Role must be buyer, seller, or creator.")
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: int
    name: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class ProductWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=100)
    price: int = Field(gt=0, le=10_000_000)
    cost: int = Field(ge=0, le=10_000_000)
    stockQty: int = Field(ge=0, le=1_000_000)
    age: int = Field(ge=0, le=10_000)
    image: str = Field(min_length=1, max_length=500)
    offers: bool
    description: str = Field(min_length=1, max_length=3000)


class OfferCreate(BaseModel):
    amount: int = Field(gt=0, le=10_000_000)


class OfferCounter(BaseModel):
    amount: int = Field(gt=0, le=10_000_000)


class WishlistUpdate(BaseModel):
    saved: bool


class OpportunityCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=80)
    collaboration_type: str = Field(min_length=1, max_length=100)
    brief: str = Field(min_length=10, max_length=3000)
    terms: str = Field(min_length=1, max_length=1000)


class PricingRequest(BaseModel):
    unit_cost: int = Field(gt=0, le=10_000_000)
    target_margin_percent: float = Field(gt=0, le=75)
    inventory_age_days: int = Field(ge=0, le=10_000)
    demand_index: int = Field(ge=0, le=100)


class CheckoutCreate(BaseModel):
    accepted_offer_id: int = Field(gt=0)
    referral_code: str | None = Field(default=None, min_length=1, max_length=64)
    size: str | None = Field(default=None, min_length=1, max_length=30)
    payment_method: Literal["razorpay", "cod"] = "razorpay"
    delivery_name: str | None = Field(default=None, min_length=1, max_length=100)
    delivery_phone: str | None = Field(default=None, min_length=7, max_length=30)
    delivery_address: str | None = Field(default=None, min_length=8, max_length=1000)

    @field_validator("delivery_name", "delivery_phone", "delivery_address")
    @classmethod
    def clean_checkout_details(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Delivery details cannot be blank.")
        return value

class ProductCheckoutCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=80)
    size: str | None = Field(default=None, min_length=1, max_length=30)
    payment_method: Literal["razorpay", "cod"]
    delivery_name: str = Field(min_length=1, max_length=100)
    delivery_phone: str = Field(min_length=7, max_length=30)
    delivery_address: str = Field(min_length=8, max_length=1000)

    @field_validator("delivery_name", "delivery_phone", "delivery_address")
    @classmethod
    def clean_delivery_details(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Delivery details are required.")
        return value


class PaymentVerify(BaseModel):
    order_id: str = Field(min_length=1, max_length=80)
    razorpay_order_id: str = Field(min_length=1, max_length=80)
    razorpay_payment_id: str = Field(min_length=1, max_length=80)
    razorpay_signature: str = Field(min_length=1, max_length=256)

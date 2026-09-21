"""Pydantic row schemas for the customer intelligence entity model.

These mirror the tables in docs/data_dictionary.md and exist so the
generator and the data-quality suite validate against one shared
definition instead of two copies drifting apart.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class AcquisitionChannel(str, Enum):
    ORGANIC = "organic"
    PAID_SEARCH = "paid_search"
    SOCIAL = "social"
    AFFILIATE = "affiliate"
    EMAIL = "email"
    REFERRAL = "referral"


class LoyaltyPlan(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class OrderStatus(str, Enum):
    COMPLETED = "completed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class InteractionType(str, Enum):
    LOGIN = "login"
    PAGE_VIEW = "page_view"
    ADD_TO_CART = "add_to_cart"
    EMAIL_OPEN = "email_open"
    EMAIL_CLICK = "email_click"


class InteractionChannel(str, Enum):
    WEB = "web"
    MOBILE_APP = "mobile_app"
    EMAIL = "email"


class SupportCategory(str, Enum):
    BILLING = "billing"
    SHIPPING = "shipping"
    PRODUCT_ISSUE = "product_issue"
    CANCELLATION_REQUEST = "cancellation_request"
    GENERAL = "general"


class Customer(BaseModel):
    customer_id: str
    signup_date: date
    country: str
    acquisition_channel: AcquisitionChannel
    plan: LoyaltyPlan


class Product(BaseModel):
    product_id: str
    category: str
    price: float = Field(gt=0)


class Order(BaseModel):
    order_id: str
    customer_id: str
    order_date: datetime
    product_id: str
    quantity: int = Field(gt=0)
    amount: float = Field(ge=0)
    discount: float = Field(ge=0, le=1)
    status: OrderStatus


class Interaction(BaseModel):
    interaction_id: str
    customer_id: str
    event_time: datetime
    event_type: InteractionType
    channel: InteractionChannel


class SupportTicket(BaseModel):
    ticket_id: str
    customer_id: str
    created_at: datetime
    category: SupportCategory


class Prediction(BaseModel):
    customer_id: str
    model_version: str
    churn_probability: float = Field(ge=0, le=1)
    predicted_clv: float = Field(ge=0)
    prediction_date: date

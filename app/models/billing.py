from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String

from .base import Base, get_utc_now


class Subscription(Base):
    """A prepaid subscription period bought through PayPhone.

    One row per checkout. The row becomes ``active`` only after PayPhone confirms
    the transaction; access lasts until ``period_end``.
    """

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan = Column(String(30), nullable=False)
    months = Column(Integer, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(String(20), nullable=False, default="pending", index=True)
    provider = Column(String(20), nullable=False, default="payphone")
    client_transaction_id = Column(String(64), nullable=False, unique=True)
    provider_transaction_id = Column(String(64), nullable=True)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True, index=True)
    provider_response = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False
    )

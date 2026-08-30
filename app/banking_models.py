"""Pydantic contracts for customer profiles produced by the banking ETL."""

from datetime import date
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    StringConstraints,
    model_validator,
)

CustomerId = StrictInt | StrictStr
Money = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonEmptyText = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)]


class TransactionModel(BaseModel):
    """A validated transaction belonging to one customer."""

    model_config = ConfigDict(extra="forbid", strict=True)

    operation_date: date
    transaction_type: NonEmptyText
    amount: Money
    channel: NonEmptyText | None = None
    category: NonEmptyText | None = None


class DefaultRecordModel(BaseModel):
    """A point-in-time credit-default status for one customer."""

    model_config = ConfigDict(extra="forbid", strict=True)

    reference_date: date
    status: StrictInt | NonEmptyText
    status_description: NonEmptyText | None = None


class ProductHoldingModel(BaseModel):
    """A banking product held by a customer."""

    model_config = ConfigDict(extra="forbid", strict=True)

    product: NonEmptyText
    opening_date: date | None = None
    closure_date: date | None = None

    @model_validator(mode="after")
    def closure_cannot_precede_opening(self) -> "ProductHoldingModel":
        if (
            self.opening_date is not None
            and self.closure_date is not None
            and self.closure_date < self.opening_date
        ):
            raise ValueError("closure_date cannot be earlier than opening_date")
        return self


class CustomerProfileModel(BaseModel):
    """The validated output returned by ``get_customer_profile`` in the ETL layer."""

    model_config = ConfigDict(extra="forbid", strict=True)

    customer_id: CustomerId
    current_balance: Money
    total_transaction_amount: Money
    transactions: list[TransactionModel] = Field(default_factory=list)
    default_history: list[DefaultRecordModel] = Field(default_factory=list)
    products: list[ProductHoldingModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def total_must_match_transactions(self) -> "CustomerProfileModel":
        calculated_total = sum(transaction.amount for transaction in self.transactions)
        if abs(self.total_transaction_amount - calculated_total) > 1e-9:
            raise ValueError(
                "total_transaction_amount must equal the sum of transaction amounts"
            )
        return self

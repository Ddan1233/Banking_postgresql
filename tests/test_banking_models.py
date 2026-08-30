from datetime import date

import pytest
from pydantic import ValidationError

from app.banking_models import CustomerProfileModel, ProductHoldingModel


def valid_profile() -> dict[str, object]:
    return {
        "customer_id": "C-1001",
        "current_balance": 1250.5,
        "total_transaction_amount": -15.5,
        "transactions": [
            {
                "operation_date": date(2025, 1, 15),
                "transaction_type": "debit card",
                "amount": -20.0,
                "channel": "internet",
                "category": "food&groceries",
            },
            {
                "operation_date": date(2025, 1, 16),
                "transaction_type": "bank transfer",
                "amount": 4.5,
            },
        ],
        "default_history": [
            {
                "reference_date": date(2025, 1, 31),
                "status": 0,
                "status_description": "bonis",
            }
        ],
        "products": [
            {
                "product": "Current Account",
                "opening_date": date(2020, 1, 1),
            }
        ],
    }


def test_customer_profile_accepts_a_consistent_etl_result() -> None:
    profile = CustomerProfileModel.model_validate(valid_profile())

    assert profile.customer_id == "C-1001"
    assert profile.transactions[0].amount == -20.0
    assert profile.default_history[0].status == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("current_balance", "1250.50"),
        ("current_balance", True),
        ("total_transaction_amount", float("inf")),
    ],
)
def test_customer_profile_rejects_non_numeric_or_non_finite_money(
    field: str, value: object
) -> None:
    profile = valid_profile()
    profile[field] = value

    with pytest.raises(ValidationError):
        CustomerProfileModel.model_validate(profile)


def test_customer_profile_rejects_non_standardized_dates_and_wrong_totals() -> None:
    profile = valid_profile()
    profile["transactions"] = [
        {
            "operation_date": "2025-01-15",
            "transaction_type": "debit card",
            "amount": -20.0,
        }
    ]
    profile["total_transaction_amount"] = -20.0

    with pytest.raises(ValidationError):
        CustomerProfileModel.model_validate(profile)

    profile = valid_profile()
    profile["total_transaction_amount"] = 999.0
    with pytest.raises(ValidationError, match="must equal the sum"):
        CustomerProfileModel.model_validate(profile)


def test_product_rejects_a_closure_before_the_opening_date() -> None:
    with pytest.raises(ValidationError, match="cannot be earlier"):
        ProductHoldingModel(
            product="Credit Card",
            opening_date=date(2024, 2, 1),
            closure_date=date(2024, 1, 1),
        )

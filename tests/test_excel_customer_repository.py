from pathlib import Path

import pytest
from fastapi import HTTPException

from app.excel_customer_repository import ExcelCustomerRepository


def test_repository_joins_all_excel_sheets_for_customer_two() -> None:
    profile = ExcelCustomerRepository(Path("Data.xlsx")).get_customer_profile(2)

    assert profile.customer_id == 2
    assert profile.current_balance == 400.0
    assert profile.total_transaction_amount == -350.0
    assert len(profile.transactions) == 2
    assert len(profile.default_history) == 3
    assert profile.default_history[-1].status_description == "bonis"
    assert len(profile.products) == 3
    assert profile.customer_data is not None
    assert profile.customer_data.region == "Toscana"
    assert profile.regional_context is not None
    assert profile.regional_context.delinquency_rate == 7.0


def test_repository_returns_404_for_unknown_customer() -> None:
    with pytest.raises(HTTPException) as error:
        ExcelCustomerRepository(Path("Data.xlsx")).get_customer_profile(99999)

    assert error.value.status_code == 404

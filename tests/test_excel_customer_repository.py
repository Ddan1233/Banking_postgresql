import pytest
from fastapi import HTTPException

from app.excel_customer_repository import ExcelCustomerRepository


def sample_sheets() -> dict[str, list[dict[str, str]]]:
    """Minimal workbook content that mirrors the Excel sheet contracts."""

    return {
        "MasterData": [{
            "customer ID": "2", "DATE OF BIRTH": "33208", "REGION": "Toscana",
            "ADDRESS": "Via Giuseppe Verdi 21", "SEX": "F",
            "TYPE OF CUSTOMER LEV 1 ": "IND", "TYPE OF CUSTOMER LEV 2": "LOW",
        }],
        "Products": [{
            "customer ID": "2", "PRODUCTS OWNED": "Current Account",
            "DATE OPENING": "2000", "DATE CLOSURE": "",
        }],
        "Liquidity": [
            {"customer ID": "2", "reference date": "45961", "balance €": "500"},
            {"customer ID": "2", "reference date": "45991", "balance €": "400"},
        ],
        "Transactions": [
            {
                "customer ID": "2", "operation date": "45932", "type": "credit card",
                "category": "food&groceries", "channel ": "NA", "amount": "-200",
            },
            {
                "customer ID": "2", "operation date": "45977", "type": "credit card",
                "category": "food&groceries", "channel ": "NA", "amount": "-150",
            },
        ],
        "Investments": [],
        "Default": [{
            "customer ID": "2", "reference date": "45961", "status code": "20",
            "status desc": "default 30gg",
        }],
        "SocioDemographic": [{
            "REGION": "Toscana", "Squared kilometers": "300000",
            "Deliquency rates": "7",
        }],
    }


def test_repository_joins_all_excel_sheets_for_customer_two(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = ExcelCustomerRepository("not-needed-in-this-test.xlsx")
    monkeypatch.setattr(repository, "_read_sheets", sample_sheets)
    profile = repository.get_customer_profile(2)

    assert profile.customer_id == 2
    assert profile.current_balance == 400.0
    assert profile.total_transaction_amount == -350.0
    assert len(profile.transactions) == 2
    assert len(profile.default_history) == 1
    assert profile.default_history[-1].status_description == "default 30gg"
    assert len(profile.products) == 1
    assert profile.customer_data is not None
    assert profile.customer_data.region == "Toscana"
    assert profile.regional_context is not None
    assert profile.regional_context.delinquency_rate == 7.0


def test_repository_returns_404_for_unknown_customer(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = ExcelCustomerRepository("not-needed-in-this-test.xlsx")
    monkeypatch.setattr(repository, "_read_sheets", sample_sheets)
    with pytest.raises(HTTPException) as error:
        repository.get_customer_profile(99999)

    assert error.value.status_code == 404

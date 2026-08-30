"""HTTP API contract tests for the banking application."""

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_exposes_the_customer_profile_and_risk_report_endpoints() -> None:
    schema = TestClient(app).get("/openapi.json").json()

    assert set(schema["paths"]) == {"/generate-risk-report", "/customer-profiles/{customer_id}"}
    assert schema["paths"]["/generate-risk-report"]["post"]["tags"] == [
        "banking-risk"
    ]


def test_risk_report_returns_404_when_customer_is_not_in_excel() -> None:
    response = TestClient(app).post(
        "/generate-risk-report", json={"customer_id": 99999}
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Customer 99999 was not found in the Excel workbook."
    }

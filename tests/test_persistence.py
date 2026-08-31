from datetime import date

from app.banking_agents.generator import ProductRecommendation, RiskReport
from app.banking_agents.validator import ValidationResult
from app.banking_models import CustomerProfileModel
from app.banking_orchestrator import RiskReportResult
from app.persistence import BankingStorage, CustomerProfileRecord, RiskReportRecord


def test_storage_persists_the_etl_profile_and_agent_report() -> None:
    storage = BankingStorage("sqlite+pysqlite:///:memory:")
    profile = CustomerProfileModel(
        customer_id=2,
        current_balance=400.0,
        total_transaction_amount=0.0,
        default_history=[
            {
                "reference_date": date(2025, 10, 31),
                "status": 20,
                "status_description": "default 30gg",
            }
        ],
    )
    result = RiskReportResult(
        report=RiskReport(
            customer_id="2",
            risk_level="high",
            risk_summary="Default history is present.",
            key_risk_factors=["Default 30gg"],
            product_recommendations=[
                ProductRecommendation(
                    product_name="Savings Account",
                    category="savings",
                    rationale="Supports a liquidity buffer.",
                )
            ],
        ),
        validation=ValidationResult(is_valid=True),
        refinement_count=0,
    )
    observability = {"trace_id": "test-trace", "total_duration_ms": 12.5}

    storage.save_customer_profile(profile)
    report_id = storage.save_risk_report(profile, result, observability, "gpt-4.1-mini")
    observability["report_persistence_ms"] = 1.5
    storage.update_report_observability(report_id, observability)

    with storage._sessions() as session:
        customer = session.get(CustomerProfileRecord, "2")
        report = session.get(RiskReportRecord, report_id)

    assert customer is not None
    assert customer.profile_data["current_balance"] == 400.0
    assert report is not None
    assert report.risk_level == "high"
    assert report.observability_data["report_persistence_ms"] == 1.5

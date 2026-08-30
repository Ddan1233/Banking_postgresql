from datetime import date
from unittest.mock import Mock

from app.banking_agents.generator import (
    GeneratorAgent,
    ProductRecommendation,
    RiskReport,
)
from app.banking_agents.refiner import RefinerAgent
from app.banking_agents.validator import ValidatorAgent
from app.banking_models import CustomerProfileModel
from app.banking_orchestrator import BankingRiskOrchestrator


def defaulted_profile() -> CustomerProfileModel:
    return CustomerProfileModel(
        customer_id="C-2001",
        current_balance=100.0,
        total_transaction_amount=0.0,
        transactions=[],
        default_history=[
            {
                "reference_date": date(2025, 1, 31),
                "status": 1,
                "status_description": "defaulted loan",
            }
        ],
        products=[],
    )


def invalid_credit_report() -> RiskReport:
    return RiskReport(
        customer_id="C-2001",
        risk_level="high",
        risk_summary="A report draft.",
        key_risk_factors=["Default history."],
        product_recommendations=[
            ProductRecommendation(
                product_name="Personal Loan", category="credit", rationale="Draft error."
            )
        ],
    )


def test_validator_prohibits_credit_recommendations_for_default_history() -> None:
    result = ValidatorAgent().validate(defaulted_profile(), invalid_credit_report())

    assert result.is_valid is False
    assert result.errors == [
        "Credit recommendations are prohibited because the customer has a default "
        "history: Personal Loan."
    ]


def test_refiner_removes_prohibited_credit_recommendations() -> None:
    profile = defaulted_profile()
    validator = ValidatorAgent()
    refined = RefinerAgent(use_openai=False).refine(
        profile, invalid_credit_report(), validator.validate(profile, invalid_credit_report())
    )

    assert [item.category for item in refined.product_recommendations] == ["savings"]
    assert validator.validate(profile, refined).is_valid is True


def test_orchestrator_runs_generator_validator_and_refiner_until_compliant() -> None:
    profile = defaulted_profile()
    generator = Mock()
    generator.generate.return_value = invalid_credit_report()
    validator = ValidatorAgent()
    refiner = RefinerAgent(use_openai=False)

    result = BankingRiskOrchestrator(
        generator=generator, validator=validator, refiner=refiner
    ).create_risk_report(profile)

    assert result.validation.is_valid is True
    assert result.refinement_count == 1
    assert generator.generate.call_count == 1
    assert all(item.category != "credit" for item in result.report.product_recommendations)


def test_generator_local_fallback_receives_the_validated_profile() -> None:
    report = GeneratorAgent(use_openai=False).generate(defaulted_profile())

    assert report.customer_id == "C-2001"
    assert report.risk_level == "high"
    assert all(item.category != "credit" for item in report.product_recommendations)

"""Business-rule validation for banking risk-report drafts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.banking_agents.generator import RiskReport
from app.banking_models import CustomerProfileModel


class ValidationResult(BaseModel):
    """Business-rule outcome returned to the orchestrator and refiner."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    errors: list[str] = Field(default_factory=list)


class ValidatorAgent:
    """Validate recommendations using deterministic, auditable banking rules."""

    _CREDIT_WORDS = ("credit", "loan", "overdraft", "mortgage", "card")
    _DEFAULT_STATUS_CODES = {20, 40}

    def validate(
        self, profile: CustomerProfileModel, report: RiskReport
    ) -> ValidationResult:
        errors: list[str] = []
        if report.customer_id != str(profile.customer_id):
            errors.append("Report customer_id does not match the validated customer profile.")

        if self._has_default_history(profile):
            credit_products = [
                recommendation.product_name
                for recommendation in report.product_recommendations
                if recommendation.category == "credit"
                or any(
                    word in recommendation.product_name.lower()
                    for word in self._CREDIT_WORDS
                )
            ]
            if credit_products:
                errors.append(
                    "Credit recommendations are prohibited because the customer has "
                    f"a default history: {', '.join(credit_products)}."
                )
        return ValidationResult(is_valid=not errors, errors=errors)

    @staticmethod
    def _has_default_history(profile: CustomerProfileModel) -> bool:
        return any(
            (
                isinstance(record.status, int)
                and record.status in ValidatorAgent._DEFAULT_STATUS_CODES
            )
            or (isinstance(record.status, str) and "default" in record.status.lower())
            or "default" in (record.status_description or "").lower()
            for record in profile.default_history
        )

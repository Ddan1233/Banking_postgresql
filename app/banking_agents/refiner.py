"""OpenAI-backed correction of reports rejected by banking business rules."""

from __future__ import annotations

import json

from openai import OpenAI

from app.banking_agents.generator import ProductRecommendation, RiskReport
from app.banking_agents.validator import ValidationResult
from app.banking_models import CustomerProfileModel
from app.core.config import settings


class RefinerAgent:
    """Correct a draft in response to validator errors, preserving its structure."""

    def __init__(
        self, client: OpenAI | None = None, use_openai: bool | None = None
    ) -> None:
        self._client = client
        self._use_openai = use_openai

    def refine(
        self,
        profile: CustomerProfileModel,
        report: RiskReport,
        feedback: ValidationResult,
    ) -> RiskReport:
        if feedback.is_valid:
            return report
        if self._client is not None or (
            self._use_openai is not False and settings.openai_api_key
        ):
            return self._refine_with_openai(profile, report, feedback)
        return self._refine_locally(report, feedback)

    def _refine_with_openai(
        self,
        profile: CustomerProfileModel,
        report: RiskReport,
        feedback: ValidationResult,
    ) -> RiskReport:
        client = self._client or OpenAI(api_key=settings.openai_api_key)
        response = client.responses.create(
            model=settings.openai_model,
            instructions=(
                "You correct banking risk reports. Return a revised report that resolves "
                "every validator error. Never recommend credit when default history exists."
            ),
            input=json.dumps(
                {
                    "profile": profile.model_dump(mode="json"),
                    "draft_report": report.model_dump(mode="json"),
                    "validator_errors": feedback.errors,
                }
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "refined_risk_report",
                    "strict": True,
                    "schema": RiskReport.model_json_schema(),
                }
            },
        )
        return RiskReport.model_validate_json(response.output_text)

    @staticmethod
    def _refine_locally(report: RiskReport, feedback: ValidationResult) -> RiskReport:
        recommendations = [
            recommendation
            for recommendation in report.product_recommendations
            if recommendation.category != "credit"
            and not any(
                word in recommendation.product_name.lower()
                for word in ("credit", "loan", "overdraft", "mortgage", "card")
            )
        ]
        if not recommendations:
            recommendations.append(
                ProductRecommendation(
                    product_name="Savings Account",
                    category="savings",
                    rationale="A non-credit product proposed after business-rule review.",
                )
            )
        return report.model_copy(
            update={
                "risk_summary": f"{report.risk_summary} Refined after business-rule review.",
                "product_recommendations": recommendations,
            }
        )

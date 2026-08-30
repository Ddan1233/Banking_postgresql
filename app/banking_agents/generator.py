"""OpenAI-backed generation of customer risk reports."""

from __future__ import annotations

import json
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.banking_models import CustomerProfileModel
from app.core.config import settings


ProductCategory = Literal["credit", "savings", "protection", "everyday_banking"]
RiskLevel = Literal["low", "medium", "high"]


class ProductRecommendation(BaseModel):
    """A product proposed to a customer, with an explainable reason."""

    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(min_length=1)
    category: ProductCategory
    rationale: str = Field(min_length=1)


class RiskReport(BaseModel):
    """Structured draft produced for a validated customer profile."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str
    risk_level: RiskLevel
    risk_summary: str = Field(min_length=1)
    key_risk_factors: list[str] = Field(default_factory=list)
    product_recommendations: list[ProductRecommendation] = Field(default_factory=list)


class GeneratorAgent:
    """Create a risk-report draft through the OpenAI Responses API.

    Structured Outputs constrain an LLM response to :class:`RiskReport`; a
    deterministic local implementation makes the workflow testable without a
    network connection or an API key.
    """

    def __init__(
        self, client: OpenAI | None = None, use_openai: bool | None = None
    ) -> None:
        self._client = client
        self._use_openai = use_openai

    def generate(self, profile: CustomerProfileModel) -> RiskReport:
        if self._client is not None or (
            self._use_openai is not False and settings.openai_api_key
        ):
            return self._generate_with_openai(profile)
        return self._generate_locally(profile)

    def _generate_with_openai(self, profile: CustomerProfileModel) -> RiskReport:
        client = self._client or OpenAI(api_key=settings.openai_api_key)
        response = client.responses.create(
            model=settings.openai_model,
            instructions=(
                "You are a prudent retail-banking risk analyst. Generate a concise "
                "customer risk report using only the supplied profile. Recommendations "
                "must be suitable and explainable. If default history exists, do not "
                "recommend any credit product."
            ),
            input=json.dumps(profile.model_dump(mode="json")),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "risk_report",
                    "strict": True,
                    "schema": RiskReport.model_json_schema(),
                }
            },
        )
        return RiskReport.model_validate_json(response.output_text)

    @staticmethod
    def _generate_locally(profile: CustomerProfileModel) -> RiskReport:
        has_default = any(
            (isinstance(item.status, int) and item.status > 0)
            or "default" in (item.status_description or "").lower()
            or (isinstance(item.status, str) and "default" in item.status.lower())
            for item in profile.default_history
        )
        balance_risk = profile.current_balance < 0
        risk_level: RiskLevel = "high" if has_default else "medium" if balance_risk else "low"
        factors: list[str] = []
        if has_default:
            factors.append("Historical default is present in the credit record.")
        if balance_risk:
            factors.append("Current account balance is negative.")
        if not factors:
            factors.append("No default history or negative current balance was detected.")

        recommendations = [
            ProductRecommendation(
                product_name="Savings Account",
                category="savings",
                rationale="Supports a liquidity buffer based on the available account data.",
            )
        ]
        if not has_default:
            recommendations.append(
                ProductRecommendation(
                    product_name="Personal Loan",
                    category="credit",
                    rationale="Credit eligibility remains subject to affordability and underwriting.",
                )
            )
        return RiskReport(
            customer_id=str(profile.customer_id),
            risk_level=risk_level,
            risk_summary="Customer risk assessment generated from the validated profile.",
            key_risk_factors=factors,
            product_recommendations=recommendations,
        )

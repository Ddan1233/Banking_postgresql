"""Generator -> Validator -> Refiner workflow for banking risk reports."""

from __future__ import annotations

from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from app.banking_agents import (
    GeneratorAgent,
    RefinerAgent,
    RiskReport,
    ValidationResult,
    ValidatorAgent,
)
from app.banking_models import CustomerProfileModel


class RiskReportResult(BaseModel):
    """Final report and the audit information for its multi-agent processing."""

    model_config = ConfigDict(extra="forbid")

    report: RiskReport
    validation: ValidationResult
    refinement_count: int = Field(ge=0)
    generation_duration_ms: float = Field(default=0.0, ge=0)
    validation_duration_ms: float = Field(default=0.0, ge=0)
    refinement_duration_ms: float = Field(default=0.0, ge=0)
    observability: dict[str, object] | None = None


class BankingRiskOrchestrator:
    """Coordinates generation, rule checking, and bounded iterative correction."""

    def __init__(
        self,
        generator: GeneratorAgent | None = None,
        validator: ValidatorAgent | None = None,
        refiner: RefinerAgent | None = None,
        max_refinements: int = 2,
    ) -> None:
        if max_refinements < 0:
            raise ValueError("max_refinements cannot be negative")
        self._generator = generator or GeneratorAgent()
        self._validator = validator or ValidatorAgent()
        self._refiner = refiner or RefinerAgent()
        self._max_refinements = max_refinements

    def create_risk_report(self, profile: CustomerProfileModel) -> RiskReportResult:
        """Generate a draft and refine it until valid or the limit is reached."""

        generation_start = perf_counter()
        report = self._generator.generate(profile)
        generation_duration_ms = (perf_counter() - generation_start) * 1000

        validation_start = perf_counter()
        validation = self._validator.validate(profile, report)
        validation_duration_ms = (perf_counter() - validation_start) * 1000
        refinement_duration_ms = 0.0
        refinement_count = 0
        while not validation.is_valid and refinement_count < self._max_refinements:
            refinement_start = perf_counter()
            report = self._refiner.refine(profile, report, validation)
            refinement_duration_ms += (perf_counter() - refinement_start) * 1000
            refinement_count += 1
            validation_start = perf_counter()
            validation = self._validator.validate(profile, report)
            validation_duration_ms += (perf_counter() - validation_start) * 1000
        return RiskReportResult(
            report=report,
            validation=validation,
            refinement_count=refinement_count,
            generation_duration_ms=generation_duration_ms,
            validation_duration_ms=validation_duration_ms,
            refinement_duration_ms=refinement_duration_ms,
        )

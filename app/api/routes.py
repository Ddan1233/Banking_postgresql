"""Scenario-generation HTTP endpoints."""

from fastapi import APIRouter, Request, status

from app.agents.refiner import RefinementResult
from app.agents.validator import ValidationResult
from app.agents.generator import GeneratedScenario
from app.schemas import GenerationResult, RefinementRequest, ScenarioRequest
from app.banking_orchestrator import RiskReportResult
from app.schemas import RiskReportRequest

router = APIRouter(tags=["scenarios"])


@router.post(
    "/generate-scenario",
    response_model=GenerationResult,
    status_code=status.HTTP_200_OK,
)
def generate_scenario(payload: ScenarioRequest, request: Request) -> GenerationResult:
    """Generate and return a scenario that passed the app's realism checks."""

    return request.app.state.scenario_orchestrator.generate_validated_scenario(
        payload.flight_plan, payload.weather, payload.airspace_constraints
    )


@router.post(
    "/validate-scenario",
    response_model=ValidationResult,
    status_code=status.HTTP_200_OK,
)
def validate_scenario(scenario: GeneratedScenario, request: Request) -> ValidationResult:
    """Assess a supplied scenario and return its realism result."""

    return request.app.state.scenario_orchestrator.validate_scenario(scenario)


@router.post(
    "/refine-scenario",
    response_model=RefinementResult,
    status_code=status.HTTP_200_OK,
)
def refine_scenario(payload: RefinementRequest, request: Request) -> RefinementResult:
    """Refine a supplied scenario using validator feedback, then validate it."""

    return request.app.state.scenario_orchestrator.refine_scenario(payload)


@router.post(
    "/generate-risk-report",
    response_model=RiskReportResult,
    status_code=status.HTTP_200_OK,
)
def generate_risk_report(payload: RiskReportRequest, request: Request) -> RiskReportResult:
    """Generate, validate, and if necessary refine a banking risk report."""

    return request.app.state.banking_risk_orchestrator.create_risk_report(
        payload.profile
    )

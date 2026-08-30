"""HTTP request and response schemas."""

from pydantic import BaseModel, Field

from app.agents.generator import GeneratedScenario
from app.agents.refiner import RefinementAlternative
from app.agents.validator import ValidationResult
from app.models import AirspaceConstraints, FlightPlan, WeatherData
from app.banking_models import CustomerProfileModel


class ScenarioRequest(BaseModel):
    """Payload received when a new ATC scenario is requested."""

    flight_plan: FlightPlan
    weather: WeatherData
    airspace_constraints: AirspaceConstraints


class GenerationResult(BaseModel):
    """The final scenario, plan, and validation produced by orchestration."""

    scenario: GeneratedScenario
    flight_plan: FlightPlan
    validation: ValidationResult
    attempts: int
    alternative_flight_plan: FlightPlan | None = None
    alternative_reason: str | None = None
    alternatives: list[RefinementAlternative] = Field(default_factory=list)
    selected_alternative: str | None = None


class RefinementRequest(BaseModel):
    """A scenario and optional flight context for manual refinement."""

    scenario: GeneratedScenario
    flight_plan: FlightPlan | None = None
    airspace_constraints: AirspaceConstraints | None = None


class RiskReportRequest(BaseModel):
    """Request for a banking risk report; profile validation happens at the boundary."""

    profile: CustomerProfileModel

"""FastAPI application factory and scenario-generation orchestration."""

from fastapi import FastAPI, HTTPException, status

from app.agents.generator import GeneratedScenario, GeneratorAgent
from app.agents.refiner import RefinementAlternative, RefinementResult, RefinerAgent
from app.agents.validator import ValidationResult, ValidatorAgent
from app.api.routes import router as scenario_router
from app.core.config import settings
from app.models import AirspaceConstraints, FlightPlan, WeatherData
from app.schemas import GenerationResult, RefinementRequest
from app.banking_orchestrator import BankingRiskOrchestrator


class ScenarioOrchestrator:
    """Generate, validate, and refine scenarios within a fixed attempt limit."""

    _MAX_ATTEMPTS = 3

    def __init__(
        self,
        generator: GeneratorAgent | None = None,
        validator: ValidatorAgent | None = None,
        refiner: RefinerAgent | None = None,
    ) -> None:
        self._generator = generator or GeneratorAgent()
        self._validator = validator or ValidatorAgent()
        self._refiner = refiner or RefinerAgent()

    def generate_validated_scenario(
        self,
        flight_plan: FlightPlan,
        weather: WeatherData,
        airspace_constraints: AirspaceConstraints,
    ) -> GenerationResult:
        """Return the first realistic scenario or report failure after three tries."""

        attempts = 1
        scenario = self._generator.generate(flight_plan, weather)
        active_flight_plan = flight_plan
        last_validation: ValidationResult | None = None
        alternative_flight_plan: FlightPlan | None = None
        alternative_reason: str | None = None
        alternatives: list[RefinementAlternative] = []
        selected_alternative: str | None = None

        while attempts < self._MAX_ATTEMPTS:
            validation = self._validator.validate(
                scenario, active_flight_plan, airspace_constraints
            )

            if validation.is_realistic:
                return GenerationResult(
                    scenario=scenario,
                    flight_plan=active_flight_plan,
                    validation=validation,
                    attempts=attempts,
                    alternative_flight_plan=alternative_flight_plan,
                    alternative_reason=alternative_reason,
                    alternatives=alternatives,
                    selected_alternative=selected_alternative,
                )

            last_validation = validation
            proposal = self._refiner.refine(
                scenario, validation, active_flight_plan, airspace_constraints
            )
            scenario = proposal.scenario
            active_flight_plan = proposal.flight_plan or active_flight_plan
            if proposal.flight_plan is not None:
                alternative_flight_plan = proposal.flight_plan
                alternative_reason = proposal.alternative_reason
            alternatives = proposal.alternatives
            selected_alternative = proposal.selected_alternative
            attempts += 1

        last_validation = self._validator.validate(
            scenario, active_flight_plan, airspace_constraints
        )
        if last_validation.is_realistic:
            return GenerationResult(
                scenario=scenario,
                flight_plan=active_flight_plan,
                validation=last_validation,
                attempts=attempts,
                alternative_flight_plan=alternative_flight_plan,
                alternative_reason=alternative_reason,
                alternatives=alternatives,
                selected_alternative=selected_alternative,
            )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Could not generate a realistic scenario after three attempts.",
                "attempts": attempts,
                "validation": last_validation.model_dump(mode="json"),
            },
        )

    def validate_scenario(self, scenario: GeneratedScenario) -> ValidationResult:
        """Validate a user-supplied scenario without generating a replacement."""

        return self._validator.validate(scenario)

    def refine_scenario(self, payload: RefinementRequest) -> RefinementResult:
        """Refine a supplied rejected scenario once and validate the revision."""

        feedback = self._validator.validate(
            payload.scenario, payload.flight_plan, payload.airspace_constraints
        )
        proposal = self._refiner.refine(
            payload.scenario,
            feedback,
            payload.flight_plan,
            payload.airspace_constraints,
        )
        active_flight_plan = proposal.flight_plan or payload.flight_plan
        return RefinementResult(
            scenario=proposal.scenario,
            validation=self._validator.validate(
                proposal.scenario, active_flight_plan, payload.airspace_constraints
            ),
            alternative_flight_plan=proposal.flight_plan,
            alternative_reason=proposal.alternative_reason,
            alternatives=proposal.alternatives,
            selected_alternative=proposal.selected_alternative,
        )


def create_app() -> FastAPI:
    """Create the HTTP application without side effects at import time."""

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Prototype AI Agentic for Air Traffic Control scenario generation.",
    )
    application.state.scenario_orchestrator = ScenarioOrchestrator()
    application.state.banking_risk_orchestrator = BankingRiskOrchestrator()
    application.include_router(scenario_router)
    return application


app = create_app()

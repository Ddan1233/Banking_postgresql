from app.agents.generator import Disruption, GeneratedScenario
from app.agents.refiner import RefinerAgent
from app.agents.validator import ValidatorAgent


def test_refiner_uses_rejected_weather_feedback_to_create_a_safe_action() -> None:
    scenario = GeneratedScenario(
        flight_id="ATC101",
        summary="Unsafe weather response.",
        disruption=Disruption(
            type="weather",
            severity="high",
            description="Storm cells affect the route.",
            recommended_action="Climb to 60,000 ft and continue as planned.",
        ),
    )
    validator = ValidatorAgent()

    proposal = RefinerAgent().refine(scenario, validator.validate(scenario))
    result = validator.validate(proposal.scenario)

    assert proposal.scenario.disruption.recommended_action == (
        "Reroute around affected weather, avoid hazardous cells, and maintain 30,000 ft."
    )
    assert result.is_realistic is True

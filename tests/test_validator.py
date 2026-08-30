from app.agents.generator import Disruption, GeneratedScenario
from app.agents.validator import ValidatorAgent
from app.models import AirspaceConstraints, FlightPlan


def test_validator_accepts_plausible_weather_response() -> None:
    scenario = GeneratedScenario(
        flight_id="ATC101",
        summary="Thunderstorms require rerouting.",
        disruption=Disruption(
            type="weather",
            severity="high",
            description="Storm cells affect the planned route.",
            recommended_action="Reroute around storm cells and descend to 30,000 ft.",
        ),
    )

    result = ValidatorAgent().validate(scenario)

    assert result.realism_score == 100
    assert result.needs_regeneration is False
    assert result.is_realistic is True


def test_validator_flags_unsafe_altitude_and_missing_mitigation() -> None:
    scenario = GeneratedScenario(
        flight_id="ATC101",
        summary="Severe weather on route.",
        disruption=Disruption(
            type="weather",
            severity="high",
            description="Storm cells affect the planned route.",
            recommended_action="Climb to 60,000 ft and continue as planned.",
        ),
    )

    result = ValidatorAgent().validate(scenario)

    assert result.realism_score == 0
    assert result.needs_regeneration is True
    assert result.is_realistic is False
    assert len(result.observations) == 3


def test_validator_flags_a_flight_plan_above_the_airspace_limit() -> None:
    scenario = GeneratedScenario(
        flight_id="ATC102",
        summary="A weather avoidance route is available.",
        disruption=Disruption(
            type="weather",
            severity="medium",
            description="Rain affects the planned route.",
            recommended_action="Reroute around the weather and maintain 30,000 ft.",
        ),
    )

    result = ValidatorAgent().validate(
        scenario,
        FlightPlan(id="ATC102", origin="LROP", destination="LBSF", altitude=41_000),
        AirspaceConstraints(maximum_altitude=40_000),
    )

    assert result.realism_score == 50
    assert result.needs_regeneration is True
    assert result.observations == [
        "Planned altitude 41,000 ft exceeds the airspace maximum of 40,000 ft."
    ]

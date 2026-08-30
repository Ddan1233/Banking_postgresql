from app.agents.generator import GeneratedScenario, GeneratorAgent
from app.models import FlightPlan, WeatherData


def test_generator_returns_a_validated_json_compatible_scenario() -> None:
    scenario = GeneratorAgent(use_openai=False).generate(
        FlightPlan(
            id="ATC101",
            origin="LROP",
            destination="LBSF",
            altitude=35000,
        ),
        WeatherData(conditions="thunderstorms", wind_speed=28.5),
    )

    assert isinstance(scenario, GeneratedScenario)
    assert scenario.flight_id == "ATC101"
    assert scenario.disruption.type == "weather"
    assert scenario.model_dump(mode="json")["disruption"]["severity"] == "medium"


def test_generated_scenario_rejects_invalid_llm_shape() -> None:
    invalid_response = {
        "flight_id": "ATC101",
        "summary": "A scenario",
        "disruption": {
            "type": "unknown",
            "severity": "medium",
            "description": "Something happened.",
            "recommended_action": "Investigate.",
        },
    }

    try:
        GeneratedScenario.model_validate(invalid_response)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid LLM data must be rejected by Pydantic.")

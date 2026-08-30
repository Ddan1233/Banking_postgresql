from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.agents.generator import Disruption, GeneratedScenario
from app.agents.refiner import RefinementProposal, RefinerAgent
from app.agents.validator import ValidationResult
from app.main import app
from app.models import AirspaceConstraints, FlightPlan, WeatherData
from app.schemas import GenerationResult

client = TestClient(app)


def test_generate_scenario_returns_validated_agent_output() -> None:
    generated_scenario = GeneratedScenario(
        flight_id="ATC101",
        summary="Thunderstorms require a reroute.",
        disruption=Disruption(
            type="weather",
            severity="high",
            description="Thunderstorms affect the planned route.",
            recommended_action="Coordinate a reroute around the storm cells.",
        ),
    )

    with patch.object(app.state, "scenario_orchestrator") as orchestrator:
        orchestrator.generate_validated_scenario.return_value = GenerationResult(
            scenario=generated_scenario,
            flight_plan=FlightPlan(
                id="ATC101", origin="LROP", destination="LBSF", altitude=35_000
            ),
            validation=ValidationResult(
                realism_score=100, observations=["Scenario is realistic."], needs_regeneration=False
            ),
            attempts=1,
        )
        response = client.post(
            "/generate-scenario",
            json={
                "flight_plan": {
                    "id": "ATC101",
                    "origin": "LROP",
                    "destination": "LBSF",
                    "altitude": 35000,
                },
                "weather": {"conditions": "clear", "wind_speed": 12.5},
                "airspace_constraints": {"restricted_areas": []},
            },
        )

    orchestrator.generate_validated_scenario.assert_called_once()
    assert response.status_code == 200
    assert response.json()["scenario"] == generated_scenario.model_dump(mode="json")
    assert response.json()["validation"]["is_realistic"] is True


def test_validate_scenario_returns_a_realism_result() -> None:
    response = client.post(
        "/validate-scenario",
        json={
            "flight_id": "ATC101",
            "summary": "Unsafe weather response.",
            "disruption": {
                "type": "weather",
                "severity": "high",
                "description": "Storm cells affect the route.",
                "recommended_action": "Climb to 60,000 ft and continue as planned.",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "realism_score": 0.0,
        "observations": [
            "Requested altitude 60,000 ft is outside the supported safe operating range "
            "(1,000-45,000 ft).",
            "A weather disruption should include avoidance, holding, diversion, or "
            "rerouting instructions.",
            "A high-severity disruption requires a concrete mitigation action.",
        ],
        "needs_regeneration": True,
        "is_realistic": False,
    }


def test_refine_scenario_corrects_an_unsafe_recommendation() -> None:
    response = client.post(
        "/refine-scenario",
        json={
            "scenario": {
                "flight_id": "ATC101",
                "summary": "Unsafe weather response.",
                "disruption": {
                    "type": "weather",
                    "severity": "high",
                    "description": "Storm cells affect the route.",
                    "recommended_action": "Climb to 60,000 ft and continue as planned.",
                },
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["scenario"]["disruption"]["recommended_action"] == (
        "Reroute around affected weather, avoid hazardous cells, and maintain 30,000 ft."
    )
    assert response.json()["validation"]["is_realistic"] is True


def test_orchestrator_refines_until_a_scenario_is_realistic() -> None:
    unrealistic = ValidationResult(
        realism_score=25, observations=["Unsafe altitude."], needs_regeneration=True
    )
    realistic = ValidationResult(
        realism_score=100, observations=["Scenario is realistic."], needs_regeneration=False
    )
    generator = Mock()
    generator.generate.side_effect = [Mock(), Mock()]
    validator = Mock()
    validator.validate.side_effect = [unrealistic, realistic]
    refiner = Mock()
    refined_scenario = GeneratedScenario(
        flight_id="ATC101",
        summary="Refined scenario.",
        disruption=Disruption(
            type="weather",
            severity="high",
            description="Storm cells affect the route.",
            recommended_action="Reroute and maintain 30,000 ft.",
        ),
    )
    refiner.refine.return_value = RefinementProposal(scenario=refined_scenario)

    from app.main import ScenarioOrchestrator

    ScenarioOrchestrator(
        generator=generator, validator=validator, refiner=refiner
    ).generate_validated_scenario(
        FlightPlan(id="ATC101", origin="LROP", destination="LBSF", altitude=35_000),
        WeatherData(conditions="rain", wind_speed=12.5),
        AirspaceConstraints(maximum_altitude=40_000),
    )

    assert generator.generate.call_count == 1
    assert validator.validate.call_count == 2
    assert refiner.refine.call_count == 1


def test_orchestrator_validates_a_refined_weather_scenario() -> None:
    generated_scenario = GeneratedScenario(
        flight_id="ATC101",
        summary="Unsafe weather response.",
        disruption=Disruption(
            type="weather",
            severity="high",
            description="Storm cells affect the route.",
            recommended_action="Climb to 60,000 ft and continue as planned.",
        ),
    )
    generator = Mock()
    generator.generate.return_value = generated_scenario

    from app.main import ScenarioOrchestrator

    result = ScenarioOrchestrator(generator=generator).generate_validated_scenario(
        FlightPlan(id="ATC101", origin="LROP", destination="LBSF", altitude=35_000),
        WeatherData(conditions="thunderstorms", wind_speed=28.5),
        AirspaceConstraints(maximum_altitude=40_000),
    )

    assert generator.generate.call_count == 1
    assert result.scenario.disruption.recommended_action == (
        "Reroute around affected weather, avoid hazardous cells, and maintain 30,000 ft."
    )


def test_generate_scenario_returns_an_explained_alternative_for_an_unrealistic_plan() -> None:
    response = client.post(
        "/generate-scenario",
        json={
            "flight_plan": {
                "id": "ATC101",
                "origin": "LROP",
                "destination": "LBSF",
                "altitude": 41_000,
            },
            "weather": {"conditions": "thunderstorms", "wind_speed": 28.5},
            "airspace_constraints": {
                "restricted_areas": [],
                "maximum_altitude": 40_000,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["is_realistic"] is True
    assert body["attempts"] == 2
    assert body["alternative_flight_plan"] == {
        "id": "ATC101",
        "origin": "LROP",
        "destination": "LBSF",
        "altitude": 30_000,
    }
    assert body["alternative_reason"] == (
        "Planned altitude was reduced to comply with the airspace maximum."
    )
    assert body["selected_alternative"] == "Compliant avoidance reroute"
    assert len(body["alternatives"]) == 3
    assert body["alternatives"][0]["feasibility"] == "high"
    assert "Advantage:" in body["alternatives"][0]["rationale"]
    assert "Trade-off:" in body["alternatives"][0]["rationale"]
    assert body["scenario"]["disruption"]["recommended_action"] == (
        "Reroute around affected weather, avoid hazardous cells, and maintain 30,000 ft."
    )


def test_orchestrator_returns_422_after_three_unrealistic_attempts() -> None:
    validation = ValidationResult(
        realism_score=25,
        observations=["Altitude is unsafe."],
        needs_regeneration=True,
    )
    generator = Mock()
    generator.generate.return_value = Mock()
    validator = Mock()
    validator.validate.return_value = validation
    refiner = Mock()
    refiner.refine.return_value = RefinementProposal(
        scenario=GeneratedScenario(
            flight_id="ATC101",
            summary="Still unsafe.",
            disruption=Disruption(
                type="weather",
                severity="high",
                description="Storm cells affect the route.",
                recommended_action="Climb to 60,000 ft.",
            ),
        )
    )

    from fastapi import HTTPException
    from app.main import ScenarioOrchestrator

    try:
        ScenarioOrchestrator(
            generator=generator, validator=validator, refiner=refiner
        ).generate_validated_scenario(Mock(), Mock(), Mock())
    except HTTPException as error:
        assert error.status_code == 422
        assert error.detail["attempts"] == 3
    else:
        raise AssertionError("The orchestrator must stop after three attempts.")

    assert generator.generate.call_count == 1
    assert refiner.refine.call_count == 2

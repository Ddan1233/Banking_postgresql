from app.agents.generator import Disruption, GeneratedScenario
from app.agents.refiner import RefinerAgent
from app.agents.validator import ValidatorAgent
from app.models import AirspaceConstraints, FlightPlan


def test_refiner_proposes_a_plan_within_the_airspace_altitude_limit() -> None:
    flight_plan = FlightPlan(
        id="GULF729", origin="OMDB", destination="OOMS", altitude=52_000
    )
    constraints = AirspaceConstraints(maximum_altitude=39_000)
    scenario = GeneratedScenario(
        flight_id="GULF729",
        summary="Severe weather requires a response.",
        disruption=Disruption(
            type="weather",
            severity="high",
            description="Storm cells affect the route.",
            recommended_action="Climb to 60,000 ft and continue as planned.",
        ),
    )
    validator = ValidatorAgent()

    proposal = RefinerAgent().refine(
        scenario, validator.validate(scenario, flight_plan, constraints), flight_plan, constraints
    )

    assert proposal.flight_plan is not None
    assert proposal.flight_plan.altitude == 30_000
    assert proposal.alternative_reason is not None
    assert proposal.selected_alternative == "Compliant avoidance reroute"
    assert len(proposal.alternatives) == 3
    assert [alternative.feasibility for alternative in proposal.alternatives] == [
        "high",
        "medium",
        "medium",
    ]
    for alternative in proposal.alternatives:
        assert alternative.description
        assert "Advantage:" in alternative.rationale
        assert "Trade-off:" in alternative.rationale
    assert validator.validate(proposal.scenario, proposal.flight_plan, constraints).is_realistic

"""Rule-based refinement of ATC scenarios from validator feedback."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.generator import GeneratedScenario
from app.agents.validator import ValidationResult
from app.models import AirspaceConstraints, FlightPlan


class RefinementProposal(BaseModel):
    """A corrected scenario and, when needed, an alternate flight plan."""

    model_config = ConfigDict(extra="forbid")

    scenario: GeneratedScenario
    flight_plan: FlightPlan | None = None
    alternative_reason: str | None = None
    alternatives: list["RefinementAlternative"] = Field(default_factory=list)
    selected_alternative: str | None = None


class RefinementAlternative(BaseModel):
    """One operationally viable way to address a rejected ATC scenario."""

    model_config = ConfigDict(extra="forbid")

    strategy: str
    description: str
    rationale: str
    feasibility: Literal["high", "medium", "low"]


class RefinementResult(BaseModel):
    """A refined scenario together with the validation of that refinement."""

    model_config = ConfigDict(extra="forbid")

    scenario: GeneratedScenario
    validation: ValidationResult
    alternative_flight_plan: FlightPlan | None = None
    alternative_reason: str | None = None
    alternatives: list[RefinementAlternative] = Field(default_factory=list)
    selected_alternative: str | None = None


class RefinerAgent:
    """Turn validator feedback into a safer, actionable ATC recommendation.

    The refiner is deterministic in this stage: it turns a rejected action into
    a disruption-specific avoidance/mitigation action at a supported altitude.
    This makes refinements repeatable in tests and can later be replaced or
    augmented by an LLM without changing the orchestration contract.
    """

    _DEFAULT_ALTITUDE_FEET = 30_000
    _SAFE_MIN_ALTITUDE_FEET = 1_000
    _SAFE_MAX_ALTITUDE_FEET = 45_000

    def refine(
        self,
        scenario: GeneratedScenario,
        feedback: ValidationResult,
        flight_plan: FlightPlan | None = None,
        airspace_constraints: AirspaceConstraints | None = None,
    ) -> RefinementProposal:
        """Return a revised scenario that addresses rejected recommendations."""

        if feedback.is_realistic:
            return RefinementProposal(scenario=scenario)

        altitude = self._select_safe_altitude(airspace_constraints)
        alternatives = self._build_alternatives(
            scenario.disruption.type, altitude, feedback
        )
        selected_alternative = alternatives[0]
        disruption = scenario.disruption.model_copy(
            update={"recommended_action": self._build_recommended_action(
                scenario.disruption.type, altitude
            )}
        )
        refined_scenario = scenario.model_copy(
            update={
                "summary": f"{scenario.summary} Refined after validator feedback.",
                "disruption": disruption,
            }
        )
        alternative_plan = self._refine_flight_plan(flight_plan, airspace_constraints)
        return RefinementProposal(
            scenario=refined_scenario,
            flight_plan=alternative_plan,
            alternative_reason=(
                "Planned altitude was reduced to comply with the airspace maximum."
                if alternative_plan is not None
                else None
            ),
            alternatives=alternatives,
            selected_alternative=selected_alternative.strategy,
        )

    def _refine_flight_plan(
        self,
        flight_plan: FlightPlan | None,
        airspace_constraints: AirspaceConstraints | None,
    ) -> FlightPlan | None:
        if (
            flight_plan is None
            or airspace_constraints is None
            or airspace_constraints.maximum_altitude is None
            or flight_plan.altitude <= airspace_constraints.maximum_altitude
        ):
            return None
        return flight_plan.model_copy(
            update={"altitude": self._select_safe_altitude(airspace_constraints)}
        )

    def _select_safe_altitude(
        self, airspace_constraints: AirspaceConstraints | None
    ) -> int:
        maximum_altitude = (
            airspace_constraints.maximum_altitude
            if airspace_constraints is not None
            and airspace_constraints.maximum_altitude is not None
            else self._SAFE_MAX_ALTITUDE_FEET
        )
        return max(
            self._SAFE_MIN_ALTITUDE_FEET,
            min(self._DEFAULT_ALTITUDE_FEET, maximum_altitude, self._SAFE_MAX_ALTITUDE_FEET),
        )

    @staticmethod
    def _build_recommended_action(disruption_type: str, altitude: int) -> str:
        if disruption_type == "weather":
            return (
                "Reroute around affected weather, avoid hazardous cells, and "
                f"maintain {altitude:,} ft."
            )
        if disruption_type == "conflict":
            return (
                "Vector the aircraft to avoid the traffic conflict and maintain "
                f"{altitude:,} ft."
            )
        return (
            "Reroute around affected airspace and maintain "
            f"{altitude:,} ft."
        )

    def _build_alternatives(
        self,
        disruption_type: str,
        altitude: int,
        feedback: ValidationResult,
    ) -> list[RefinementAlternative]:
        """Return three explained choices, ordered by operational preference."""

        issue_summary = " ".join(feedback.observations)
        primary_action = self._build_recommended_action(disruption_type, altitude)
        if disruption_type == "weather":
            hazard = "hazardous weather cells"
        elif disruption_type == "conflict":
            hazard = "the traffic conflict"
        else:
            hazard = "the affected airspace"

        return [
            RefinementAlternative(
                strategy="Compliant avoidance reroute",
                description=primary_action,
                rationale=(
                    f"This directly resolves the critic feedback: {issue_summary} "
                    f"It keeps the flight clear of {hazard} while using the supported "
                    f"altitude of {altitude:,} ft. Advantage: it preserves progress toward "
                    "the planned destination. Trade-off: it can increase route distance and fuel use."
                ),
                feasibility="high",
            ),
            RefinementAlternative(
                strategy="Temporary hold and reassessment",
                description=(
                    f"Hold clear of {hazard}, maintain {altitude:,} ft, and request an "
                    "updated route when conditions permit."
                ),
                rationale=(
                    f"This avoids committing the aircraft to an unsafe instruction identified by "
                    f"the critic: {issue_summary} Advantage: it gives ATC time to confirm "
                    "traffic and hazard conditions. Trade-off: it consumes fuel and may create delay."
                ),
                feasibility="medium",
            ),
            RefinementAlternative(
                strategy="Controlled diversion",
                description=(
                    f"Divert to a suitable alternate airport, remain clear of {hazard}, and "
                    f"maintain {altitude:,} ft until receiving the diversion clearance."
                ),
                rationale=(
                    f"Diversion removes the need to continue through the rejected scenario: "
                    f"{issue_summary} Advantage: it provides a conservative recovery path when "
                    "the disruption persists. Trade-off: it requires an available alternate, fuel "
                    "assessment, and may materially delay the arrival."
                ),
                feasibility="medium",
            ),
        ]

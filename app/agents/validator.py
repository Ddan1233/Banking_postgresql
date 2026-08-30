"""Rule-based realism validation for generated ATC disruption scenarios."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.agents.generator import GeneratedScenario
from app.models import AirspaceConstraints, FlightPlan


class ValidationResult(BaseModel):
    """The outcome of assessing whether a scenario is operationally plausible."""

    model_config = ConfigDict(extra="forbid")

    realism_score: float = Field(ge=0, le=100)
    observations: list[str] = Field(default_factory=list)
    needs_regeneration: bool

    @computed_field
    @property
    def is_realistic(self) -> bool:
        """Whether the scenario passed the currently configured checks."""

        return not self.needs_regeneration


class ValidatorAgent:
    """Assess a generated scenario against simple, explainable flight rules.

    This first validator does not claim to model a specific aircraft. It catches
    unsafe altitude instructions and checks that a serious disruption has an
    appropriate operational response. Aircraft-performance data can be added in
    a later stage without changing the result contract.
    """

    _SAFE_MIN_ALTITUDE_FEET = 1_000
    _SAFE_MAX_ALTITUDE_FEET = 45_000
    _REGENERATION_THRESHOLD = 60

    def validate(
        self,
        scenario: GeneratedScenario,
        flight_plan: FlightPlan | None = None,
        airspace_constraints: AirspaceConstraints | None = None,
    ) -> ValidationResult:
        """Return a realism score, observations, and regeneration decision."""

        score = 100.0
        observations: list[str] = []
        action = scenario.disruption.recommended_action.lower()

        if (
            flight_plan is not None
            and airspace_constraints is not None
            and airspace_constraints.maximum_altitude is not None
            and flight_plan.altitude > airspace_constraints.maximum_altitude
        ):
            score -= 50
            observations.append(
                f"Planned altitude {flight_plan.altitude:,} ft exceeds the airspace "
                f"maximum of {airspace_constraints.maximum_altitude:,} ft."
            )

        for altitude in self._extract_altitudes(action):
            if not self._SAFE_MIN_ALTITUDE_FEET <= altitude <= self._SAFE_MAX_ALTITUDE_FEET:
                score -= 50
                observations.append(
                    f"Requested altitude {altitude:,} ft is outside the supported "
                    "safe operating range (1,000-45,000 ft)."
                )

        if scenario.disruption.type == "weather" and not any(
            word in action for word in ("reroute", "divert", "avoid", "hold")
        ):
            score -= 25
            observations.append(
                "A weather disruption should include avoidance, holding, diversion, "
                "or rerouting instructions."
            )

        if scenario.disruption.severity == "high" and not any(
            word in action for word in ("reroute", "divert", "avoid", "hold", "delay")
        ):
            score -= 35
            observations.append(
                "A high-severity disruption requires a concrete mitigation action."
            )

        score = max(score, 0.0)
        needs_regeneration = score < self._REGENERATION_THRESHOLD

        if not observations:
            observations.append(
                "Scenario contains a plausible operational response within the "
                "validated altitude range."
            )

        return ValidationResult(
            realism_score=score,
            observations=observations,
            needs_regeneration=needs_regeneration,
        )

    @staticmethod
    def _extract_altitudes(action: str) -> list[int]:
        """Extract altitude instructions expressed as ``ft`` or ``feet``."""

        matches = re.findall(r"\b(\d{1,3}(?:,\d{3})?|\d{4,5})\s*(?:ft|feet)\b", action)
        return [int(match.replace(",", "")) for match in matches]

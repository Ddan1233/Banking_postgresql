from __future__ import annotations

import json
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.models import FlightPlan, WeatherData


DisruptionType = Literal["conflict", "weather", "rerouting"]
Severity = Literal["low", "medium", "high"]


class Disruption(BaseModel):
    """An operational event that requires response."""

    model_config = ConfigDict(extra="forbid")

    type: DisruptionType
    severity: Severity
    description: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)


class GeneratedScenario(BaseModel):
    """JSON-compatible, validated output from :class:`GeneratorAgent`."""

    model_config = ConfigDict(extra="forbid")

    flight_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    disruption: Disruption


class GeneratorAgent:
    """Create a single disruption scenario from a flight plan and weather data.

    When an OpenAI key is configured, the agent requests Structured Outputs and
    then validates the returned JSON again with Pydantic.  Without a key, a
    deterministic placeholder keeps local development and tests independent of
    external services.
    """

    def __init__(
        self, client: OpenAI | None = None, use_openai: bool | None = None
    ) -> None:
        self._client = client
        self._use_openai = use_openai

    def generate(self, flight_plan: FlightPlan, weather: WeatherData) -> GeneratedScenario:
        """Generate and validate one scenario for ``flight_plan`` and ``weather``."""

        if self._client is not None or (
            self._use_openai is not False and settings.openai_api_key
        ):
            return self._generate_with_openai(flight_plan, weather)
        return self._generate_placeholder(flight_plan, weather)

    def _generate_with_openai(
        self, flight_plan: FlightPlan, weather: WeatherData
    ) -> GeneratedScenario:
        client = self._client or OpenAI(api_key=settings.openai_api_key)
        response = client.responses.create(
            model=settings.openai_model,
            instructions=(
                "You generate concise, realistic ATC training scenarios. "
                "Create exactly one disruption. Do not add facts not needed "
                "to describe the disruption and the controller action."
            ),
            input=json.dumps(
                {
                    "flight_plan": flight_plan.model_dump(mode="json"),
                    "weather": weather.model_dump(mode="json"),
                }
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "generated_scenario",
                    "strict": True,
                    "schema": GeneratedScenario.model_json_schema(),
                }
            },
        )
        return GeneratedScenario.model_validate_json(response.output_text)

    @staticmethod
    def _generate_placeholder(
        flight_plan: FlightPlan, weather: WeatherData
    ) -> GeneratedScenario:
        return GeneratedScenario(
            flight_id=flight_plan.id,
            summary=(
                f"{flight_plan.id} from {flight_plan.origin} to "
                f"{flight_plan.destination} encounters adverse weather."
            ),
            disruption=Disruption(
                type="weather",
                severity="medium",
                description=(
                    f"{weather.conditions.capitalize()} conditions with winds of "
                    f"{weather.wind_speed:g} knots affect the planned route."
                ),
                recommended_action=(
                    "Coordinate a weather avoidance reroute and monitor the "
                    "flight for further deviation requests."
                ),
            ),
        )

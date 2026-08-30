"""Domain Pydantic models for ATC scenario data."""

from typing import Annotated

from pydantic import BaseModel, Field


class FlightPlan(BaseModel):
    """Basic information about a planned flight."""

    id: Annotated[str, Field(min_length=1, description="Unique flight identifier")]
    origin: Annotated[str, Field(min_length=3, description="Departure airport code")]
    destination: Annotated[str, Field(min_length=3, description="Arrival airport code")]
    altitude: Annotated[int, Field(gt=0, description="Cruising altitude in feet")]


class WeatherData(BaseModel):
    """Weather conditions relevant to an ATC scenario."""

    conditions: Annotated[str, Field(min_length=1, description="Weather description")]
    wind_speed: Annotated[float, Field(ge=0, description="Wind speed in knots")]


class AirspaceConstraints(BaseModel):
    """Operational restrictions that apply to the airspace."""

    restricted_areas: list[str] = Field(default_factory=list)
    maximum_altitude: Annotated[
        int | None,
        Field(default=None, gt=0, description="Optional maximum altitude in feet"),
    ]

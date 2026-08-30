"""Run the generator agent manually from the project root."""

from app.agents.generator import GeneratorAgent
from app.models import FlightPlan, WeatherData


def main() -> None:
    flight_plan = FlightPlan(
        id="ATC101",
        origin="LROP",
        destination="LBSF",
        altitude=35000,
    )
    weather = WeatherData(conditions="thunderstorms", wind_speed=28.5)

    scenario = GeneratorAgent().generate(flight_plan, weather)
    print(scenario.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

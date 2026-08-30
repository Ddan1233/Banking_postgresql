# ATC Agentic Prototype

FastAPI skeleton for an AI-assisted Air Traffic Control scenario generator.

## Generator agent

`GeneratorAgent` in `app/agents/generator.py` accepts a `FlightPlan` and
`WeatherData`, then returns a Pydantic-validated `GeneratedScenario`. With no
`OPENAI_API_KEY`, it uses a deterministic weather-disruption placeholder. Set
`OPENAI_API_KEY` to enable OpenAI Structured Outputs; the response is still
validated with Pydantic before it is returned.

`POST /generate-scenario` accepts the flight and weather input, then returns
the generated scenario directly. The `airspace_constraints` field is validated
at the API boundary and is reserved for the next routing/constraint stage.

## Validator agent

`ValidatorAgent` in `app/agents/validator.py` receives a `GeneratedScenario`
and returns a Pydantic-validated `ValidationResult`: a 0-100 realism score,
observations, and a `needs_regeneration` flag. It currently applies explicit
rules for safe altitude instructions and mitigations for serious disruptions.

## Orchestration

`ScenarioOrchestrator` in `app/main.py` coordinates `GeneratorAgent` and
`ValidatorAgent`. The `/generate-scenario` endpoint only returns a scenario
after it passes validation. If validation fails, the orchestrator tries again,
up to three total attempts; failure on every attempt produces HTTP 422 with the
last validation observations.

`POST /validate-scenario` accepts an already-written `GeneratedScenario` and
returns its `ValidationResult`. A scenario that is structurally valid but
operationally unrealistic returns HTTP 200 with `is_realistic: false` and the
validator observations.

The generator workflow also rejects a flight plan whose altitude exceeds the
numeric `airspace_constraints.maximum_altitude`. Geographic route validation is
not implemented yet: airport codes and restricted-area names alone do not
contain the coordinates or airspace boundaries required to determine whether a
route intersects a restricted area.

## Refinement

`RefinerAgent` receives a rejected scenario plus the validator result and
replaces the unsafe recommendation with a disruption-specific alternative.
`ScenarioOrchestrator` now follows Generator → Validator → Refiner → Validator,
allowing up to three validations in total. `POST /refine-scenario` exposes one
manual refinement cycle in Swagger; the normal `/generate-scenario` flow uses
the refiner automatically before returning HTTP 422. When it selects a
different flight plan, the `/generate-scenario` response includes
`alternative_flight_plan` and `alternative_reason` so the decision is explicit.
For each rejected scenario, it also returns exactly three explained alternatives
in priority order. Each alternative has a strategy, description, rationale with
advantages and trade-offs, and a feasibility rating. The selected first option
is reported as `selected_alternative` and is used to refine the scenario.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

## Test

```powershell
pytest
```

"""Extension point for the future ATC scenario-generation agent."""

from app.schemas import ScenarioRequest


class ScenarioAgent:
    """Placeholder for an OpenAI-backed scenario-generation workflow.

    The API does not call an LLM yet; keeping this boundary explicit prevents
    transport code from becoming coupled to future agent orchestration.
    """

    def build_prompt_context(self, request: ScenarioRequest) -> dict[str, object]:
        """Return structured context that a future agent can consume."""

        return request.model_dump()

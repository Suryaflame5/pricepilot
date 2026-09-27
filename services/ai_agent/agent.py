"""Agent entry point (V1.2): intent -> plan -> execute -> respond.

The rule-based planner is the default; the LLM backend (same interface) is
enabled with PRICEPILOT_LLM_BASE_URL/API_KEY/MODEL and only produces the
plan - every number in an answer still comes from the typed tool registry.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent.planner import Agent, DeterministicBackend, LLMBackend
from prediction_engine.inference import PredictionEngine
from schemas.alerts import ChatResponse


async def run_agent(
    message: str,
    user_id: uuid.UUID | None,
    db: AsyncSession,
    engine: PredictionEngine | None = None,
) -> ChatResponse:
    """Ephemeral (stateless) turn - legacy/default entry used by the chat route."""
    import os

    backend = LLMBackend() if os.getenv("PRICEPILOT_LLM_BASE_URL") else DeterministicBackend()
    agent = Agent(engine=engine, backend=backend)
    return await agent.chat(message, conversation_id=None, db=db, user_id=user_id)


__all__ = ["run_agent", "Agent"]
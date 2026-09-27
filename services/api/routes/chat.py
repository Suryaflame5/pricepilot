"""Chat route: AI shopping assistant facade (V1.2).

The assistant NEVER computes forecasts itself - it plans (intent + constraints),
then calls the same typed tools a human would (search, compare, history,
forecast, decide). Conversation state (constraints, product context) persists
across turns via conversation_id so "gaming laptop under Rs 80k" + "I can wait
two months" accumulate into one decision.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent.planner import Agent
from api.config import settings
from api.dependencies import get_db
from prediction_engine.inference import PredictionEngine
from schemas.alerts import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    engine = PredictionEngine(
        registry_dir=settings.model_registry_dir,
        calibration_dir=settings.calibration_store_dir,
        conformal_dir=settings.conformal_store_dir,
        shadow_dir=settings.shadow_log_dir,
    )
    agent = Agent(engine=engine)
    return await agent.chat(
        request.message,
        conversation_id=request.conversation_id,
        db=db,
        user_id=request.user_id,
    )
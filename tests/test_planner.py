"""V1.2 planner tests: intent extraction, constraint persistence across turns,
typed tool validation, narrator contract, LLM backend fallback."""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

import httpx
import pytest

from ai_agent.narrator import REASON_TEXT, explain
from ai_agent.planner import (
    Agent,
    Constraints,
    DeterministicBackend,
    IntentSpec,
    LLMBackend,
    _classify_intent,
    _extract_constraints,
    _merge_constraints,
    _requires_for,
)
from ai_agent.tools import ToolCallError, ToolContext, ToolRegistry
from database.models import ConversationState, Listing, PriceObservation
from database.session import create_engine, create_session_factory, init_db
from ml.datasets.seed_db import seed
from prediction_engine.inference import PredictionEngine

DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_factory():
    engine = create_engine(DB_URL)
    await init_db(engine)
    yield create_session_factory(engine)
    await engine.dispose()


class TestConstraintExtraction:
    def test_price_under(self):
        c = _extract_constraints("gaming laptop under Rs 80,000")
        assert c.max_price == 80000.0

    def test_price_k_suffix(self):
        c = _extract_constraints("show me something under ₹80k")
        assert c.max_price == 80000.0

    def test_wait_horizon_months(self):
        c = _extract_constraints("I can wait two months")
        assert c.wait_horizon_days == 60

    def test_wait_horizon_weeks(self):
        c = _extract_constraints("wait 3 weeks")
        assert c.wait_horizon_days == 21

    def test_requirements(self):
        c = _extract_constraints("need RTX 5060 and 16GB ram, 1TB storage")
        assert c.requirements["gpu"] == "RTX 5060"
        assert c.requirements["ram"] == "16GB"
        assert c.requirements["storage"] == "1TB"

    def test_oled(self):
        c = _extract_constraints("an OLED display laptop")
        assert c.requirements["display"] == "OLED"

    def test_cheapest_strategy(self):
        c = _extract_constraints("cheapest good one")
        assert c.strategy == "LOWEST_PRICE"
        assert c.quality_threshold is not None

    def test_best_value_strategy_with_flexibility(self):
        c = _extract_constraints("best laptop, don't care about 5k more")
        assert c.strategy == "BEST_VALUE"
        assert c.budget_flexibility == 5000

    def test_wait_strategy(self):
        c = _extract_constraints("I can wait, when should I buy")
        assert c.strategy == "WAIT_FOR_TARGET"

    def test_merge_keeps_existing(self):
        base = Constraints(max_price=80000.0, wait_horizon_days=60, requirements={"gpu": "RTX 5060"})
        merged = _merge_constraints(base, Constraints(strategy="LOWEST_PRICE"))
        assert merged.max_price == 80000.0
        assert merged.wait_horizon_days == 60
        assert merged.requirements["gpu"] == "RTX 5060"
        assert merged.strategy == "LOWEST_PRICE"

    def test_merge_accumulates_requirements(self):
        base = Constraints(requirements={"gpu": "RTX 5060"})
        merged = _merge_constraints(base, Constraints(requirements={"ram": "16GB"}))
        assert merged.requirements == {"gpu": "RTX 5060", "ram": "16GB"}


class TestIntent:
    def test_classify_buy(self):
        assert _classify_intent("should i buy the sony headphones", {}) == "SHOULD_I_BUY"

    def test_classify_forecast(self):
        assert _classify_intent("forecast the price of x1000", {}) == "FORECAST"

    def test_classify_alert(self):
        assert _classify_intent("alert me when it drops under 25000", {}) == "SET_ALERT"

    def test_classify_find_without_product(self):
        assert _classify_intent("find me the cheapest sony headphones", {}) == "FIND_PRODUCT"

    def test_classify_check_with_known_product(self):
        assert _classify_intent("whats the price now?", {"product_id": str(uuid.uuid4())}) == "CHECK_PRICE"

    def test_requires_for_buy_includes_decision(self):
        spec = _requires_for("SHOULD_I_BUY", Constraints(), "", {})
        assert "DECIDE" in spec
        assert "FORECAST" in spec

    def test_deterministic_backend_plans(self):
        backend = DeterministicBackend()
        import asyncio

        spec = asyncio.run(backend.plan("cheapest gaming laptop under Rs 80000", {}))
        assert spec.intent == "FIND_PRODUCT"
        assert spec.constraints.max_price == 80000.0
        assert spec.constraints.strategy == "LOWEST_PRICE"


class TestTypedTools:
    def test_registry_validates_arguments(self):
        registry = ToolRegistry()
        with pytest.raises(ToolCallError) as exc:
            asyncio.run(registry.call(ToolContext(db=None, engine=None), "search_products", {"query": ""}))
        assert "rejected arguments" in str(exc.value)

    def test_registry_unknown_tool(self):
        registry = ToolRegistry()
        with pytest.raises(ToolCallError) as exc:
            asyncio.run(registry.call(ToolContext(db=None, engine=None), "invented_tool", {}))
        assert "unknown tool" in str(exc.value)

    def test_tool_schemas_exposed(self):
        registry = ToolRegistry()
        names = {t["name"] for t in registry.list_tools()}
        assert names == {
            "search_products", "compare_offers", "get_price_history",
            "forecast_price", "target_probability", "get_buy_wait_decision",
            "create_price_alert",
        }

    def test_bad_strategy_rejected(self):
        registry = ToolRegistry()
        with pytest.raises(ToolCallError) as exc:
            asyncio.run(
                registry.call(
                    ToolContext(db=None, engine=None),
                    "get_buy_wait_decision",
                    {"product_id": str(uuid.uuid4()), "strategy": "MAGIC"},
                )
            )
        assert "strategy" in str(exc.value)

    def test_strategy_literal_validated(self):
        from ai_agent.tools import DecisionIn

        assert DecisionIn(strategy="WAIT_FOR_TARGET", product_id=uuid.uuid4()).strategy == "WAIT_FOR_TARGET"


class TestNarrator:
    def test_numbers_come_from_parts(self):
        parts = {
            "product": {"name": "Sony WH-1000XM6", "category": "Audio"},
            "offers": {
                "offers": [{"retailer_name": "Croma", "effective_price": 27000.0, "availability": "IN_STOCK"}],
                "cheapest": {"retailer_name": "Croma", "effective_price": 27000.0, "availability": "IN_STOCK"},
            },
            "stats": {"min_30d": 25000.0, "max_30d": 30000.0, "mean_30d": 27500.0,
                      "price_percentile_90d": 0.65, "observations_90d": 180},
            "decision": {
                "recommendation": "WAIT",
                "current_price": 27000.0,
                "expected_price": 25200.0,
                "horizon_days": 30,
                "target": 25000.0,
                "target_probability": 0.62,
                "reason_codes": ["WAIT_EXPECTED_VALUE_POSITIVE", "TARGET_ATTAINABLE_WITHIN_HORIZON"],
            },
        }
        reply = explain(parts)
        assert "27,000" in reply
        assert "25,000" in reply
        assert REASON_TEXT["WAIT_EXPECTED_VALUE_POSITIVE"] in reply
        assert "62%" in reply
        assert "30d" in reply

    def test_no_llm_numbers(self):
        """explain() never recomputes: a fake forecast number stays verbatim."""
        parts = {
            "product": {"name": "X"},
            "offers": {"offers": [], "cheapest": None},
            "forecast": {"horizon_hours": 720, "median": 12345.67,
                         "interval": {"lower": 10000.0, "upper": 15000.0},
                         "regime": "stable",
                         "confidence": {"level": "HIGH", "score": 0.9}},
        }
        reply = explain(parts)
        assert "12,345.67" in reply
        assert "10,000" in reply and "15,000" in reply


class TestConversationalPersistence:
    async def test_constraints_survive_across_turns(self, db_factory):
        async with db_factory() as db:
            await seed(db, products=2, days=90, obs_per_day=2)
        agent = Agent(engine=PredictionEngine())

        async with db_factory() as db:
            first = await agent.chat(
                "find the cheapest Sony headphones under Rs 80000",
                conversation_id="conv-1", db=db,
            )
            assert first.conversation_id == "conv-1"
            assert first.intent == "FIND_PRODUCT"
            assert first.constraints["max_price"] == 80000.0

            row = (
                await db.execute(
                    select(ConversationState).where(ConversationState.conversation_id == "conv-1")
                )
            ).scalar_one()
            assert row.state["constraints"]["max_price"] == 80000.0

        async with db_factory() as db:
            second = await agent.chat(
                "I can wait two months",
                conversation_id="conv-1", db=db,
            )
            assert second.constraints["wait_horizon_days"] == 60
            assert second.constraints["max_price"] == 80000.0  # carried over

            row = (
                await db.execute(
                    select(ConversationState).where(ConversationState.conversation_id == "conv-1")
                )
            ).scalar_one()
            assert row.state["constraints"]["wait_horizon_days"] == 60

    async def test_ephemeral_turn_gets_new_conversation(self, db_factory):
        async with db_factory() as db:
            await seed(db, products=1, days=60, obs_per_day=2)
        agent = Agent(engine=PredictionEngine())
        async with db_factory() as db:
            resp = await agent.chat("cheapest sony headphones", conversation_id=None, db=db)
            assert resp.conversation_id is not None
            assert resp.reply
            assert resp.tool_calls

    async def test_full_buy_turn_returns_decision(self, db_factory):
        async with db_factory() as db:
            await seed(db, products=1, days=180, obs_per_day=2)
        agent = Agent(engine=PredictionEngine())
        async with db_factory() as db:
            resp = await agent.chat(
                "should I buy the Sony WH-1000XM6 now?", conversation_id=None, db=db
            )
            assert resp.intent == "SHOULD_I_BUY"
            kinds = {s.kind for s in resp.steps}
            assert {"search", "compare", "history", "forecast", "decide"} <= kinds
            assert "Recommendation" in resp.reply


class TestLLMBackend:
    def _fake_llm(self, response_body: dict):
        def factory():
            async def handler(request):
                return httpx.Response(200, json=response_body)

            return httpx.AsyncClient(transport=httpx.MockTransport(handler))

        return factory

    def test_llm_backend_parses_and_validates(self, monkeypatch):
        monkeypatch.setenv("PRICEPILOT_LLM_BASE_URL", "https://llm.test")
        monkeypatch.setenv("PRICEPILOT_LLM_API_KEY", "k")
        backend = LLMBackend(client_factory=self._fake_llm(
            {"choices": [{"message": {"content": json.dumps(
                {"intent": "SHOULD_I_BUY", "product_query": "sony headphones",
                 "constraints": {"max_price": 80000, "strategy": "LOWEST_PRICE"}}
            )}}]}
        ))
        import asyncio

        spec = asyncio.run(backend.plan("should I buy the sony headphones under 80k", {}))
        assert spec.intent == "SHOULD_I_BUY"
        assert spec.constraints.max_price == 80000
        assert "DECIDE" in spec.requires

    def test_llm_failure_falls_back_to_deterministic(self, monkeypatch):
        monkeypatch.setenv("PRICEPILOT_LLM_BASE_URL", "https://llm.test")
        monkeypatch.setenv("PRICEPILOT_LLM_API_KEY", "k")

        def broken():
            async def handler(request):
                return httpx.Response(500, text="boom")

            return httpx.AsyncClient(transport=httpx.MockTransport(handler))

        backend = LLMBackend(client_factory=broken)
        import asyncio

        spec = asyncio.run(backend.plan("cheapest sony under 80k", {}))
        assert spec.intent == "FIND_PRODUCT"  # deterministic fallback
        assert spec.constraints.max_price == 80000.0

    def test_llm_garbage_json_ignored(self, monkeypatch):
        monkeypatch.setenv("PRICEPILOT_LLM_BASE_URL", "https://llm.test")
        monkeypatch.setenv("PRICEPILOT_LLM_API_KEY", "k")
        backend = LLMBackend(client_factory=self._fake_llm(
            {"choices": [{"message": {"content": "not json at all"}}]}
        ))
        import asyncio

        spec = asyncio.run(backend.plan("find sony headphones", {}))
        assert spec.intent == "FIND_PRODUCT"


def asyncio_run(awaitable):
    import asyncio

    return asyncio.get_event_loop().run_until_complete(awaitable)


from sqlalchemy import select  # noqa: E402
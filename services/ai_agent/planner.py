"""Planner state machine (V1.2): intent -> plan -> execute -> respond.

user -> planner -> TOOL SELECTION (SEARCH/COMPARE/FORECAST) -> TOOLS -> narrator

Phases per turn:
    UNDERSTAND -> IDENTIFY PRODUCT -> GATHER OFFERS -> ANALYZE HISTORY ->
    FORECAST -> DECIDE -> RESPOND

Conversational constraints persist across turns in the conversation_states
table: "gaming laptop under Rs 80k" -> {category, max_price}, "I can wait two
months" -> {wait_horizon_days: 60}, "need RTX 5060" -> {requirements: {gpu}}.

Backends: DeterministicBackend (rule-based, always available, fully tested)
and LLMBackend (OpenAI-compatible chat completions when configured; falls back
to the deterministic backend on any failure). The LLM only produces the PLAN
(intent + constraints). Every number in an answer still comes from the typed
tools - the LLM never touches prices.
"""

import json
import logging
import os
import re
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from ai_agent.narrator import explain
from ai_agent.tools import ToolCallError, ToolContext, ToolRegistry
from database.models import ConversationState, ConversationTrace
from prediction_engine.inference import PredictionEngine
from schemas.alerts import ChatResponse, ChatStep, ChatToolCall

logger = logging.getLogger(__name__)

INR = lambda v: f"\u20b9{v:,.0f}" if v is not None else "n/a"  # noqa: E731

STRATEGIES = (
    "IMMEDIATE",
    "LOWEST_PRICE",
    "BEST_VALUE",
    "WAIT_FOR_TARGET",
    "BEST_PERFORMANCE",
    "LOWEST_RISK",
)


# ------------------------------------------------------------------ state

class Constraints(BaseModel):
    category: str | None = None
    max_price: float | None = None
    requirements: dict[str, str] = Field(default_factory=dict)  # {"gpu": "RTX 5060"}
    wait_horizon_days: int | None = None
    budget_flexibility: float | None = None  # BEST_VALUE explicit trade-off
    strategy: str = "IMMEDIATE"
    quality_threshold: float | None = None  # LOWEST_PRICE floor


class IntentSpec(BaseModel):
    intent: str  # FIND_PRODUCT | CHECK_PRICE | FORECAST | SHOULD_I_BUY | SET_ALERT
    product_query: str | None = None
    constraints: Constraints = Field(default_factory=Constraints)
    requires: list[str] = Field(default_factory=list)  # SEARCH/COMPARE/HISTORY/FORECAST/DECIDE/ALERT


class PlannerResult:
    def __init__(
        self,
        intent: str,
        requires: list[str],
        calls: list[ChatToolCall],
        steps: list[ChatStep],
        parts: dict[str, Any],
        reply: str,
    ) -> None:
        self.intent = intent
        self.requires = requires
        self.calls = calls
        self.steps = steps
        self.parts = parts
        self.reply = reply


# ------------------------------------------------------------- backends


class PlannerBackend(ABC):
    name = "base"
    used_name = "base"

    @abstractmethod
    async def plan(self, message: str, state: dict[str, Any]) -> IntentSpec:
        raise NotImplementedError


class DeterministicBackend(PlannerBackend):
    """Rule-based intent + constraint extraction. Never invents parameters:
    it only fills fields it can evidence from the message text."""

    name = "deterministic"
    used_name = "deterministic"

    async def plan(self, message: str, state: dict[str, Any]) -> IntentSpec:
        msg = message.strip()
        constraints = _merge_constraints(Constraints.model_validate(state.get("constraints", {})), _extract_constraints(msg))
        intent = _classify_intent(msg, state)
        requires = _requires_for(intent, constraints, msg, state)

        product_query = _extract_product_query(msg, intent)
        # references without a query ("and that one?", "what about it?") reuse state.product_id
        if not product_query and state.get("product_id"):
            product_query = None  # keep state product

        return IntentSpec(
            intent=intent,
            product_query=product_query,
            constraints=constraints,
            requires=requires,
        )


class LLMBackend(PlannerBackend):
    """OpenAI-compatible planner. Guarded by env vars; any failure (network,
    bad JSON, invalid schema) falls back to DeterministicBackend so the agent
    never 500s because the LLM misbehaved.

    The LLM returns ONLY {intent, product_query, constraints} - pydantic
    validates it, and unverifiable constraints are dropped before execution.
    """

    name = "llm"

    def __init__(self, client_factory=None) -> None:
        import httpx

        self._httpx = httpx
        self.base_url = os.getenv("PRICEPILOT_LLM_BASE_URL", "")
        self.api_key = os.getenv("PRICEPILOT_LLM_API_KEY", "")
        self.model = os.getenv("PRICEPILOT_LLM_MODEL", "gpt-4o-mini")
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=20))
        self._fallback = DeterministicBackend()

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def plan(self, message: str, state: dict[str, Any]) -> IntentSpec:
        if not self.enabled:
            self.used_name = "deterministic"
            return await self._fallback.plan(message, state)
        self.used_name = "llm"
        try:
            return await self._llm_plan(message, state)
        except Exception as exc:  # noqa: BLE001 - degrade, never crash
            logger.warning("LLM planner failed (%s); using deterministic backend", exc)
            self.used_name = "llm-fallback"
            return await self._fallback.plan(message, state)

    async def _llm_plan(self, message: str, state: dict[str, Any]) -> IntentSpec:
        system = (
            "You are the planner of a price-intelligence shopping assistant. "
            "Return ONLY JSON with keys: intent (one of FIND_PRODUCT, CHECK_PRICE, "
            "FORECAST, SHOULD_I_BUY, SET_ALERT), product_query (string or null), "
            f"constraints (category, max_price, wait_horizon_days, budget_flexibility, "
            f"strategy one of {', '.join(STRATEGIES)}, requirements object). "
            "Never invent prices or numbers beyond what the user said."
        )
        history = state.get("history", [])[-8:]
        response = await self._client_factory().post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    *history,
                    {"role": "user", "content": message},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        raw = json.loads(content)
        spec = IntentSpec.model_validate(raw)
        spec.constraints = _merge_constraints(
            Constraints.model_validate(state.get("constraints", {})), spec.constraints
        )
        spec.requires = _requires_for(spec.intent, spec.constraints, message, state)
        return spec


# ---------------------------------------------------------- planner core


class Agent:
    """Facade used by the chat route; keeps conversation memory persisted."""

    def __init__(
        self,
        engine: PredictionEngine | None = None,
        backend: PlannerBackend | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.engine = engine or PredictionEngine()
        self.tools = registry or ToolRegistry()
        self.backend = backend or (
            LLMBackend() if os.getenv("PRICEPILOT_LLM_BASE_URL") else DeterministicBackend()
        )

    async def load_state(self, db, conversation_id: str) -> dict[str, Any]:
        if not conversation_id:
            return {"history": [], "constraints": {}, "product_id": None}
        row = (
            await db.execute(
                select(ConversationState).where(ConversationState.conversation_id == conversation_id)
            )
        ).scalar_one_or_none()
        return dict(row.state or {}) if row else {"history": [], "constraints": {}, "product_id": None}

    async def save_state(self, db, conversation_id: str, state: dict[str, Any]) -> None:
        if not conversation_id:
            return
        row = (
            await db.execute(
                select(ConversationState).where(ConversationState.conversation_id == conversation_id)
            )
        ).scalar_one_or_none()
        if row is None:
            row = ConversationState(conversation_id=conversation_id, state=state)
            db.add(row)
        else:
            row.state = state
        await db.flush()

    async def chat(
        self,
        message: str,
        conversation_id: str | None,
        db,
        user_id: uuid.UUID | None = None,
    ) -> ChatResponse:
        conversation_id = conversation_id or str(uuid.uuid4())
        state = await self.load_state(db, conversation_id)
        ctx = ToolContext(db=db, engine=self.engine, user_id=user_id)
        started = time.perf_counter()

        spec = await self.backend.plan(message, state)
        spec.constraints = _merge_constraints(
            Constraints.model_validate(state.get("constraints", {})), spec.constraints
        )
        state["constraints"] = spec.constraints.model_dump()
        state["strategy"] = spec.constraints.strategy
        state["history"] = state.get("history", []) + [
            {"role": "user", "content": message}
        ]
        state["history"] = state["history"][-12:]

        calls: list[ChatToolCall] = []
        steps: list[ChatStep] = []
        parts: dict[str, Any] = {"intent": spec.intent}
        error: str | None = None

        try:
            parts, calls, steps = await self._execute(
                ctx, spec, state, calls, steps, parts
            )
            state["product_id"] = parts.get("product_id") or state.get("product_id")
            reply = explain(parts)
        except ToolCallError as exc:
            error = str(exc)
            reply = (
                f"I couldn't complete that: {exc}. "
                "Tell me the product more precisely (brand + model), e.g. 'Sony WH-1000XM6'."
            )
            state = dict(state)

        state["history"].append({"role": "assistant", "content": reply})
        turn_index = sum(
            1 for h in state.get("history", []) if h.get("role") == "user"
        )
        db.add(
            ConversationTrace(
                conversation_id=conversation_id,
                user_id=user_id,
                turn_index=turn_index,
                intent=spec.intent,
                backend=self.backend.used_name,
                requires=list(spec.requires),
                tool_calls=[c.model_dump() for c in calls],
                steps=[s.model_dump() for s in steps],
                reply=reply,
                error=error,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        )
        await self.save_state(db, conversation_id, state)
        await db.commit()

        return ChatResponse(
            reply=reply,
            steps=steps,
            tool_calls=calls,
            conversation_id=conversation_id,
            intent=spec.intent,
            constraints=spec.constraints.model_dump(),
            strategy=spec.constraints.strategy,
        )

    async def _execute(self, ctx, spec, state, calls, steps, parts):
        """UNDERSTAND -> IDENTIFY -> GATHER -> ANALYZE -> FORECAST -> DECIDE -> RESPOND."""
        requires = list(spec.requires)

        def record(name: str, arguments: dict, kind: str, summary: str, details: dict) -> None:
            calls.append(ChatToolCall(tool=name, arguments=arguments))
            steps.append(ChatStep(kind=kind, summary=summary, details=details))

        # ---- IDENTIFY PRODUCT -------------------------------------------
        product_id = state.get("product_id")
        if "SEARCH" in requires:
            result = await ctx_tool(ctx, self.tools, "search_products", {
                "query": spec.product_query or "",
                "category": spec.constraints.category,
                "max_price": spec.constraints.max_price,
            })
            record("search_products", {"query": spec.product_query or ""}, "search",
                   "identified the product", result)
            products = result.get("products", [])
            if not products:
                raise ToolCallError("no product matched your query")
            chosen = products[0]
            if spec.constraints.max_price is not None:
                affordable = [p for p in products if p.get("price_from") is not None
                              and p["price_from"] <= spec.constraints.max_price]
                if affordable:
                    chosen = affordable[0]
            product_id = chosen["id"]
            parts["product"] = {
                "name": chosen["canonical_name"],
                "brand": chosen.get("brand"),
                "model": chosen.get("model"),
                "price_from": chosen.get("price_from"),
            }
        elif product_id:
            parts["product"] = {"id": product_id}
        parts["product_id"] = product_id

        if product_id is None:
            raise ToolCallError("I couldn't identify which product you mean")

        # ---- GATHER OFFERS ----------------------------------------------
        if "COMPARE" in requires:
            result = await ctx_tool(ctx, self.tools, "compare_offers",
                                    {"product_id": product_id, "include_shipping": True})
            record("compare_offers", {"product_id": product_id}, "compare",
                   "collected current offers", {"count": result.get("count"), "cheapest": result.get("cheapest")})
            parts["offers"] = result

        # ---- ANALYZE HISTORY --------------------------------------------
        if "HISTORY" in requires:
            result = await ctx_tool(ctx, self.tools, "get_price_history",
                                    {"product_id": product_id, "horizon_days": 365})
            record("get_price_history", {"product_id": product_id}, "history",
                   "loaded 12-month statistics", {"stats": result.get("stats")})
            parts["stats"] = result["stats"]

        # ---- FORECAST / PROBABILITY -------------------------------------
        wait = spec.constraints.wait_horizon_days
        if "FORECAST" in requires:
            h = (wait or 30) * 24
            result = await ctx_tool(ctx, self.tools, "forecast_price",
                                    {"product_id": product_id, "horizon_hours": h})
            record("forecast_price", {"product_id": product_id, "horizon_hours": h}, "forecast",
                   "ran market forecast", {k: result.get(k) for k in ("median", "interval", "regime")})
            parts["forecast"] = result

        if "DECIDE" in requires:
            target = None
            if spec.constraints.strategy == "WAIT_FOR_TARGET":
                target = spec.constraints.max_price or _extract_constraints(
                    state["history"][-1]["content"] if state.get("history") else ""
                ).max_price
            result = await ctx_tool(ctx, self.tools, "get_buy_wait_decision", {
                "product_id": product_id,
                "target_price": target,
                "deadline_days": wait,
                "strategy": spec.constraints.strategy,
            })
            record("get_buy_wait_decision",
                   {"product_id": product_id, "deadline_days": wait, "strategy": spec.constraints.strategy},
                   "decide", "ran buy/wait decision",
                   {k: result.get(k) for k in ("recommendation", "target", "target_probability", "reason_codes")})
            parts["decision"] = result

        # ---- ALERT -------------------------------------------------------
        if "ALERT" in requires:
            target = _extract_constraints(message_for_alert(state)).max_price
            if target is None:
                raise ToolCallError("tell me a target price for the alert, e.g. 'alert me under Rs 25000'")
            result = await ctx_tool(ctx, self.tools, "create_price_alert",
                                    {"product_id": product_id, "target_price": target, "user_id": str(ctx.user_id) if ctx.user_id else None})
            record("create_price_alert", {"product_id": product_id, "target_price": target},
                   "alert", "created price alert", result)
            parts["alert"] = result

        return parts, calls, steps


async def ctx_tool(ctx: ToolContext, registry: ToolRegistry, name: str, args: dict) -> dict:
    return await registry.call(ctx, name, args)


def message_for_alert(state: dict[str, Any]) -> str:
    return state.get("history", [])[-1].get("content", "") if state.get("history") else ""


# -------------------------------------------------------- intent parsing


def _classify_intent(msg: str, state: dict[str, Any]) -> str:
    if re.search(r"\b(alert|notify|notify me|when (?:it )?(?:drops|reaches|hits))\b", msg, re.I) \
            or re.search(r"\b(set|create).*\balert\b", msg, re.I):
        return "SET_ALERT"
    if re.search(r"\b(forecast|predict|price in \d|reach \d)\b", msg, re.I):
        return "FORECAST"
    if re.search(r"\b(should i buy|buy it now|worth it|worth buying|buy now|wait or buy)\b", msg, re.I):
        return "SHOULD_I_BUY"
    if re.search(r"\b(find|show|search|look(?:ing)? for|cheapest|best|recommend|price of|how much)\b", msg, re.I):
        return "FIND_PRODUCT" if not state.get("product_id") else "CHECK_PRICE"
    if msg.strip() and state.get("product_id"):
        return "CHECK_PRICE"
    return "FIND_PRODUCT"


def _requires_for(intent: str, constraints: Constraints, msg: str, state: dict[str, Any]) -> list[str]:
    has_product = bool(state.get("product_id"))
    need_search = not has_product or _has_new_query(msg)
    plan: list[str] = []
    if need_search:
        plan.append("SEARCH")
    if intent in ("FIND_PRODUCT", "CHECK_PRICE"):
        plan += ["COMPARE"]
        if not need_search:
            plan += ["HISTORY"]
    if intent == "FORECAST":
        plan += ["COMPARE", "HISTORY", "FORECAST"]
    if intent == "SHOULD_I_BUY":
        plan += ["COMPARE", "HISTORY", "FORECAST", "DECIDE"]
    if intent == "SET_ALERT":
        plan += ["COMPARE", "ALERT"]
    if need_search:
        plan += ["COMPARE"]
    return _dedupe(plan)


def _has_new_query(msg: str) -> bool:
    return bool(re.search(r"\b(cheapest|find|show|search|look|best|for|recommend|price of)\b", msg, re.I))


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for i in items:
        if i not in out:
            out.append(i)
    return out


def _extract_product_query(msg: str, intent: str) -> str | None:
    if intent == "SET_ALERT":
        msg = re.sub(r"\b(alert|notify me|when|it|drops|reaches|hits|below|under|at)\b", " ", msg, flags=re.I)
    stopwords = {
        "should", "i", "i'm", "im", "me", "buy", "purchase", "worth", "wait", "now", "is",
        "are", "what", "whats", "what's", "my", "and", "to", "in", "within", "days", "months",
        "weeks", "the", "a", "an", "of", "for", "cheapest", "find", "show", "best", "compare",
        "forecast", "predict", "price", "target", "reaches", "reach", "reaching", "below",
        "under", "at", "notify", "alert", "when", "sets", "set", "looking", "recommend",
        "give", "get", "need", "want", "with",
    }
    tokens = [
        t for t in re.split(r"[^\w'-]+", msg.lower())
        if t and t not in stopwords and not t.isdigit()
    ]
    query = " ".join(tokens)
    return query or None


# ------------------------------------------------------ constraint parsing


def _extract_constraints(msg: str) -> Constraints:
    c = Constraints()

    m = re.search(r"(?:under|below|within|less than|upto|up to|max|budget of)\s*[₹rs.\s]*([\d,\.]+)\s*([kKmM]?)", msg, re.I)
    if m:
        v = float(m.group(1).replace(",", ""))
        if m.group(2).lower() == "k":
            v *= 1000
        elif m.group(2).lower() == "m":
            v *= 1_000_000
        c.max_price = v

    m = re.search(r"\b(?:wait|within|in)\s+(\d+|[a-z]+)\s*(month|week|day)", msg.lower())
    if m:
        unit = m.group(2)
        factor = 30 if unit.startswith("month") else 7 if unit.startswith("week") else 1
        n = _word_number(m.group(1))
        if n is not None:
            c.wait_horizon_days = n * factor
    else:
        # "I can wait a month" / "two more weeks"
        m = re.search(r"\bcan wait (?:,(?: you)?|to|for|about)?\s*(a|one|two|three|four)?\s*(month|week)\b", msg.lower())
        if m and m.group(1) in ("a", "one"):
            c.wait_horizon_days = 30 if m.group(2).startswith("month") else 7

    m = re.search(r"\brtx\s?(\d+)\b", msg, re.I)
    if m:
        c.requirements["gpu"] = f"RTX {m.group(1)}"
    for mem in re.findall(r"\b(\d+)gb(?:\b| ram)", msg, re.I):
        c.requirements.setdefault("ram", f"{mem.upper()}GB")
    for store in re.findall(r"\b(\d+)tb\b", msg, re.I):
        c.requirements.setdefault("storage", f"{store.upper()}TB")
    if re.search(r"\boled\b", msg, re.I):
        c.requirements["display"] = "OLED"

    if re.search(r"\bcheapest\b|\bunder budget\b|\bbudget\b", msg, re.I):
        c.strategy = "LOWEST_PRICE"
        c.quality_threshold = c.quality_threshold or 3.9
    if re.search(r"\bbest value\b|\bbang for buck\b", msg, re.I):
        c.strategy = "BEST_VALUE"
    if re.search(r"\bbest(?: performance)?\b|don'?t care (?:about|the) price\b", msg, re.I):
        c.strategy = "BEST_VALUE"
        if re.search(r"don'?t care", msg, re.I):
            c.budget_flexibility = c.budget_flexibility or 5000
    if re.search(r"\bwait\b|\bhold off\b", msg, re.I):
        c.strategy = "WAIT_FOR_TARGET"
    if re.search(r"\blowest risk\b|\bsafe(?:st)?\b", msg, re.I):
        c.strategy = "LOWEST_RISK"

    m = re.search(r"\bcategory[:\-]\s*([\w\s]+)", msg, re.I)
    if m:
        c.category = m.group(1).strip().title()

    if c.strategy == "LOWEST_PRICE":
        c.quality_threshold = c.quality_threshold or 3.9
    return c


WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _word_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return WORD_NUMBERS.get(token.lower())


def _merge_constraints(base: Constraints, new: Constraints) -> Constraints:
    merged = base.model_copy(deep=True)
    for field_name, value in new.model_dump().items():
        if value is None:
            continue
        if field_name == "requirements":
            merged.requirements.update(new.requirements)
        else:
            setattr(merged, field_name, value)
    return merged
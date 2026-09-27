"""Typed AI-agent tool registry (V1.2).

The planner (LLM or rule-based) may ONLY call tools registered here. Every tool
declares a pydantic input schema; the registry validates every call so the
planner can never invent or mistype parameters. All outputs are plain JSON-safe
dicts - the LLM never sees raw prices/HTML, only precomputed offers.

Tools:
    search_products(query, category?, max_price?)
    compare_offers(product_id, include_shipping?)
    get_price_history(product_id, horizon_days?)
    forecast_price(product_id, horizon_hours?)
    target_probability(product_id, target_price, horizon_hours?)
    get_buy_wait_decision(product_id, deadline_days?, target_price?, strategy?)
    create_price_alert(product_id, target_price, user_id?)
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import PriceAlert, Product, ProductVariant
from prediction_engine.inference import PredictionEngine
from price_engine.history import load_variant_series, price_stats, series_to_points
from price_engine.offers import cheapest_offer, latest_offers
from schemas.alerts import ChatToolCall

logger = logging.getLogger(__name__)

MAX_QUERY = 100
STRATEGIES = (
    "IMMEDIATE",
    "LOWEST_PRICE",
    "BEST_VALUE",
    "WAIT_FOR_TARGET",
    "BEST_PERFORMANCE",
    "LOWEST_RISK",
)


class ToolCallError(Exception):
    """Raised when a tool call fails validation or domain lookup.

    The planner/interpreter converts this into a user-facing message - it is
    NOT a crash and never leaks stack traces.
    """


# ------------------------------------------------------------------- inputs

class SearchProductsIn(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY)
    category: str | None = Field(default=None, max_length=255)
    max_price: float | None = Field(default=None, ge=1)


class CompareOffersIn(BaseModel):
    product_id: uuid.UUID
    include_shipping: bool = True


class HistoryIn(BaseModel):
    product_id: uuid.UUID
    horizon_days: int = Field(default=365, ge=1, le=730)


class ForecastIn(BaseModel):
    product_id: uuid.UUID
    horizon_hours: int = Field(default=720, ge=1, le=24 * 365)


class TargetProbabilityIn(BaseModel):
    product_id: uuid.UUID
    target_price: float = Field(gt=0)
    horizon_hours: int = Field(default=168, ge=1, le=24 * 365)


class DecisionIn(BaseModel):
    product_id: uuid.UUID
    target_price: float | None = Field(default=None, gt=0)
    deadline_days: int | None = Field(default=None, ge=0, le=365)
    strategy: str = Field(default="IMMEDIATE")


class CreateAlertIn(BaseModel):
    product_id: uuid.UUID
    target_price: float = Field(gt=0)
    user_id: uuid.UUID | None = None


# ------------------------------------------------------------------ outputs

def _offer_dict(offer) -> dict[str, Any]:
    return offer.model_dump(mode="json")


@dataclass
class ToolContext:
    db: AsyncSession
    engine: PredictionEngine
    user_id: uuid.UUID | None = None


# ------------------------------------------------------------------- tools

class ToolCall:
    """One registered tool: name, description, validated inputs, callable."""

    def __init__(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        fn: Callable[[ToolContext, BaseModel], Any],
    ) -> None:
        self.name = name
        self.description = description
        self.input_model = input_model
        self._fn = fn

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_model.model_json_schema(),
        }

    async def call(self, ctx: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            parsed = self.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolCallError(
                f"tool '{self.name}' rejected arguments: {_first_error(exc)}"
            ) from exc
        result = await self._fn(ctx, parsed)
        if not isinstance(result, dict):
            raise ToolCallError(f"tool '{self.name}' returned a non-dict result")
        return result


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err.get("loc", ()))
    return f"{loc}: {err.get('msg', 'invalid')}" if loc else str(err.get("msg", "invalid"))


# ------------------------------------------------------------- tool bodies

async def _search_products(ctx: ToolContext, args: SearchProductsIn) -> dict:
    """AND-of-tokens search: 'sony headphones' matches each token somewhere
    in name/brand/model (so 'sony' + 'headphones' hits 'Sony WH-1000XM6')."""
    terms = [t for t in re.split(r"\s+", args.query.strip()[:MAX_QUERY]) if t]
    stmt = select(Product)
    if terms:
        stmt = stmt.where(
            and_(
                *[
                    or_(
                        Product.canonical_name.ilike(f"%{t}%"),
                        Product.brand.ilike(f"%{t}%"),
                        Product.model.ilike(f"%{t}%"),
                    )
                    for t in terms
                ]
            )
        )
    if args.category:
        stmt = stmt.where(Product.category == args.category)
    stmt = stmt.options(selectinload(Product.variants)).limit(10)
    products = list((await ctx.db.execute(stmt)).scalars().all())

    # If not found in local DB, universally scrape & ingest across retailers in real time
    if not products:
        from price_engine.collectors.universal_scraper import universal_scraper
        products = await universal_scraper.scrape_and_ingest(ctx.db, args.query, args.category)

    out = []
    for p in products:
        best = None
        for v in p.variants:
            offer = await cheapest_offer(ctx.db, v.id)
            if offer is not None:
                best = offer if (best is None or offer.effective_price < best.effective_price) else best
        price = float(best.effective_price) if best else None
        if args.max_price is not None and (price is None or price > args.max_price):
            continue
        out.append(
            {
                "id": str(p.id),
                "canonical_name": p.canonical_name,
                "brand": p.brand,
                "model": p.model,
                "category": p.category,
                "price_from": price,
                "variant_ids": [str(v.id) for v in p.variants],
            }
        )
    return {"query": args.query, "category": args.category, "products": out}


async def _compare_offers(ctx: ToolContext, args: CompareOffersIn) -> dict:
    variant_ids = await _variant_ids(ctx.db, args.product_id)
    if not variant_ids:
        raise ToolCallError("product not found or has no variants")
    offers = []
    for vid in variant_ids:
        offers.extend(
            await latest_offers(ctx.db, vid)  # TRUSTED gate - quarantine never surfaces
        )
    if not offers:
        raise ToolCallError("no trusted offers available for this product right now")
    offers.sort(key=lambda o: (o.expected_total, o.retailer_name))
    if not args.include_shipping:
        offers.sort(key=lambda o: (o.effective_price, o.retailer_name))
    return {
        "product_id": str(args.product_id),
        "count": len(offers),
        "cheapest": _offer_dict(offers[0]),
        "offers": [_offer_dict(o) for o in offers],
    }


async def _get_price_history(ctx: ToolContext, args: HistoryIn) -> dict:
    variant_ids = await _variant_ids(ctx.db, args.product_id)
    if not variant_ids:
        raise ToolCallError("product not found or has no variants")
    series = None
    for vid in variant_ids:
        s = await load_variant_series(ctx.db, vid, since_days=args.horizon_days)
        if not s.empty:
            series = s if series is None else series.combine_first(s)
    if series is None or series.empty:
        raise ToolCallError("no price history available for this product")
    stats = price_stats(series)
    points = series_to_points(series.tail(180))
    return {
        "product_id": str(args.product_id),
        "horizon_days": args.horizon_days,
        "observations": int(len(series)),
        "stats": stats,
        "points": points,
    }


async def _forecast_price(ctx: ToolContext, args: ForecastIn) -> dict:
    variant, series_groups = await _series_for_product(ctx, args.product_id)
    series = series_groups
    if series is None or series.empty:
        raise ToolCallError("no price history available for this product")
    try:
        result = ctx.engine.forecast_from_series(
            series,
            horizon=args.horizon_hours,
            category=variant.product.category if variant else None,
        )
    except ValueError as exc:
        raise ToolCallError(str(exc)) from exc
    q = result.quantile_at(1)
    return {
        "product_id": str(args.product_id),
        "current_price": result.current_price,
        "horizon_hours": args.horizon_hours,
        "median": q[0.5],
        "interval": result.interval,
        "confidence": result.confidence,
        "regime": result.regime["regime"],
        "warnings": result.warnings,
    }


async def _target_probability(ctx: ToolContext, args: TargetProbabilityIn) -> dict:
    variant, series = await _series_for_product(ctx, args.product_id)
    if series is None or series.empty:
        raise ToolCallError("no price history available for this product")
    horizons = {24, 168, 720, 2160, args.horizon_hours}
    probs, forecast, warnings = ctx.engine.target_probabilities_from_series(
        series,
        target=args.target_price,
        horizons_hours=sorted(h for h in horizons if h <= 24 * 365),
        category=variant.product.category if variant else None,
    )
    if not probs:
        raise ToolCallError("forecast unavailable: " + "; ".join(warnings or ["no data"]))
    return {
        "product_id": str(args.product_id),
        "target_price": args.target_price,
        "current_price": forecast.current_price if forecast else None,
        "probabilities": probs,
        "confidence": forecast.confidence if forecast else None,
        "warnings": warnings,
    }


async def _get_buy_wait_decision(ctx: ToolContext, args: DecisionIn) -> dict:
    if args.strategy not in STRATEGIES:
        raise ToolCallError(
            f"strategy must be one of {', '.join(STRATEGIES)}"
        )
    variant, series = await _series_for_product(ctx, args.product_id)
    if series is None or series.empty:
        raise ToolCallError("no price history available for this product")
    current = float(series.iloc[-1])
    target = args.target_price or round(current * 0.95, 2)

    horizons = [24 * 7, 24 * 30, 24 * 90]
    if args.deadline_days is not None:
        horizons = [24 * d for d in (1, 7, 14, 30) if d <= args.deadline_days]
        horizons += [24 * args.deadline_days]
        horizons = sorted(set(h for h in horizons if h >= 24))
    probs, forecast, warnings = ctx.engine.target_probabilities_from_series(
        series,
        target=target,
        horizons_hours=horizons,
        category=variant.product.category if variant else None,
    )
    if not probs or forecast is None:
        raise ToolCallError("forecast unavailable: " + "; ".join(warnings or ["no data"]))
    decision = ctx.engine.decide(
        current_price=current,
        probs=probs,
        forecast=forecast,
        target=target,
        max_wait_days=args.deadline_days,
    )
    return {
        "product_id": str(args.product_id),
        "strategy": args.strategy,
        **decision,
    }


async def _create_price_alert(ctx: ToolContext, args: CreateAlertIn) -> dict:
    variant_rows = await _variant_ids(ctx.db, args.product_id)
    if not variant_rows:
        raise ToolCallError("product not found or has no variants")
    alert = PriceAlert(
        user_id=ctx.user_id or args.user_id,
        product_variant_id=variant_rows[0],
        target_price=args.target_price,
        direction="below",
    )
    ctx.db.add(alert)
    await ctx.db.commit()
    await ctx.db.refresh(alert)
    return {"alert_id": str(alert.id), "product_variant_id": str(alert.product_variant_id),
            "target_price": float(alert.target_price), "active": True}


# --------------------------------------------------------------- registry

async def _variant_ids(db: AsyncSession, product_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(ProductVariant.id).where(ProductVariant.product_id == product_id)
    return [r[0] for r in (await db.execute(stmt)).all()]


async def _series_for_product(
    ctx: ToolContext, product_id: uuid.UUID
) -> tuple[ProductVariant | None, Any]:
    stmt = (
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id)
        .options(selectinload(ProductVariant.product))
        .limit(1)
    )
    variant = (await ctx.db.execute(stmt)).scalar_one_or_none()
    if variant is None:
        return None, None
    series = await load_variant_series(ctx.db, variant.id, since_days=730)
    return variant, series


def build_registry() -> dict[str, ToolCall]:
    return {
        t.name: t
        for t in (
            ToolCall("search_products", "search the catalog for a product", SearchProductsIn, _search_products),
            ToolCall("compare_offers", "compare all trusted retailer offers for a product", CompareOffersIn, _compare_offers),
            ToolCall("get_price_history", "load historical price statistics for a product", HistoryIn, _get_price_history),
            ToolCall("forecast_price", "forecast the market price of a product at a horizon", ForecastIn, _forecast_price),
            ToolCall("target_probability", "probability the price reaches a target within a horizon", TargetProbabilityIn, _target_probability),
            ToolCall("get_buy_wait_decision", "structured buy-now vs wait decision with reason codes", DecisionIn, _get_buy_wait_decision),
            ToolCall("create_price_alert", "create a price-drop alert for a product", CreateAlertIn, _create_price_alert),
        )
    }


class ToolRegistry:
    """Validated gateway - the ONLY way tools are invoked."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolCall] = build_registry()

    def list_tools(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def has(self, name: str) -> bool:
        return name in self._tools

    async def call(
        self,
        ctx: ToolContext,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolCallError(
                f"unknown tool '{name}'; available: {', '.join(sorted(self._tools))}"
            )
        return await tool.call(ctx, arguments)


def tool_calls_trace(calls: list[ChatToolCall]) -> list[dict[str, Any]]:
    """Convert validated calls for the chat log (no internal state leaks)."""
    return [{"tool": c.tool, "arguments": c.arguments} for c in calls]
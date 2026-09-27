"""Raw -> validated -> quarantined -> matched -> trusted observation pipeline.

Every observation enters as a RawObservation. Nothing reaches a trusted table
without passing validation, anomaly screening and product-identity matching.
Only TRUSTED-tier observations feed forecasters (queries filter on trust_tier).

Outcome per result (returned as a report dict):
    raw_id, listing_id, status, quality, tier, anomaly, match_decision,
    events_generated
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import (
    Listing,
    MatchCandidate,
    PriceObservation,
    Product,
    ProductVariant,
    RawObservation,
    Retailer,
    SystemEvent,
)
from events.bus import BaseEvent, EventBus, PriceChangedEvent
from price_engine.anomaly import detect_anomaly
from price_engine.changes import ChangeEvent, detect_changes
from price_engine.collectors.base import CollectionResult
from price_engine.history import load_listing_series
from price_engine.quality import score_observation, validate_state
from product_engine.matching import (
    AUTO_MATCH_THRESHOLD,
    REVIEW_MATCH_THRESHOLD,
    TextEmbedder,
    decide,
    match_score,
    normalize_identifier,
)

HISTORY_WINDOW_OBS = 90


class IngestionPipeline:
    def __init__(
        self,
        db_factory: async_sessionmaker,
        bus: EventBus | None = None,
        embedder: TextEmbedder | None = None,
    ) -> None:
        self._db_factory = db_factory
        self._bus = bus
        self._embedder = embedder or TextEmbedder()
        self._listing_cache: dict[str, dict] = {}

    async def ingest_results(
        self,
        results: list[CollectionResult],
        *,
        source_mode: str = "page",
        collected_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        async with self._db_factory() as db:
            catalog = await self._load_catalog(db)
            for result in results:
                report = await self._ingest_one(
                    db, catalog, result, source_mode=source_mode, collected_at=collected_at
                )
                reports.append(report)
            await db.commit()
            for report in reports:
                await self._publish_reported_events(report)
        return reports

    # ------------------------------------------------------------------ steps

    async def _ingest_one(
        self,
        db: AsyncSession,
        catalog: list[tuple[ProductVariant, dict[str, Any]]],
        result: CollectionResult,
        *,
        source_mode: str,
        collected_at: datetime | None,
    ) -> dict[str, Any]:
        ts = collected_at or datetime.now(timezone.utc)
        state = result.state()
        identity = dict(result.identity or {})
        identity.setdefault("title", result.title)

        validation_errors = validate_state(state)
        raw = RawObservation(
            source=result.source_metadata.get("name", "unknown"),
            collector_run_id=str(result.source_metadata.get("run_id", "")),
            retailer_name=result.source_metadata.get("retailer"),
            identity=identity,
            payload={"state": state, "raw": result.raw, "source_metadata": result.source_metadata},
            collected_at=ts,
            status="QUARANTINED" if validation_errors else "RAW",
            validation_errors=validation_errors,
        )
        db.add(raw)
        await db.flush()

        if validation_errors:
            report = self._base_report(raw, result, ts)
            report.update(
                status="QUARANTINED",
                reasons=validation_errors,
                events=[],
            )
            return report

        retailer = await self._get_or_create_retailer(
            db, result.source_metadata.get("retailer") or "unknown"
        )

        # 1) product identity resolution (conservative)
        listing, match_score_v, match_decision, details = await self._resolve_listing(
            db, catalog, raw.id, result, identity, retailer
        )

        # 2) anomaly screening against this listing's history
        history = await load_listing_series(db, listing.id, field="effective_price")
        hist_vals = [float(v) for v in history.tail(HISTORY_WINDOW_OBS).tolist()]
        previous = None
        prev_obs = await self._last_observation(db, listing.id)
        if prev_obs is not None and prev_obs.observed_at != ts:
            previous = float(prev_obs.effective_price or prev_obs.price or 0.0) or None

        verdict = detect_anomaly(
            result.effective_price, hist_vals, previous=previous,
            retailer=retailer.name if retailer else None,
        )

        # 3) quality score (match confidence + source + validity + freshness)
        quality = score_observation(
            state,
            source_mode=source_mode,
            collected_at=ts,
            match_confidence=match_score_v,
        )
        # an anomaly demotes TRUSTED -> REVIEW; REVIEW matches are always REVIEW
        # (identity unverified) - neither ever promotes QUARANTINED.
        tier = quality.tier
        if match_decision == "REVIEW":
            tier = "REVIEW"
        if verdict.is_anomaly and tier != "QUARANTINED":
            tier = "REVIEW"

        obs = PriceObservation(
            listing_id=listing.id,
            price=state.get("price"),
            mrp=state.get("mrp"),
            shipping=state.get("shipping"),
            coupon_discount=state.get("coupon_discount"),
            bank_discount=state.get("bank_discount"),
            effective_price=result.effective_price,
            availability=state.get("availability"),
            observed_at=ts,
            rating=state.get("rating"),
            review_count=state.get("review_count"),
            delivery_estimate=state.get("delivery_estimate"),
            source=str(result.source_metadata.get("name", "")),
            source_metadata=result.source_metadata,
            quality_score=quality.score,
            trust_tier=tier,
        )
        db.add(obs)
        await db.flush()

        # 4) change events
        change_events = detect_changes(prev_obs, obs) if prev_obs is not None else []
        for ev in change_events:
            await self._persist_event(
                db, ev.event_type, "listing", str(listing.id), {
                    **ev.payload, "observation_id": obs.id, "listing_id": str(listing.id),
                }
            )

        # 5) finalize raw row
        raw.status = "VERIFIED"
        raw.resolved_listing_id = listing.id
        raw.anomaly_score = verdict.score
        raw.anomaly_reasons = verdict.reasons
        raw.anomaly_status = "CONFIRMED" if verdict.is_anomaly else "CHECKED"
        raw.quality_score = quality.score
        raw.match_confidence = match_score_v
        raw.match_method = details.get("method", match_decision)

        report = self._base_report(raw, result, ts)
        report.update(
            listing_id=str(listing.id),
            status="VERIFIED",
            quality=quality.as_dict(),
            anomaly=verdict.as_dict(),
            tier=tier,
            match_decision=match_decision,
            match_score=match_score_v,
            events=[e.event_type for e in change_events],
            change_events=[e.as_dict() for e in change_events],
            observation_id=obs.id,
            availability=state.get("availability"),
            seller_name=state.get("seller_name"),
        )
        return report

    async def _resolve_listing(
        self,
        db: AsyncSession,
        catalog: list[tuple[ProductVariant, dict[str, Any]]],
        raw_id: int,
        result: CollectionResult,
        identity: dict[str, Any],
        retailer: Retailer,
    ) -> tuple[Listing, float, str, dict[str, Any]]:
        """Find best variant match, then the listing for this retailer.

        AUTO_MATCH (>=0.995): reuse listing.
        REVIEW (0.95-0.995): new listing + pending MatchCandidate (never merge).
        NO_MATCH (<0.95): new product/variant/listing (distinct catalog entry).
        """
        best, best_score = None, 0.0
        for variant, cand_identity in catalog:
            s = match_score(identity, cand_identity, self._embedder)
            if s > best_score:
                best, best_score = variant, s
        decision = decide(best_score)
        method = "identifier" if best is not None and best_score >= 0.99 else "text/attrs"

        if decision == "AUTO_MATCH" and best is not None:
            listing = await self._find_listing(db, retailer.id, best.id)
            if listing is not None:
                return listing, best_score, decision, {"method": method}

        # REVIEW / NO_MATCH (or missing listing): build a distinct catalog entry.
        # Never merge below the AUTO_MATCH bar.
        listing = await self._create_listing(db, result, retailer, best)

        if decision == "REVIEW" and best is not None:
            await self._create_candidate(db, raw_id, listing, best, best_score, method)

        # a listing created from THIS observation carries high identity confidence
        # (the listing and the observation are the same object), even though the
        # observation did not match an existing catalog entry. REVIEW matches keep
        # their raw (unverified) confidence so the tier gate catches them.
        confidence = max(best_score, 0.9) if decision == "NO_MATCH" else best_score
        return listing, confidence, decision, {"method": method}

    async def _create_candidate(
        self, db: AsyncSession, raw_id: int, listing: Listing | None,
        variant: ProductVariant | None, score: float, method: str,
    ) -> None:
        fp = self._fingerprint(variant)
        if fp:
            rows = await db.execute(
                select(MatchCandidate.identity).where(MatchCandidate.status == "PENDING")
            )
            for (ident,) in rows.all():
                if (ident or {}).get("fp") == fp:
                    return
        db.add(
            MatchCandidate(
                raw_observation_id=raw_id,
                listing_id=listing.id if listing else None,
                suggested_variant_id=variant.id if variant else None,
                identity={"fp": fp} if fp else {},
                score=score,
                method=method,
                details={"thresholds": {"auto": AUTO_MATCH_THRESHOLD, "review": REVIEW_MATCH_THRESHOLD}},
            )
        )
        await db.flush()

    @staticmethod
    def _fingerprint(variant: ProductVariant | None) -> str:
        if variant is None:
            return ""
        for key in ("gtin", "sku"):
            v = getattr(variant, key, None)
            n = normalize_identifier(v)
            if n:
                return f"{key}:{n}"
        return ""

    async def _find_listing(
        self, db: AsyncSession, retailer_id: uuid.UUID, variant_id: uuid.UUID
    ) -> Listing | None:
        stmt = select(Listing).where(
            Listing.retailer_id == retailer_id,
            Listing.product_variant_id == variant_id,
            Listing.active.is_(True),
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def _create_listing(
        self, db: AsyncSession, result: CollectionResult,
        retailer: Retailer, variant: ProductVariant | None,
    ) -> Listing:
        if variant is None:
            product = Product(
                brand=(result.identity or {}).get("brand"),
                model=(result.identity or {}).get("model"),
                canonical_name=result.title or f"Unidentified {retailer.name} product",
            )
            db.add(product)
            await db.flush()
            variant = ProductVariant(
                product_id=product.id,
                variant_name=result.title,
                gtin=_clean_ident((result.identity or {}).get("gtin")),
                sku=_clean_ident((result.identity or {}).get("sku")),
            )
            db.add(variant)
            await db.flush()
        listing = Listing(
            product_variant_id=variant.id,
            retailer_id=retailer.id,
            seller_name=result.seller_name,
            url=str(result.source_metadata.get("url", "")),
            listing_title=result.title,
        )
        db.add(listing)
        await db.flush()
        return listing

    async def _get_or_create_retailer(self, db: AsyncSession, name: str) -> Retailer:
        stmt = select(Retailer).where(Retailer.name == name)
        retailer = (await db.execute(stmt)).scalar_one_or_none()
        if retailer is None:
            retailer = Retailer(name=name, currency="INR")
            db.add(retailer)
            await db.flush()
        return retailer

    async def _last_observation(self, db: AsyncSession, listing_id: uuid.UUID) -> PriceObservation | None:
        stmt = (
            select(PriceObservation)
            .where(PriceObservation.listing_id == listing_id)
            .order_by(PriceObservation.observed_at.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def _load_catalog(
        self, db: AsyncSession
    ) -> list[tuple[ProductVariant, dict[str, Any]]]:
        stmt = select(ProductVariant, Product).join(Product, ProductVariant.product_id == Product.id)
        catalog: list[tuple[ProductVariant, dict[str, Any]]] = []
        for variant, product in (await db.execute(stmt)).all():
            catalog.append(
                (
                    variant,
                    {
                        "gtin": variant.gtin,
                        "sku": variant.sku,
                        "model": product.model,
                        "brand": product.brand,
                        "title": variant.variant_name or product.canonical_name,
                        "canonical_name": product.canonical_name,
                        "category": product.category,
                        "subcategory": product.subcategory,
                        "color": variant.color,
                        "storage": variant.storage,
                        "size": variant.size,
                        "condition": variant.condition,
                    },
                )
            )
        return catalog

    async def _persist_event(
        self, db: AsyncSession, event_type: str, entity_type: str, entity_id: str, payload: dict[str, Any]
    ) -> None:
        db.add(
            SystemEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                occurred_at=datetime.now(timezone.utc),
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload,
            )
        )

    async def _publish_reported_events(self, report: dict[str, Any]) -> None:
        if self._bus is None:
            return
        listing_id = report.get("listing_id")
        ctx = {"variant_id": None, "retailer_name": None}
        if listing_id:
            async with self._db_factory() as db:
                ctx = await self._listing_context(db, listing_id)
        base = {
            "listing_id": listing_id,
            "variant_id": ctx.get("variant_id"),
            "retailer_name": ctx.get("retailer_name"),
            "effective_price": report.get("effective_price"),
            "availability": report.get("availability"),
            "tier": report.get("tier"),
            "observed_at": report.get("observed_at"),
        }
        for change in report.get("change_events", []):
            await self._bus.publish(
                PriceChangedEvent(
                    event_type=change.get("event_type", "price.changed"),
                    payload={**change.get("payload", {}), **base},
                )
            )
        await self._bus.publish(
            BaseEvent(
                event_type="price.collected",
                payload={**base, "observation_id": report.get("observation_id")},
            )
        )

    async def _listing_context(self, db: AsyncSession, listing_id: str) -> dict[str, str | None]:
        key = str(listing_id)
        if key in self._listing_cache:
            return self._listing_cache[key]
        try:
            listing_uuid = uuid.UUID(key)
        except ValueError:
            return {"variant_id": None, "retailer_name": None}
        row = (
            await db.execute(
                select(Listing, Retailer.name)
                .join(Retailer, Listing.retailer_id == Retailer.id)
                .where(Listing.id == listing_uuid)
            )
        ).first()
        ctx = {
            "variant_id": str(row[0].product_variant_id) if row else None,
            "retailer_name": row[1] if row else None,
        }
        self._listing_cache[key] = ctx
        return ctx

    @staticmethod
    def _base_report(raw: RawObservation, result: CollectionResult, ts: datetime) -> dict[str, Any]:
        return {
            "raw_id": raw.id,
            "listing_id": str(raw.listing_id) if raw.listing_id else None,
            "source": raw.source,
            "collected_at": ts.isoformat(),
            "effective_price": result.effective_price,
        }


def min_tier(a: str, b: str) -> str:
    order = {"TRUSTED": 0, "REVIEW": 1, "QUARANTINED": 2}
    return a if order.get(a, 2) >= order.get(b, 2) else b


def _clean_ident(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value).strip()[:255] if str(value).strip() else None

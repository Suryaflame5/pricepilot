"""Explanation contract (V1.2).

Every answer is built ONLY from structured tool outputs (Product facts ->
Offers -> Statistics -> Forecast -> Probability -> Reliability -> Decision).
The narrator formats numbers verbatim; it never recomputes and never lets an
LLM rewrite figures. Every number in a reply is traceable to a tool result.

Reason codes map 1:1 to fixed, honest human text - no embellishment.
"""

from typing import Any

INR = lambda v: f"\u20b9{v:,.0f}" if v is not None else "n/a"  # noqa: E731

RECOMMENDATION_TEXT = {
    "BUY_NOW": "buy now",
    "WAIT": "wait",
    "INSUFFICIENT_CONFIDENCE": "insufficient confidence to recommend definitively",
}

REASON_TEXT = {
    "WAIT_EXPECTED_VALUE_POSITIVE": "waiting has a positive expected value today",
    "TARGET_ATTAINABLE_WITHIN_HORIZON": "your target price is reachable within the forecast window",
    "WAIT_EXPECTED_VALUE_NEGATIVE": "the expected benefit of waiting does not justify the delay",
    "USER_DEADLINE_SHORTER_THAN_HORIZON": "your deadline is shorter than the forecast window, so waiting would overshoot it",
    "INSUFFICIENT_EVIDENCE": "not enough evidence for a strong call yet",
    "LOW_CONFIDENCE_ADVISORY": "advisory only - confidence is low",
    "NO_FORECAST_AVAILABLE": "no forecast available for this product",
}


def explain(parts: dict[str, Any]) -> str:
    out: list[str] = []

    product = parts.get("product") or {}
    name = product.get("name") or f"product {parts.get('product_id', '')[:8]}"
    out.append(f"**{name}**" + (f" ({product.get('category')})" if product.get("category") else ""))

    offers = parts.get("offers") or {}
    if offers.get("offers"):
        cheap = offers["cheapest"]
        total = cheap.get("effective_price")
        if cheap.get("shipping"):
            total = round(float(cheap["effective_price"] or 0) + float(cheap.get("shipping") or 0), 2)
        out.append(
            f"**Current offers:** {len(offers['offers'])} across retailers - cheapest "
            f"{INR(total)} at {cheap.get('retailer_name')} "
            f"({cheap.get('availability', 'unknown')})."
        )
        extra = [
            f"- {o.get('retailer_name')}: {INR(o.get('effective_price'))}"
            + (f" ({o.get('availability')})" if o.get("availability") else "")
            for o in offers["offers"][1:4]
        ]
        if extra:
            out.extend(extra)

    stats = parts.get("stats")
    if stats:
        out.append(
            f"**12-month history:** 30d range {INR(stats.get('min_30d'))}-{INR(stats.get('max_30d'))} "
            f"(mean {INR(stats.get('mean_30d'))}); today's price sits at the "
            f"**{int((stats.get('price_percentile_90d') or 0) * 100)}th percentile** "
            f"({int(stats.get('observations_90d') or 0)} observations in 90d)."
        )

    forecast = parts.get("forecast")
    if forecast:
        interval = forecast.get("interval") or {}
        conf = forecast.get("confidence") or {}
        median = forecast.get("median")
        median_txt = f"\u20b9{median:,.2f}" if isinstance(median, (int, float)) else "n/a"
        out.append(
            f"**Forecast ({_horizon_label(forecast.get('horizon_hours', '?'))}):** median "
            f"{median_txt}, calibrated 90% interval "
            f"{INR(interval.get('lower'))}-{INR(interval.get('upper'))} "
            f"(regime: {forecast.get('regime', 'unknown')})."
        )
        out.append(
            f"**Reliability:** model confidence **{conf.get('level', 'INSUFFICIENT')}** "
            f"(score {conf.get('score', 0):.2f}) - forecast {conf.get('forecast_confidence', 0):.2f}, "
            f"model {conf.get('model_reliability', 0):.2f}, data {conf.get('data_reliability', 0):.2f}."
        )

    decision = parts.get("decision")
    if decision:
        target_prob = decision.get("target_probability")
        lines = [f"**Recommendation: {RECOMMENDATION_TEXT.get(decision.get('recommendation', '?'), decision.get('recommendation'))}**"]
        if decision.get("current_price") is not None:
            lines[0] += f" (current {INR(decision.get('current_price'))})"
        if decision.get("expected_price") is not None:
            lines[0] += f" - expected {INR(decision.get('expected_price'))} in {decision.get('horizon_days')}d"
        if target_prob is not None:
            lines.append(f"Probability of reaching {INR(decision.get('target'))} within {decision.get('horizon_days')}d: **{target_prob:.0%}**")
        codes = [
            REASON_TEXT.get(c, c.replace("_", " ").lower())
            for c in (decision.get("reason_codes") or [])
        ]
        if codes:
            lines.append("Why: " + "; ".join(codes[:3]))
        out.append("\n".join(lines))

    prob = parts.get("probability")
    if prob and not decision:
        targets = prob.get("probabilities") or {}
        if targets:
            lines = ", ".join(
                f"{k}: {v:.0%}" for k, v in sorted(
                    targets.items(), key=lambda kv: (int(kv[0].rstrip('d')) if kv[0].rstrip('d').isdigit() else 9999)
                )
            )
            out.append(f"**Probability of reaching {INR(prob.get('target_price'))}:** {lines}")

    alert = parts.get("alert")
    if alert:
        out.append(
            f"**Alert created:** I'll notify you when the price drops to "
            f"{INR(alert.get('target_price'))} (id {str(alert.get('alert_id', ''))[:8]})."
        )

    warnings = _collect_warnings(parts)
    if warnings:
        out.append("Note: " + "; ".join(warnings[:3]))

    return "\n\n".join(out)


def _horizon_label(hours: Any) -> str:
    if isinstance(hours, int) and hours % 24 == 0:
        return f"{hours // 24}d"
    return str(hours)


def _collect_warnings(parts: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for key in ("forecast", "decision"):
        for w in (parts.get(key) or {}).get("warnings") or []:
            if w not in warnings:
                warnings.append(w)
    return warnings
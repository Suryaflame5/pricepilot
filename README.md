# PricePilot

**Rigorous price forecasting and shopping-decision engine.** Not "an AI that claims
99% accuracy" — a system that combines statistics, time-series forecasting, gradient
boosting, probabilistic modeling, ensemble learning, calibration, conformal
prediction and continuous backtesting, and **refuses to make confident claims when
the evidence isn't strong enough.**

Every forecast reports three separate scores (blueprint §final):

```text
FORECAST          ₹28,000–₹30,400        (conformal prediction interval)
PROBABILITY       73% chance of reaching ₹28,000   (calibrated)
MODEL RELIABILITY 96% historical calibration       (measured, not manufactured)
```

## Repository layout

```text
├── apps/web/                 Next.js 14 UI: chat, search, product, history,
│                             forecast, watchlist, alerts, settings
├── services/
│   ├── api/                  FastAPI: routes (products, prices, predictions,
│   │                         alerts, chat, watchlist, matching, monitoring)
│   ├── price_engine/         collectors (retailer adapters), quality pipeline,
│   │                         anomaly detection, change detection, history
│   ├── product_engine/       identity matching (identifiers/text/embeddings,
│   │                         conservative merge policy, review queue)
│   ├── prediction_engine/    models → ensemble → calibration (hierarchical) →
│   │                         conformal (regime-conditional) → confidence (three
│   │                         components) → decision; model registry, shadow,
│   │                         drift, reconciliation
│   ├── ai_agent/             tool-calling assistant (rule-based v1 planner)
│   └── alert_engine/         scheduled target-price trigger scanner
├── packages/
│   ├── database/             SQLAlchemy models + async session + hypertable init
│   ├── schemas/              Pydantic API contracts
│   └── events/               event schemas + stream bus (Redis Streams)
├── ml/
│   ├── datasets/             synthetic series generator + DB seed script
│   ├── experiments/          walk-forward backtest CLI + champion/challenger runner
│   ├── training/             GBM training CLI with baseline gate
│   ├── backtesting/          continuous backtest: calibration + conformal +
│   │                         registry refresh + monitoring report
│   └── model_registry/       ensemble weights, registry.json, calibration
│                             curves, conformal buckets, shadow logs
├── infrastructure/           TimescaleDB init, V1.1 migration SQL, Dockerfiles
└── tests/                    pipeline, reliability, collectors + API smoke tests
```

## The prediction pipeline (V1.1)

```text
history ──► feature engine ──► model zoo ──► ensemble ──► quantile paths
               │                    │            │
               │              naive / MA / ES /    │
               │              seasonal / ARIMA /   │
               │              GBM quantile         │
               ▼                                   ▼
        regime + change-point            probabilistic layer
        (CUSUM heuristic)                P(price ≤ target)
               │                                   │
               └──────────────┬────────────────────┘
                              ▼
       calibration — hierarchical isotonic, min-pairs guarded:
       (category:horizon:regime:retailer) → (category:horizon:regime)
       → (category:horizon) → global      [keys are HOURS]
                              ▼
   conformal interval — split conformal on backtest residuals,
   bucketized by regime (wider under PROMOTION/volatility = correct)
                              ▼
   confidence — THREE independently measured components:
       forecast_confidence | model_reliability | data_reliability
       decision_confidence = 0.40·forecast + 0.35·model + 0.25·data
                              ▼
        decision: EU(buy) vs EU(wait) — or "insufficient confidence"
```

The "deep learning must beat the baseline" rule is enforced: models are only
included in the ensemble if they earn it out-of-sample (`ml/experiments/run_backtest.py`).
Champion/challenger promotion (`ml/experiments/run_champion_challenger.py`) requires
winning on MAE, quantile loss, ECE, coverage error, directional accuracy and stability
with no regression beyond tolerance on any horizon.

## Data pipeline (V1.1): quarantine-first

```text
collector (feed/page/mock) ──► raw_observations (RAW)
        │
        ├─ validation errors? ──► QUARANTINED (nothing reaches forecasters)
        │
        ├─ anomaly screen (robust z / sudden-change / retailer thresholds /
        │   isolation forest) ──► anomaly demotes TRUSTED → REVIEW
        │
        ├─ product identity match (conservative):
        │       ≥0.995 auto-match · 0.95–0.995 review candidate · <0.95 no merge
        │
        ├─ quality score: 0.30 source + 0.20 match + 0.25 price + 0.15
        │   availability + 0.10 freshness → TRUSTED / REVIEW / QUARANTINED
        │
        └─ trusted observation + change events
           (price.changed/dropped/spike, stock.changed, seller.changed,
            promotion.started/ended) → system_events (replayable) + stream
```

## Reliability contract (V1.1)

- **Model registry** (`prediction_engine/registry.py`): EXPERIMENT → CANDIDATE →
  SHADOW → CHAMPION → RETIRED; every promotion is evidence-gated on identical
  backtest folds; per-category and per-horizon breakdowns required.
- **Shadow inference** (`prediction_engine/shadow.py`): challengers run alongside
  the champion, logged to JSONL, never served to users.
- **Drift + coverage monitoring** (`prediction_engine/drift.py`): KS test on return
  distributions (PSI as diagnostic), rolling 90% interval coverage vs
  `prediction_outcomes` — drift triggers recalibration, never silent degradation.
- **Retailer reconciliation** (`prediction_engine/reconciliation.py`):
  `P_retailer(t) = P_market(t) + R_retailer(t)`, offsets recentered so the market
  series represents the typical retailer.
- **The 99% requirement is a measurable contract**: calibration curves, reliability
  diagrams, ECE, Brier, coverage and sharpness are produced and exposed
  (`/monitoring/*`), not claimed.

## Quickstart

### Option A — Docker (Postgres + TimescaleDB + Redis + API + web)

```bash
cp .env.example .env
docker compose up --build
```

Then seed synthetic demo data (5 products, 365 days of history):

```bash
docker compose exec api python -m ml.datasets.seed_db
docker compose exec api python -m ml.experiments.run_backtest --learn-weights
docker compose exec api python -m ml.backtesting.run           # continuous refresh
```

- UI: http://localhost:3000 · API docs: http://localhost:8000/docs

### Option B — local dev

```bash
# backend
python -m venv .venv
.venv\Scripts\activate            # (Windows) / source .venv/bin/activate
pip install -e ".[ml,dev]"
docker compose up db redis        # or set DATABASE_URL to any asyncpg URL
python -m ml.datasets.seed_db
uvicorn api.main:app --reload --app-dir services

# frontend
cd apps/web
npm install
npm run dev
```

For an existing V1 database, apply `infrastructure/postgres/migrations/001_v11.sql`.

## V1.2 — Live Commerce Intelligence (product layer)

ML core is frozen; V1.2 adds the product-layer surfaces on top of it:

### Adaptive polling (`ml/intake/run_scheduler.py`, `services/price_engine/collectors/scheduler.py`)

Continuous price intelligence: the scheduler computes a poll interval per listing
from measured volatility, active alert count and price-change rate, multiplied by
a retailer pace factor, clamped to [30 min, 7 d]. Calm listings get polled ~every
8 h; volatile/alerted ones much faster.

```bash
.venv\Scripts\python.exe -m ml.intake.run_scheduler --round   # one pass (dry-run: --dry-run)
.venv\Scripts\python.exe -m ml.intake.run_scheduler           # run forever
```

### Canonical Offer (`packages/schemas/offer.py`, `services/price_engine/offers.py`)

Every price point is projected to an `Offer` with a tier gate:
`QUARANTINED` never surfaces; the default `min_tier="TRUSTED"` keeps `REVIEW`
out of comparisons. `expected_total` is deterministic: the pipeline's
`effective_price` already includes shipping and coupons, so the user pays exactly
that. `latest_offers` / `cheapest_offer` / `offer_by_listing` are the only paths
the compare view and purchase layer use.

### Agent planner (`services/ai_agent/planner.py`)

`POST /chat` now runs a typed tool-calling agent: intent classification →
deterministic backend (search → compare → history → forecast → decide), with an
LLM backend behind `PRICEPILOT_LLM_BASE_URL` / `PRICEPILOT_LLM_API_KEY`
(`PRICEPILOT_LLM_MODEL`, default `gpt-4o-mini`) that falls back to the
deterministic backend on any failure. Constraints (max budget, wait horizon —
including word-numbers like "two months") persist across turns per
conversation. All 7 tools validate inputs through a pydantic registry
(`services/ai_agent/tools.py`); narration (`narrator.py`) renders ONLY what the
tools returned — no invented numbers.

### Purchase workflow with two confirmations (`services/purchase/`)

`ShoppingSession` follows the spec-locked state machine
`SEARCHING → SELECTED → PRICE_VERIFIED → CHECKOUT_READY → USER_CONFIRMED → ORDER_PLACED → TRACKING → COMPLETED`:

1. **select offer** (session-owned listing)
2. **verify price** — re-read from DB, requires `SELECTED`
3. **confirm offer** — requires `PRICE_VERIFIED`; prepares the provider checkout
4. **place order** — requires `CHECKOUT_READY`; re-validates the price from the
   DB immediately before purchase; drift > 0.5% blocks with
   "price changed since you confirmed"
5. **order status** — tracked via the provider

Only retailer-permitted providers are registered (`services/purchase/registry.py`);
an unregistered retailer (e.g. "croma") is a hard error, never a fallback.
The provider session id is persisted on the session, so the two confirmations
share one server-side checkout. Routes: `POST /shopping-sessions`,
`/select`, `/verify-price`, `/confirm`, `/place-order`, `/order`,
`GET /shopping-sessions/providers/list`.

### Prediction Ledger (`ml/ledger/resolve_outcomes.py`)

Every elapsed prediction is resolved against the minimum effective price over its
horizon window and stored as an outcome — measured performance only, no
self-reported metrics:

```bash
.venv\Scripts\python.exe -m ml.ledger.resolve_outcomes
```

`GET /monitoring/ledger` reports per-category/per-horizon coverage_90, MAE,
median error and Brier from the resolved outcomes.

## Example conversation

> **User:** Should I buy the Sony WH-1000XM6?

> **Agent:** **Best current offer: ₹27,022 (Croma)** — 17th percentile of 12 months.
> 30-day median forecast **₹26,688**, calibrated 90% interval **₹22,158–₹31,218**.
> Regime NORMAL · model confidence **MEDIUM (0.71)**.

## Tests

```bash
python -m pytest tests/ -v        # 164 tests: pipeline, matching, reliability,
                                  # collectors, scheduler, offers, planner,
                                  # purchase + realtime + API smoke on SQLite
```

## API surface (v1.2)

| Endpoint | Purpose |
|---|---|
| `POST /prices/ingest` | quarantine-first raw intake (quality + anomaly + match) |
| `POST /predictions/price` | quantile forecast + conformal interval + 3-part confidence |
| `POST /predictions/target` | P(price ≤ target) per horizon + wait window |
| `POST /predictions/decision` | BUY_NOW / WAIT / INSUFFICIENT_CONFIDENCE |
| `GET /matching/candidates` + decision | product-identity review queue (0.95–0.995 band) |
| `GET /monitoring/drift,coverage,registry,calibration,ledger` | reliability-contract surfaces + prediction ledger |
| `POST /chat` | agent (search → compare → history → forecast → calibrate → decide) with persistent constraints |
| `WS /ws/live?topics=&entities=` | realtime push: typed change events (`price.changed`, `stock.changed`, `promotion.changed`, `prediction.updated`, `decision.changed`, `alert.triggered`) as versioned envelopes `{v, event_id, event_type, aggregate_type, aggregate_id, sequence, occurred_at, observed_at, payload}`; heartbeat 20s |
| `POST /shopping-sessions` + select/verify-price/confirm/place-order/order | two-confirmation purchase workflow |
| `GET/POST /products`, `/prices`, `/alerts`, `/watchlist` | catalog, history, alerts |

## Honesty guarantees

- Confidence is a function of data quantity, freshness, model agreement,
  backtested accuracy, calibration error, volatility and regime stability —
  split into measured forecast / model / data components.
- Model disagreement widens uncertainty; it is never hidden.
- Calibration curves only fit with a minimum number of (probability, outcome)
  pairs; otherwise the key falls back to a coarser bucket — never calibrated on
  a handful of observations.
- If evidence is insufficient, the system says **"Insufficient confidence"** —
  it does not manufacture a number.
- If a product/category eventually demonstrates 99% *measured* calibration,
  that number gets exposed — never fabricated.

## Retailer collectors (compliance)

Adapters exist for amazon/flipkart/croma/reliance_digital (`collectors/adapters.py`),
with shared retry/rate-limit/degradation handling, JSON-LD/meta parsing and
official-feed mode. Enable per retailer only where terms of service permit
collection or an official feed/API is available — never CAPTCHA/anti-bot evasion.
`collectors/registry.py` gates each adapter; page-mode is off by default.

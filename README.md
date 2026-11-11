# Project Lucy

Independent prototype for Paytm Build for India AI Hackathon 2026, Track 3: Autonomous AI Teammates. **Lucy** is the customer-facing crew lead; **CrewOS** is its commerce execution foundation. The product direction is Adaptive Commerce Orchestration across procurement, group purchasing, surplus and rental alternatives, with payment and support continuity. This is not an official Paytm product.

Phase 0 preserves the navy/cyan mobile customer and merchant UI, 24 merchants, 400 demo customers, 14,304 synthetic historical transactions and existing ML insights. It adds durable operational commerce, approval boundaries and honest simulated payments. Autonomous LLM planning is not implemented.

## Run locally

Requires Node 20.19+ (or compatible newer Node), Python 3.11–3.13.

```sh
npm ci
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-test.txt
cp .env.example .env
npm run backend
```

In another terminal, `npm run dev`, then open http://127.0.0.1:5173. `#/app` opens the demo. Backend reads `.env`; Vite reads `VITE_` settings. Defaults work without an env file. No ML training or snapshot rebuild is required. `backend/requirements-dev.txt` adds the optional historical ML toolchain; it is unnecessary for serving the app.

```sh
npm run build
npm run test:backend
npm run qa
npm run reset
```

Playwright starts local servers if absent and runs desktop/mobile Chromium. Install its browser with `npx playwright install chromium` if needed. Reset requires the running API and the local developer token; it deletes operational demo records only. It is disabled on hosted/production instances. Tests use a temporary SQL database and never reset the developer's SQLite database.

## Architecture

- React/TypeScript, Tailwind and existing hash navigation; payment UI extracted from `src/App.tsx` into `src/components/PaymentFlow.tsx`.
- FastAPI `backend/app.py` keeps the historical JSON snapshot read-only. Pulse, pricing, loyalty modelling, rewards recommendations and loan coaching remain precomputed historical insights.
- SQLAlchemy `backend/domain_models.py`, `backend/services.py` and `backend/commerce.py` provide the mutable operational store, services and typed APIs. Money is integer paise, identifiers are UUIDs and timestamps are UTC.
- `/docs` exposes OpenAPI. `/agents` declares all eight specialists with honest PLANNED/LIMITED status. `/tools` publishes tool input schemas. `POST /missions` is Lucy's structured goal entry point; it records goals rather than inventing an execution trace.

See [ARCHITECTURE.md](docs/ARCHITECTURE.md), [DEMO.md](DEMO.md), [PAYTM_TECH.md](PAYTM_TECH.md) and the original [audit evidence](docs/BASELINE.md).

## Persistence and deployment

Local single-instance development uses `backend/lucy.db` with SQLite WAL, foreign keys and explicit transaction boundaries. Version 1 initialization creates the schema deterministically and seeds missing identities/offers without replacing operational state. Schema version mismatches fail startup; later schema changes require an explicit migration, not `create_all` pretending to alter existing tables.

Hosted environments require a durable PostgreSQL `DATABASE_URL`, e.g. `postgresql+psycopg://…?sslmode=require`; Vercel or `APP_ENV=production` refuses SQLite. The production requirements include SQLAlchemy and psycopg. Vercel's backend configuration includes operational modules; use the backend directory as its project root, with a managed PostgreSQL connection and pooling appropriate to the host. Hosted deployment itself is not exercised by local tests.

For a hosted demo, set `LUCY_DEMO_AUTH=true` only behind deployment access protection. This explicitly permits impersonation through `X-Demo-Role` / `X-Demo-Id` headers. Customer/merchant selectors are demo navigation, **not authentication**. Demo identity defaults off on hosted environments; real authenticated principals must replace the dependency before a public transactional deployment. Configure `LUCY_CORS_ORIGINS` for the actual frontend origin. Reset remains disabled even if requested through environment variables.

Phase 0 serializes operational database requests (`BEGIN IMMEDIATE` locally, transaction-scoped PostgreSQL advisory lock across instances). This deliberately favors correctness and repeatability at demo scale. There are no external calls while locks are held. Reservations expire lazily on inventory/reservation reads and reservation-dependent actions; no worker is required.

To run the same suite against a disposable PostgreSQL database:

```sh
LUCY_TEST_DATABASE_URL='postgresql+psycopg://USER@localhost:5432/lucy_test' npm run test:backend
```

That database must be dedicated to tests: each test resets its operational fixtures. Historical rebuild scripts are guarded and excluded from normal operation; never point them at the operational store. The checked-in multi-megabyte snapshot was not regenerated in Phase 0.

## Current limits

All payment sessions use `DEMO_SIMULATED`; no funds, credit, refund or dispute processing occurs. Synthetic VPAs are preview-only. The demo allowance is an illustrative opening ₹7,500 minus confirmed simulated payments, not stored money. Demo points start from historical points and add one point per whole ₹10 simulated payment, minus durable redemptions. Historical ML results are not recomputed when a simulated payment is confirmed.

Movie Night offers are deterministic merchant-consented fixtures for customers 6 and 7, with fixed quote expiry at the end of 2027. Rental inventory reserves the single fixture asset conservatively; date-specific calendars, returns, deposits and live merchant onboarding are later work. No specialist is advertised as a working autonomous agent.

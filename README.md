# Paytm Grow

Hackathon prototype foundation for a merchant-growth layer built on Paytm-style payment infrastructure. The product name is **Paytm Grow**.

## Stack

- Frontend: Vite + React + TypeScript + Tailwind
- Backend: FastAPI + precomputed JSON snapshot
- Storage: in-memory working copy of `backend/data/precomputed.json`
- Services: none; the production server only serves checked-in data

## Setup
```bash
npm install
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
python backend/precompute.py
```

Python 3.11-3.13 works well. If your default `python3` is 3.14, use Python 3.13 for the virtualenv because current Pydantic wheels may not be ready for 3.14.

Fresh clone to running demo is under 5 minutes on a normal laptop. ML dependencies are needed only for the local `precompute.py` script; the deployed API uses the small production requirements file.

## Run

Terminal 1:

```bash
npm run backend
```

Alternative manual commands:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

From inside `backend/`, either `uvicorn app:app --reload` or `uvicorn app.main:app --reload` now works.

Terminal 2:

```bash
npm run dev
```

Open `http://127.0.0.1:5173`.

Everything runs locally/offline after dependencies are installed. Set `VITE_API_BASE_URL` to the backend URL in the frontend Vercel project; it defaults to `/api` for local Vite proxy use. Serverless writes are in-memory and ephemeral: a fresh instance may not retain a payment or redemption from an earlier instance. Vercel normally keeps a warm instance for back-to-back demo requests.

## Routes

Hash routing, no router dependency and no auth:

- `#/` — the marketing landing page (top nav, hero, feature grid, stats strip, footer). Default route.
- `#/app` — the demo app shell, opened by the landing page's **Launch Demo** button. Always opens in Customer view; the top-bar toggle switches to Merchant view, and the top-bar wordmark returns to the landing page.

## Modules

| Module | What it does |
| --- | --- |
| Loyalty Points | BG/NBD `P(alive)`, Gamma-Gamma CLV, visit-count loyalty tier, postpaid eligibility |
| Merchant Pulse | Holt-Winters 30-day forecast with confidence band, busiest hours, anomaly text, cashflow note |
| Market Match | SVD peer-similarity price benchmarking, shown alongside an illustrative demo comparison set |
| Rewards Boost | Thompson Sampling point multipliers over seeded synthetic redemption history |
| Loan Readiness Coach | Random Forest readiness tier with SHAP-derived coaching factors |
| Soundbox Copilot | Voice/typed answers that only rephrase already-computed numbers |

## Reset Demo Data

```bash
npm run reset
```

The precompute reset is deterministic. It recreates the same **24 merchants across 6 categories** (4 per category), 400 customers, six months of transaction history, SKU/service prices, line items, seasonality, festival spikes, churn labels, and the seeded illustrative demo-platform prices every time. Production reset restores the checked-in JSON snapshot in memory.

| Category | Example merchant | Catalogue |
| --- | --- | --- |
| Kirana | Sharma Kirana Store | milk, salt, atta, maggi, oil, soap, tea |
| Chemist | Sai Ram Medicals | paracetamol strip, band-aid box, hand sanitizer 100ml, thermometer, multivitamin strip, ORS sachet |
| Salon | Style Street Salon | haircut, shave, head massage, basic facial (services: price only, no unit) |
| Distributor | Charminar FMCG Supply | bulk cooking oil 15L, rice 25kg, wheat flour 25kg, sugar 25kg |
| Sports Shop | Deccan Sports Corner | cricket bat, badminton racket, football, yoga mat, gym gloves |
| Clothing Shop | Nizam Fashion House | cotton t-shirt, jeans, kurta, formal shirt, saree |

The merchant selector in both Customer and Merchant view groups shops by category, so switching merchants shows Market Match adapting to a completely different catalogue. The relationship engine is category-agnostic: transaction history and Loyalty Points behave identically for a salon and a kirana.

After seeding, the script logs:

- total transactions
- transaction date range
- weekend vs weekday volume ratio
- churn count
- merchants per category
- seeded illustrative demo-platform price rows
- sample UPI deep links, with VPA format validation

## Market Match honesty

The focused comparison view ranks five sources per item:

- **Your shop** and **Paytm Grow Network Avg** are genuinely computed. The network average is the mean price across behaviourally similar merchants found with `TruncatedSVD` embeddings and cosine similarity over our own transaction data, and it is tagged `Computed` in the UI.
- **ZipKart, SpeedBasket, CityMart Express, QuickHive** are fictional demo platforms invented for this prototype. Their prices are seeded offsets around each item's category-norm price. A permanent caption under the list says exactly this, and the pricing recommendation ignores them entirely — it reads only the real network benchmark.

## Paytm technology

The Pay flow generates real UPI deep-link intents (`paytmmp://pay?...` plus the universal `upi://pay?...` fallback) in the standard NPCI URI format, and the transaction API mirrors Paytm's public Payment Links / Order API field naming. See [PAYTM_TECH.md](PAYTM_TECH.md).

## API

- `GET /customers`
- `GET /merchants`
- `GET /stats`
- `GET /customers/{id}`
- `GET /merchants/{id}`
- `GET /merchants/{id}/transactions`
- `GET /merchants/{id}/upi-intent?amount=&note=`
- `GET /customers/{id}/transactions`
- `POST /payments`
- `POST /recompute`
- `GET /relationship/{customer_id}/{merchant_id}`
- `GET /merchant/{id}/pulse`
- `GET /merchant/{id}/pricing`
- `POST /merchant/{id}/pricing/actions`
- `POST /reset-demo`
- `GET /rewards/{customer_id}/multiplier`
- `GET /merchant/{id}/rewards`
- `GET /merchant/{id}/loan-readiness`

## Precomputed Production Data

`backend/precompute.py` recreates the seeded dataset and computes the ML cache locally. It writes the complete checked-in snapshot to `backend/data/precomputed.json`. The deployed FastAPI app loads that JSON once at cold start and does not import any ML or database library. The snapshot includes:

- Loyalty Points: BG/NBD `P(alive)`, Gamma-Gamma CLV, visit-count loyalty tier, postpaid eligibility.
- Merchant Pulse: Holt-Winters weekly-seasonal 30-day forecast, confidence band, busiest hours, churn alerts, anomaly text, and cashflow note.
- Market Match: behavior-based merchant peer embeddings with `TruncatedSVD`, same-category cosine neighbors, SKU benchmarks, and deterministic recommendations.
- Rewards Boost: pure NumPy Thompson Sampling over point multipliers with seeded synthetic redemption observations by loyalty tier.
- Loan Readiness: `RandomForestClassifier` over synthetic merchant features with synthetic demo labels, plus SHAP-derived coaching factors. The demo label cut-points and the count/revenue coaching targets are percentiles of the network's own score distribution, so all three tiers stay populated whatever the merchant mix is.

Use `python backend/precompute.py` locally after changing seed logic, then commit the regenerated JSON.

The visible reset button in the app top bar calls `POST /reset-demo`, which restores the immutable in-memory snapshot instantly. `POST /recompute` reports the snapshot metadata and never runs ML in production.

## Vercel Backend

Deploy the `backend/` directory as its own Vercel project, with the project root set to `backend`. Vercel's Python runtime detects `api/index.py` and its top-level FastAPI `app`; `backend/vercel.json` rewrites all paths to that function. Deploy the backend first, verify `GET /health`, then set `VITE_API_BASE_URL` in the separate frontend Vercel project to the backend's deployment URL and redeploy the frontend. The CORS policy allows localhost and Vercel deployment domains.

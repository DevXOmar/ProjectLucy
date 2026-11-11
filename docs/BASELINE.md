# Phase 0 audit evidence

Original commit inspected before editing (2026-11-11). No finalized idea documents or AGENTS.md were present in this repository.

- Active `backend/app.py` deep-copied the JSON snapshot to a global mutable `DATA` dictionary. Payments, reward redemptions and pricing actions mutated it without persistence.
- `POST /payments` appended a transaction immediately and returned `TXN_SUCCESS`. No order/session separation, provider verification, approval, idempotency or authorization existed.
- SQLAlchemy models and SQLite seed existed but the active API did not import them; production requirements did not include SQLAlchemy. Vercel excluded those modules.
- Frontend `AmountEntry` assumed success, had no error path and exposed synthetic VPAs through executable payment links. Wallet was `max(120, 7500 - recentSpend)`.
- Customer/merchant controls were client-only demo selectors. App.tsx contained 1,333 lines.
- Docs mixed snapshot-server behavior with older SQLite/ML startup behavior and overstated live-payment readiness. Legacy branding remained throughout.
- Only one Playwright UI test existed; no backend transaction/workflow coverage.

Baseline commands: `npm ci` passed (184 packages); `npm run build` passed with a pre-existing large-chunk warning. `npm run qa` failed before navigation: Chromium MachPort bootstrap permission denied in sandbox. First `npm run backend` failed because the environment lacked uvicorn; dependency installation then succeeded with network escalation. There were no original backend tests.

Snapshot SHA256 before changes: `489ca5cb47578da74268fe8a0d13b00564fac88dcad2c4f498b0c7ea6fb1d650`. Snapshot regeneration is excluded from Phase 0.

After dependencies were installed, the original API started successfully (`/health` 200); an isolated TestClient payment returned `TXN_SUCCESS` immediately. The original Playwright suite passed outside the sandbox (1 test, 56.5s, no console errors). Screenshots were captured under `/tmp/pg-shots` for visual comparison.

## Repair verification

Final Phase 0 checks on 2026-11-11:

- `npm run build`: passed; existing Vite large-bundle warning remains.
- `npm run test:backend`: 32 passed on isolated SQLite; the same 32 passed with `LUCY_TEST_DATABASE_URL` pointed at a temporary PostgreSQL 14 instance. Only an upstream Starlette/AnyIO deprecation warning was emitted.
- `npm run qa`: four existing/expanded desktop/mobile scenarios passed. `npm run qa -- --grep 'records a Lucy mission'`: two additional desktop/mobile mission-entry scenarios passed. Browser execution required escaping the host sandbox; the deliberate HTTP 503 error-recovery probe was the only expected console resource error.
- Actual workflow: three approved/reserved orders totaling ₹2,200, three pending sessions, explicit simulated confirmations, merchant fulfillment, product/budget verification, persisted task evidence and completed mission. Inventory contention, multi-line rollback, TTL/cancellation release, duplicate event rejection, idempotent replay, scope errors, reset and fresh-interpreter persistence were checked on both databases.
- `npm run reset`: passed against the running local API; operational fixtures returned to their initial state.
- `git diff --check` and Python compile check passed. Snapshot SHA256 remains identical to baseline. No ML snapshot rebuild, commit, push or hosted deployment was performed.

Visual screenshots for the preserved customer/merchant modules, pending/confirmed payments and mission entry are under `/tmp/lucy-shots/{desktop,mobile}` on the development machine. Hosted deployment, public authentication, real merchant/provider integration and autonomous planning remain outside this verification.

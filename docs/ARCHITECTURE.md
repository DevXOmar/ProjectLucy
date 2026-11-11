# Lucy foundation, version 1

Lucy is the customer-facing crew lead. CrewOS is the shared mission, policy, tool and evidence layer. Specialists express commerce capabilities; they do not run independent LLM services in Phase 0. Adaptive Commerce Orchestration will choose valid combinations of buying, group purchasing, surplus and rentals, while keeping order/payment/support state continuous.

The preserved application provides historical merchant analytics and demo navigation. The new foundation provides executable SQL-backed commerce tools and structured goal intake. No natural-language planner, LLM delegation or autonomous specialist execution is claimed.

## Domain and API boundary

`contracts.py` defines Pydantic input/output contracts; `/docs` exposes OpenAPI and `/tools` exposes tool input schemas. HTTP handlers in `commerce.py` and future orchestrators call the same validated functions in `services.py`.

| Records | Purpose |
|---|---|
| Mission, MissionTask | Requester, goal, requirements, budget, UTC deadline, backend-assigned authorization scope, explicit status, specialist assignment, dependencies, evidence references |
| MerchantOffer, Inventory | Merchant consent, product/asset ID, integer paise, quote expiry, eligibility/quantity/rental terms, available stock |
| Reservation | Order/customer/offer reference, held quantity, TTL, ACTIVE/EXPIRED/RELEASED/CONSUMED |
| Order, OrderItem | Customer, merchant, mission reference, immutable quoted lines/totals and separate fulfillment state |
| Approval | Exact order amount, customer decision and timestamp before commercial commitment |
| PaymentSession, PaymentEvent | Amount, currency, order association, mode, separately tracked refund/dispute fields, durable transition provenance |
| AuditEvent | Outcome Ledger: actor, specialist, mission, action, timestamp, validated inputs, resulting records/output, approval and verification state |
| Idempotency, DemoRedemption, SchemaVersion | Retry result fingerprint, durable demo reward mutation, deterministic schema initialization |

Existing customer/merchant models hold fixture identity references. Existing float-based historical transaction/pricing models remain for optional legacy ML generation; mutable commerce money never uses them. The JSON snapshot is read-only reference data and retains all original historical data.

Local SQLite uses WAL and explicit `BEGIN IMMEDIATE`; PostgreSQL uses transaction-scoped advisory serialization across instances. Conditional inventory decrement prevents stock falling below zero. Multi-line reservation failure rolls back the entire action. Expired holds are released lazily when inventory/reservations are inspected or required for an action. Orders need renewed valid reservations before commitment/payment confirmation.

## Policy and lifecycle

Demo principals are explicit `X-Demo-Role` / `X-Demo-Id` headers, enabled locally and disabled by default when hosted. This is controlled demo impersonation, not production authentication. Customer actions are scoped to the requester; merchant actions to the owning merchant. The backend enforces customer offer eligibility, merchant consent, quote/rental/surplus terms, quantity thresholds, exact order/payment references, mission spending limits and explicit customer approval. Future authenticated principals must replace `policy.identity` without bypassing these service checks.

Order lifecycle: DRAFT → AWAITING_APPROVAL → CONFIRMED → FULFILLMENT_PENDING → FULFILLED. Draft, approval-pending and unpaid confirmed orders can be cancelled; payment failure/cancellation is an explicit failure/cancellation path. A paid order needs future refund handling rather than silent cancellation.

Payment lifecycle: CREATED → INITIATED → PENDING → CONFIRMED / FAILED / CANCELLED. The installed adapter always uses DEMO_SIMULATED, never external verification. Session creation records pending state; confirmation is a separate customer-controlled simulation action. Terminal sessions cannot be reconfirmed. Unique event IDs and actor-scoped idempotency protect retries. Refund/dispute states are separate and currently NONE.

Mission transitions are centralized in `services.MISSION_TRANSITIONS`: CREATED, PLANNING, AWAITING_APPROVAL, EXECUTING, REPLANNING, VERIFYING, COMPLETED, BLOCKED, FAILED and CANCELLED. Terminal states cannot restart. Completion requires a deterministic outcome check of required product quantities, fulfilled orders, corresponding confirmed simulated payments and total budget. Assigned tasks must also be completed or explicitly cancelled; the outcome tool records verified order/payment evidence on its task. An empty requirement set cannot falsely verify a free-text goal. Confirmation does not claim real settlement or externally verified fulfillment.

## Specialists and tools

`agents.py` registers MissionCart, SwarmBuy, ShelfLife, RentRight, SplitSettle, Rebound AI, GhostPay and DisputePilot with task types and explicit tool permissions. MissionCart, ShelfLife and RentRight are LIMITED because commerce tools exist; the other five are PLANNED. None is WORKING as an autonomous agent.

Tools include search_catalog, check_inventory, get_offer, reserve_inventory, create_order, get_order_status, create_payment_session, get_payment_status, request_approval and verify_outcome. Tool calls require a mission assignment, eligible lifecycle state, permitted implemented specialist capability, complete dependencies and matching mission references. Tools cannot approve customer decisions, simulate payments or fulfill merchant orders. Those remain explicit principal actions.

The Outcome Ledger persists successful actions and resulting references, plus rejected service attempts after their commerce transaction rolls back. Mission events use stable timestamp/UUID ordering and cursor polling; clients can resume without losing ties. UI commerce activity polls independently every four seconds. No SSE dependency or orchestration framework is needed yet.

## Next implementation slice

Attach one Crew Lead planner and MissionCart executor to the existing tool contracts. Turn the Movie Night goal into validated product requirements; compare the four fixtures; create the three orders totaling ₹2,200 and reserve stock; pause for real customer approval, then resume payment-session creation. On expiry/stock failure, transition to REPLANNING and reuse the same validated services. A human controls demo payment outcomes and merchants record fulfillment; the deterministic verifier decides completion. Use `/tasks/{id}/transition` to persist progress and evidence; completed dependencies require scoped fulfilled-order or confirmed-payment references. Add planner restart tests before expanding to another specialist.

LangGraph can use mission/task IDs as durable graph state and call these functions or the authenticated tool API. It must never write tables directly, grant itself authorization, invent catalog facts or treat an LLM assertion as outcome evidence. Public auth, live merchant onboarding and a verified provider adapter are separate later milestones.

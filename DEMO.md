# Project Lucy demo

Start the API and Vite as described in README. Use default local configuration. All merchant/customer identities, inventory, historical transactions and payment outcomes are synthetic.

1. Open the landing page. The navy/cyan composition, six existing merchant modules and historical stats are preserved. Launch Demo opens customer 6.
2. Customer home shows **Demo allowance**, its SQL-derived source, demo rewards, existing loyalty insight and transaction history. Identity and merchant selectors are demo navigation.
3. **Ask Lucy** records the Movie Night goal, ₹2,500 budget and product requirements as a `CREATED` mission. It does not automatically plan or execute. The API supports explicit state transitions and task assignments for the next orchestration slice.
4. Open **Pay**, choose Deccan Sports Corner, enter ₹450 and expand **View UPI payment link**. It is a non-clickable syntax preview for a synthetic recipient. No app handoff is available.
5. Choose **Create demo payment**. The session is `PENDING`; transaction history, demo allowance and points have not changed. Return home and select it under Lucy commerce activity to resume after navigation or page reload.
6. Choose **Simulate confirmation**. It becomes `CONFIRMED` with `DEMO_SIMULATED`, external verification false and an explicit no-real-settlement label. History gains one simulated transaction; allowance decreases ₹450 and points increase 45. Failure/cancel simulation is also available while pending. Retries with the same key replay the original result; another confirmation is rejected.
7. Switch to **Merchant view**, select Deccan Sports Corner. Lucy commerce activity independently reads the payment. Existing pulse, insights, pricing, rewards, category switching, loan coaching and Soundbox lookup remain available. They use preserved historical ML data.
8. Reset through the header/Profile or `npm run reset`. Operational missions, orders, payments, reservations, redemptions and audit events are cleared; inventory and demo allowance return to fixture values. Historical analytics and all 24 merchants remain unchanged. This action is developer-only and disabled when hosted.

## Order workflow and Movie Night

`npm run test:backend` executes the complete workflow through actual API and database changes. `npm run qa` additionally creates an approved rental order through the API and verifies the resulting order/payment states in both customer and merchant screens on desktop and mobile.

Movie Night fixture prices: projector rental ₹900 at merchant 17, ten sealed eligible surplus snack boxes at ₹70 each from merchant 1, and ten drinks at ₹60 each from merchant 2. Total **₹2,200**. A projector purchase alternative costs ₹18,000 and exceeds the mission budget. Each merchant requires a separate order/payment session.

The API sequence, using `X-Demo-Role: customer`, `X-Demo-Id: 6` and a fresh `Idempotency-Key` for each logical mutation:

1. `POST /missions` with goal, budget_paise=250000 and product requirements.
2. `POST /missions/{id}/transition` to PLANNING; assign MissionCart procurement through `/tasks`; transition to EXECUTING.
3. Read `/offers` and `/offers/{id}`. `POST /orders` with merchant_id, mission_id and offer/quantity lines creates DRAFT. Retry the same key to retrieve the same order.
4. `POST /reservations` with order_id atomically holds inventory for up to 15 minutes. Insufficient stock rejects the entire operation.
5. `POST /approvals` requests approval. `POST /approvals/{id}/decision` with approve=true records the customer's decision. `POST /orders/{id}/confirm` commits only with that approval and live reservation.
6. `POST /payments` with order_id, matching merchant_id and amount_paise creates PENDING. `POST /payments/{id}/simulate` with status=CONFIRMED and unique event_key records the explicit simulated outcome. The order becomes FULFILLMENT_PENDING.
7. With the corresponding merchant identity, `POST /orders/{id}/fulfill` records demo fulfillment. Repeat for the three merchants.
8. Transition the mission to VERIFYING. Invoke `/tools/verify_outcome` with mission_id, specialist_id=missioncart and inputs={}. It checks product quantities, fulfillment, matching confirmed demo payments and budget. Only then can the mission transition to COMPLETED.

Read `/orders/{id}`, `/payments/{id}`, `/payments/{id}/events` and `/missions/{id}/events` independently. Event polling accepts `after=<last event UUID>` and returns `next_cursor`; no fabricated AI logs are shown. Fulfillment is a merchant-recorded demo action, not externally verified delivery.

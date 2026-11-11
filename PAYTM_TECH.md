# Paytm Technology in Paytm Grow

Source of truth for the question "did you actually use Paytm technology?" — written to be pasted into a submission form as-is.

## Summary

We generate real UPI deep-link payment intents (`paytmmp://pay?...`) following the standard NPCI UPI URI scheme that the Paytm app itself resolves, so our payment flow produces a genuinely valid Paytm-compatible payment link for every transaction. Our backend's transaction schema is modeled on Paytm's public Payment Links API field structure so a live merchant integration is a credentials swap, not a rewrite. We did not have sandbox merchant credentials in the hackathon timeframe, so the in-app payment simulation (not the UPI link generation, which is real) drives the live demo for reliability.

## What is actually built

**1. Real UPI deep-link intents, per transaction.**
Every merchant in our dataset has a UPI virtual payment address (VPA) in the standard NPCI `identifier@psp` handle format, for example `sharmakirana@paytm`. When a payment is confirmed we construct two real deep links from that VPA:

```
paytmmp://pay?pa=sharmakirana@paytm&pn=Sharma%20Kirana%20Store&am=120.00&cu=INR&tn=Paytm%20Grow%20payment%20to%20Sharma%20Kirana%20Store&tr=PG-1-000123
upi://pay?pa=sharmakirana@paytm&pn=Sharma%20Kirana%20Store&am=120.00&cu=INR&tn=Paytm%20Grow%20payment%20to%20Sharma%20Kirana%20Store&tr=PG-1-000123
```

`paytmmp://` is the Paytm app's own registered URI scheme; `upi://` is the universal NPCI-defined scheme that any UPI app on the device resolves, Paytm included. The parameters are the standard NPCI ones: `pa` payee address, `pn` payee name, `am` amount, `cu` currency, `tn` transaction note, `tr` transaction reference (we pass our own `orderId` through it, which is what a live merchant reconciles against).

The links are generated in both the backend (`backend/upi.py`, used by the payment API) and the frontend (`src/lib/upi.ts`, used for the pre-payment preview), with identical percent-encoding so the previewed string is the string the backend records.

**2. A real handoff attempt, not a mock.**
The Pay screen has a secondary "Pay with Paytm" button that assigns the generated URI to `window.location.href` — exactly how a web page invokes an installed UPI app. On a phone with Paytm installed this genuinely hands off to the real Paytm app. On a demo laptop no application is registered for the scheme, so it simply does not resolve; that is expected and does not affect the demo. A collapsible "View UPI payment link" shows the full generated URL string so the link can be inspected as a correctly-formed intent rather than taken on trust.

**3. Transaction schema modeled on Paytm's public API field structure.**
`POST /payments` accepts and returns Paytm-style field names so a live integration is a transport-and-credentials change rather than a schema migration:

- Request: `merchantId`, `customerId`, `txnAmount: { value, currency }`, `paymentMode`, `txnNote`
- Response: `orderId`, `txnId`, `txnAmount: { value, currency }`, `txnDate`, `txnStatus` (`TXN_SUCCESS`), `respCode`, `respMsg`, `paymentMode`, `payerVpa`, `payeeVpa`, `payeeName`, `txnNote`, `paytmIntent`, `upiIntent`

This is documented in the code as a deliberate choice (see the docstring on `create_payment` in `backend/app.py` and the comment on `createPayment` in `src/lib/api.ts`). `GET /merchants/{id}/upi-intent` exposes the same link construction for inspection and logging.

## What we are explicit about not having

- **No sandbox merchant credentials.** We could not obtain Paytm merchant sandbox credentials within the hackathon timeframe, so no payment is initiated, authorised, or settled through Paytm. Nothing in the demo claims otherwise.
- **The in-browser payment is simulated.** It writes a real row to our local SQLite database and triggers a real ML recompute, but it is not a live Paytm transaction. We kept it as the primary demo path for on-stage reliability. The UPI link generation sitting alongside it is real.
- **No Paytm branding, trademarks, or scraped content.** The landing page and UI take visual cues (navy/cyan palette, structure) but all copy is our own.
- **The comparison platforms in Market Match are fictional.** ZipKart, SpeedBasket, CityMart Express and QuickHive are invented demo brands with seeded prices, disclosed in a permanent visible caption in the app. The only real number in that comparison is the Paytm Grow Network Avg, computed from our own merchant data via peer similarity.

## Verified

- Every merchant VPA passes the NPCI handle format check (`backend/upi.py::is_valid_vpa`); `python backend/seed.py` prints sample links and reports any failures.
- Amounts are always emitted with two decimals, spaces are percent-encoded as `%20`, and `@` is left raw in `pa` as real merchant links do.

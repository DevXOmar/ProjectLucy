# Paytm Grow Demo Script

## 3-Minute Walkthrough

1. Open `http://127.0.0.1:5173`. Start on the **landing page**: top nav, hero with the animated gradient wash and floating module icons, the six-module feature grid, the stats strip pulled live from `GET /stats`, and the footer. Tap **Launch Demo** — no login, no form.
2. Land in Customer view on Home. Show the Paytm-style top bar, navy wallet card, quick actions, Paytm Grow Insight banner, and real SQLite transaction list. Note the two grouped selectors: demo customer, and the store they're shopping at (grouped by category).
3. Tap UPI or Scan & Pay. Nearby merchants lists one shop per category with a colour-coded category chip. Select Sharma Kirana Store, enter ₹120.
4. Before paying, expand **Pay with Paytm → View UPI payment link**. Show the real `paytmmp://pay?...` and `upi://pay?...` intents built from that merchant's VPA. On a phone this opens the Paytm app; on the laptop it will not resolve, which is why the simulated payment below is the demo path.
5. Tap Pay. Payment writes a real SQLite transaction, recomputes ML, and lands on Payment Success — with the backend's `orderId`, `txnStatus`, `payerVpa`/`payeeVpa`, and the UPI link generated for that order.
6. Return Home. The QR payment now appears in Recent Activity and the customer insight refreshes without restarting the server.
7. Tap Rewards. Show Rewards Boost: Thompson Sampling selected multiplier, points earned on last purchase, wallet redemption offers. Redeem one offer and show the point balance decrement.
8. Tap Profile. Show avatar, phone, home store, loyalty-by-merchant list, and Reset Demo Data.
9. Switch to Merchant view. The dashboard surfaces all AI modules as tappable cards: Merchant Pulse, Loyalty call-list, Market Match, Rewards Boost, Loan Coach, and Soundbox Copilot.
10. Tap Merchant Pulse. Read the Holt-Winters briefing with forecast sparkline, busiest hours, anomaly/same-weekday drop, cashflow note, and churn-risk call list.
11. Tap Pricing for **Market Match**. Pick one item to open the focused comparison: your shop, the `Computed` Paytm Grow Network Avg, and the four illustrative demo platforms, sorted cheapest first with a Best price badge. Read the permanent caption — it is plainly visible, not behind a tooltip. Point out that the recommendation card underneath cites only your price against the network average. Tap Accept action once.
12. **Switch category.** Use the grouped merchant dropdown to pick a Sports Shop (e.g. Deccan Sports Corner). Market Match instantly shows cricket bat / badminton racket / football instead of milk and atta, and Merchant Pulse and Loan Readiness re-render for that merchant. Repeat with a Salon to show services priced without units.
13. Tap Rewards and Loan. Show merchant rewards economics and SHAP-derived loan coaching.
14. Tap the floating Soundbox mic in Merchant view. Try: "business update", "who should I call", "am I priced right on milk" (or "cricket bat" on a Sports Shop), and "loan readiness". Typed fallback opens immediately when voice is unavailable.
15. Tap Reset Demo Data. Explain that it reseeds deterministic SQLite across all six categories, removes demo payments/redemptions, and recomputes the ML cache for the next judge.

## What Is Fully Real ML

- BG/NBD P(alive) and Gamma-Gamma CLV from `lifetimes`.
- Holt-Winters weekly-seasonal revenue forecast from `statsmodels`.
- Residual and same-weekday anomaly detection from transaction history.
- Merchant peer embeddings from `TruncatedSVD` and cosine similarity — this is what the Paytm Grow Network Avg row is computed from.
- Thompson Sampling offer selection in NumPy using seeded synthetic redemption observations.
- Random Forest loan-readiness classifier and SHAP explanations.
- Payment writes, reward redemptions, reset, and pricing action logging are real local backend mutations.
- UPI deep-link generation: real NPCI-format `upi://pay` and `paytmmp://pay` intents, built from each merchant's VPA. See PAYTM_TECH.md.

## What Is Polished Mockup

- QR scanning camera integration is mocked; selecting a nearby merchant and posting the payment are real local flows.
- The in-browser payment is simulated. The UPI link generation around it is real; we had no sandbox merchant credentials, so nothing settles.
- ZipKart, SpeedBasket, CityMart Express and QuickHive are fictional demo platforms with seeded prices — illustrative comparison rows only, never used in any recommendation. The app says so on the screen.
- Pricing accept action logs to backend console only.
- Loan labels are synthetic demo labels generated from documented rules; the tier cut-points are percentiles of the network's own readiness score.
- Merchant retained revenue and rewards cost are simplified estimates.

## Roadmap

- Swap the simulated payment for a live Paytm merchant integration; the transaction schema already mirrors Paytm's public Payment Links / Order API field names.
- Replace synthetic labels and redemption observations with Paytm production outcomes.
- Persist accepted pricing/reward actions and measure uplift.
- Add real lending policy constraints and underwriting review.
- Upgrade Soundbox Copilot phrasing with a local LLM only when an offline Ollama server is available.

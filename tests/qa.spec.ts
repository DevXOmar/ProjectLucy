import { test, expect } from "@playwright/test";

/**
 * Part F QA pass: landing -> Launch Demo -> both views, across two merchant
 * categories, checking for leftover old product names on every screen visited.
 */

const OLD_NAMES = /paytm grow|paytmgrow|apna dukaan|apna|dukaan|rishta|bhaav|vyapar/i;
const BASE = "http://127.0.0.1:5173";
let SHOTS = "/tmp/lucy-shots";

test.beforeEach(async ({ request }, info) => {
  SHOTS = `/tmp/lucy-shots/${info.project.name}`;
  const reset = await request.post("/api/reset-demo", { headers: { "X-Reset-Token": "local-reset" } });
  expect(reset.ok()).toBeTruthy();
});

/** Bottom-nav tab by label (avoids matching same-named dashboard cards). */
function navTab(page: any, label: string) {
  return page.locator("nav button").filter({ hasText: new RegExp(`^${label}$`) });
}

async function assertNoOldNames(page: any, label: string) {
  const text = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  const match = text.match(OLD_NAMES);
  if (match) throw new Error(`Old product name "${match[0]}" still visible on: ${label}`);
}

test("landing page, rename sweep, category switch, market match, upi link", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (error) => errors.push(String(error)));

  // --- Landing page ---
  await page.goto(BASE, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 1 })).toContainText("relationship");
  await expect(page.getByText("Six modules, one merchant dashboard")).toBeVisible();
  for (const module of ["Loyalty Points", "Market Match", "Merchant Pulse", "Rewards Boost", "Loan Readiness Coach"]) {
    await expect(page.getByRole("heading", { name: module, exact: true })).toBeVisible();
  }
  await expect(page.getByText("Built for the Paytm Build for India AI Hackathon.")).toBeVisible();
  // Stats strip should show the real seeded numbers, not the fallback only.
  await expect(page.getByText("Demo merchants")).toBeVisible();
  const statsText = await page.locator("section").filter({ hasText: "Demo merchants" }).first().innerText();
  console.log("STATS STRIP:", statsText.replace(/\n/g, " | "));
  await assertNoOldNames(page, "landing page");
  await page.screenshot({ path: `${SHOTS}/01-landing-hero.png` });
  await page.evaluate(() => window.scrollTo(0, 900));
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${SHOTS}/02-landing-features.png` });

  // --- Launch Demo -> customer view ---
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByRole("button", { name: "Launch Demo" }).last().click();
  await page.waitForTimeout(1200);
  await expect(page.getByText("Your Project Lucy Insight")).toBeVisible();
  await expect(page.getByText("Store you're shopping at")).toBeVisible();
  await assertNoOldNames(page, "customer home");
  await page.screenshot({ path: `${SHOTS}/03-customer-home.png`, fullPage: true });

  // --- Pay flow with UPI intent ---
  await navTab(page, "Pay").click();
  await page.waitForTimeout(600);
  await assertNoOldNames(page, "scan qr");
  await page.screenshot({ path: `${SHOTS}/04-scan.png`, fullPage: true });
  await page.locator("button").filter({ hasText: "Deccan Sports Corner" }).first().click();
  await page.waitForTimeout(500);
  for (const key of ["4", "5", "0"]) await page.getByRole("button", { name: key, exact: true }).click();
  await expect(page.getByRole("heading", { name: "UPI intent preview" })).toBeVisible();
  await page.getByRole("button", { name: "View UPI payment link" }).click();
  await page.waitForTimeout(500);
  const paytmLink = await page.locator("p.font-mono").first().innerText();
  const upiLink = await page.locator("p.font-mono").nth(1).innerText();
  console.log("PAYTM INTENT:", paytmLink);
  console.log("UPI INTENT:", upiLink);
  expect(paytmLink).toMatch(/^paytmmp:\/\/pay\?pa=[^&]+@paytm&pn=[^&]+&am=450\.00&cu=INR&tn=/);
  expect(upiLink).toMatch(/^upi:\/\/pay\?pa=[^&]+@paytm&pn=[^&]+&am=450\.00&cu=INR&tn=/);
  await assertNoOldNames(page, "amount entry + upi panel");
  await page.screenshot({ path: `${SHOTS}/05-amount-upi.png`, fullPage: true });

  // First attempt errors visibly; retry creates a pending session without a transaction.
  await page.route("**/api/payments", route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { message: "Temporary demo failure" } }) }));
  await page.getByRole("button", { name: /^Create demo payment/ }).click();
  await expect(page.getByRole("alert")).toContainText("Temporary demo failure");
  await page.unroute("**/api/payments");
  await page.getByRole("button", { name: /^Create demo payment/ }).click();
  await expect(page.getByRole("heading", { name: "Payment pending" })).toBeVisible();
  await expect(page.getByText("PENDING", { exact: true })).toBeVisible();
  await expect(page.locator('a[href^="upi:"], a[href^="paytmmp:"]')).toHaveCount(0);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS}/06-pending.png`, fullPage: true });
  await page.getByRole("button", { name: "Simulate confirmation", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Demo payment confirmed" })).toBeVisible();
  await expect(page.getByText("CONFIRMED", { exact: true })).toBeVisible();
  await expect(page.getByText(/No real Paytm settlement/)).toBeVisible();
  await assertNoOldNames(page, "demo payment confirmed");
  await page.screenshot({ path: `${SHOTS}/06-confirmed.png`, fullPage: true });

  // --- Customer rewards + profile ---
  await navTab(page, "Rewards").click();
  await page.waitForTimeout(900);
  await assertNoOldNames(page, "customer rewards");
  await page.screenshot({ path: `${SHOTS}/07-rewards.png`, fullPage: true });
  await navTab(page, "Profile").click();
  await page.waitForTimeout(900);
  await assertNoOldNames(page, "customer profile");

  // --- Merchant view, Kirana ---
  await page.getByRole("button", { name: "Merchant view" }).click();
  await page.waitForTimeout(1500);
  await expect(page.getByText("Merchant Pulse briefing")).toBeVisible();
  await expect(page.getByText("Loyalty call-list")).toBeVisible();
  await assertNoOldNames(page, "merchant home (kirana)");
  await page.screenshot({ path: `${SHOTS}/08-merchant-home-kirana.png`, fullPage: true });

  const merchantSelect = page.locator("select").first();
  console.log("MERCHANT DROPDOWN GROUPS:", await page.locator("optgroup").evaluateAll((nodes) => nodes.map((n) => n.getAttribute("label"))));

  // Market Match for Kirana
  await navTab(page, "Pricing").click();
  await page.waitForTimeout(1600);
  await expect(page.getByRole("heading", { name: "Market Match" })).toBeVisible();
  const kiranaSkus = await page.locator("div.no-scrollbar button").allInnerTexts();
  console.log("KIRANA SKUS:", kiranaSkus.join(" / "));
  await page.locator("div.no-scrollbar button").nth(1).click();
  await page.waitForTimeout(1600);
  for (const platform of ["ZipKart", "SpeedBasket", "CityMart Express", "QuickHive", "Project Lucy Network Avg"]) {
    await expect(page.getByText(platform, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText("Best price")).toBeVisible();
  const caption = page.getByText(/are illustrative demo platforms for this prototype/);
  await expect(caption).toBeVisible();
  console.log("DISCLOSURE VISIBLE:", (await caption.innerText()).replace(/\s+/g, " "));
  await assertNoOldNames(page, "market match focused (kirana)");
  await page.screenshot({ path: `${SHOTS}/09-market-match-kirana.png`, fullPage: true });

  // --- Switch category to Sports Shop ---
  await navTab(page, "Home").click();
  await page.waitForTimeout(1200);
  await merchantSelect.selectOption({ label: "Deccan Sports Corner · Sports Shop" });
  await page.waitForTimeout(2500);
  await expect(page.getByText("Sports Shop").first()).toBeVisible();
  await assertNoOldNames(page, "merchant home (sports shop)");
  await page.screenshot({ path: `${SHOTS}/10-merchant-home-sports.png`, fullPage: true });

  await navTab(page, "Pricing").click();
  await page.waitForTimeout(1600);
  const sportsSkus = await page.locator("div.no-scrollbar button").allInnerTexts();
  console.log("SPORTS SKUS:", sportsSkus.join(" / "));
  expect(sportsSkus.join(" ")).toContain("Cricket bat");
  await page.locator("div.no-scrollbar button").nth(1).click();
  await page.waitForTimeout(1600);
  await expect(page.getByText(/are illustrative demo platforms/)).toBeVisible();
  await assertNoOldNames(page, "market match focused (sports shop)");
  await page.screenshot({ path: `${SHOTS}/11-market-match-sports.png`, fullPage: true });

  // Insights + loan for sports shop
  await navTab(page, "Insights").click();
  await page.waitForTimeout(2000);
  await expect(page.getByText("Merchant Pulse")).toBeVisible();
  await assertNoOldNames(page, "insights (sports shop)");
  await page.screenshot({ path: `${SHOTS}/12-insights-sports.png`, fullPage: true });
  await navTab(page, "Loan").click();
  await page.waitForTimeout(1800);
  await expect(page.getByText("Loan Readiness")).toBeVisible();
  await assertNoOldNames(page, "loan readiness (sports shop)");
  await page.screenshot({ path: `${SHOTS}/13-loan-sports.png`, fullPage: true });
  await navTab(page, "Rewards").click();
  await page.waitForTimeout(1200);
  await assertNoOldNames(page, "merchant rewards (sports shop)");

  // --- Soundbox copilot intents ---
  await navTab(page, "Home").click();
  await page.waitForTimeout(1200);
  await page.locator("button").filter({ hasText: "Soundbox Copilot" }).first().click();
  await page.waitForTimeout(800);
  const soundboxAsks = ["how am I doing", "who should I call", "am I priced right on cricket bat", "loan readiness", "market match"];
  for (const ask of soundboxAsks) {
    await page.getByPlaceholder("Ask Soundbox").fill(ask);
    await page.locator("div.fixed button").last().click();
    await page.waitForTimeout(700);
    const answer = await page.locator("div.fixed p.text-sm").first().innerText();
    console.log(`SOUNDBOX "${ask}" ->`, answer.replace(/\s+/g, " ").slice(0, 160));
    expect(answer).not.toMatch(OLD_NAMES);
    expect(answer).not.toContain("could not match that yet");
  }
  await assertNoOldNames(page, "soundbox copilot");
  await page.screenshot({ path: `${SHOTS}/14-soundbox.png`, fullPage: true });

  // --- Reset demo data ---
  await page.locator("header button").last().click();
  await page.waitForTimeout(12000);
  await expect(page.getByText("Merchant Pulse briefing")).toBeVisible();
  console.log("DROPDOWN GROUPS AFTER RESET:", await page.locator("optgroup").evaluateAll((nodes) => nodes.map((n) => n.getAttribute("label"))));
  await assertNoOldNames(page, "merchant home after reset");
  await page.screenshot({ path: `${SHOTS}/15-after-reset.png`, fullPage: true });

  // --- Back to landing via wordmark ---
  await page.locator("header button").first().click();
  await page.waitForTimeout(900);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("relationship");

  console.log("CONSOLE ERRORS:", errors.length ? errors.join(" || ") : "none");
  expect(errors.filter((error) => !/favicon|ResizeObserver|503 \(Service Unavailable\)/i.test(error))).toEqual([]);
});

test('durable approved order and payment appear in customer and merchant screens', async ({ page, request }) => {
  const customer = { 'X-Demo-Role': 'customer', 'X-Demo-Id': '6' };
  const merchant = { 'X-Demo-Role': 'merchant', 'X-Demo-Id': '17' };
  const post = async (path: string, data?: unknown, actor = customer, key = crypto.randomUUID()) => {
    const response = await request.post(`/api${path}`, { data, headers: { ...actor, 'Idempotency-Key': key } });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };
  const orderKey = crypto.randomUUID();
  const payload = { merchant_id: 17, items: [{ offer_id: 'projector-rent', quantity: 1 }] };
  const order = await post('/orders', payload, customer, orderKey);
  expect((await post('/orders', payload, customer, orderKey)).id).toBe(order.id);
  await post('/reservations', { order_id: order.id });
  const approval = (await post('/approvals', { order_id: order.id })).approval;
  await post(`/approvals/${approval.id}/decision`, { approve: true });
  await post(`/orders/${order.id}/confirm`);
  const payment = await post('/payments', { merchant_id: 17, order_id: order.id, amount_paise: 90000 });
  expect(payment.status).toBe('PENDING');
  await page.goto('/#/app');
  await expect(page.getByText(new RegExp(`Order ${order.id.slice(0, 8)}.*CONFIRMED`))).toBeVisible();
  await expect(page.getByRole('button', { name: new RegExp(`Payment ${payment.id.slice(0, 8)}.*PENDING`) })).toBeVisible();
  await page.getByRole('button', { name: new RegExp(`Payment ${payment.id.slice(0, 8)}`) }).click();
  await expect(page.getByRole('heading', { name: 'Payment pending' })).toBeVisible();
  await page.getByRole('button', { name: 'Simulate confirmation', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Demo payment confirmed' })).toBeVisible();
  const sessions = await request.get('/api/payments', { headers: customer });
  expect((await sessions.json()).length).toBe(1);
  const duplicate = await request.post(`/api/payments/${payment.id}/simulate`, { headers: { ...customer, 'Idempotency-Key': crypto.randomUUID() }, data: { status: 'CONFIRMED', event_key: crypto.randomUUID() } });
  expect(duplicate.status()).toBe(409);
  await page.getByRole('button', { name: 'Merchant view' }).click();
  await page.locator('select').first().selectOption({ label: 'Deccan Sports Corner · Sports Shop' });
  await expect(page.getByText(new RegExp(`Order ${order.id.slice(0, 8)}.*FULFILLMENT_PENDING`))).toBeVisible();
  await expect(page.getByRole('button', { name: new RegExp(`Payment ${payment.id.slice(0, 8)}.*CONFIRMED`) })).toBeVisible();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SHOTS}/16-durable-merchant-order.png`, fullPage: true });
  await post(`/orders/${order.id}/fulfill`, undefined, merchant);
  await expect(page.getByText(new RegExp(`Order ${order.id.slice(0, 8)}.*FULFILLED`))).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Merchant view' }).click();
  await page.locator('select').first().selectOption({ label: 'Deccan Sports Corner · Sports Shop' });
  await expect(page.getByText(new RegExp(`Order ${order.id.slice(0, 8)}.*FULFILLED`))).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBeFalsy();
});

test('records a Lucy mission without claiming autonomous execution', async ({ page, request }) => {
  await page.goto('/#/app');
  await page.locator('summary').filter({ hasText: 'Ask Lucy' }).click();
  await page.getByRole('button', { name: 'Create Movie Night mission', exact: true }).click();
  await expect(page.getByText(/^Mission .* · CREATED$/)).toBeVisible();
  const response = await request.get('/api/missions', { headers: { 'X-Demo-Role': 'customer', 'X-Demo-Id': '6' } });
  const missions = await response.json();
  expect(missions).toHaveLength(1);
  expect(missions[0].budget_paise).toBe(250000);
  expect(missions[0].status).toBe('CREATED');
  expect(missions[0].requirements.products).toHaveLength(3);
  await expect(page.getByText(/Autonomous planning is the next phase/)).toBeVisible();
  const events = await request.get(`/api/missions/${missions[0].id}/events`, { headers: { 'X-Demo-Role': 'customer', 'X-Demo-Id': '6' } });
  expect((await events.json()).events.map((event: { action: string }) => event.action)).toEqual(['create_mission']);
  await page.screenshot({ path: `${SHOTS}/17-lucy-mission.png`, fullPage: true });
});

export type Role = "customer" | "merchant";

export type Customer = {
  id: number;
  name: string;
  phone: string;
  locality: string;
  vpa: string;
  home_merchant_id: number;
  home_merchant_name: string | null;
  churned: boolean;
};

export type Merchant = {
  id: number;
  name: string;
  category: string;
  locality: string;
  /** Synthetic demo VPA; never an authorized live destination. */
  vpa: string;
  prices: { sku: string; price: number }[];
};

export type DemoStats = {
  merchants: number;
  customers: number;
  categories: number;
  transactions: number;
  category_names: string[];
  history_months: number;
};

export type Transaction = {
  id: number | string;
  provenance?: "DEMO_SIMULATED";
  customer_id: number;
  customer_name: string;
  merchant_id: number;
  merchant_name: string;
  timestamp: string;
  amount: number;
  items: { sku: string; quantity: number; unit_price: number }[];
};

export type Relationship = {
  customer_id: number;
  merchant_id: number;
  customer_name: string;
  merchant_name: string;
  visit_count: number;
  tier: string;
  next_tier_threshold: number | null;
  visits_to_next_tier: number;
  p_alive: number;
  predicted_clv: number;
  postpaid_eligible: boolean;
  last_visit_date: string | null;
  days_since_last_visit: number | null;
};

export type Pulse = {
  forecast_30d: { date: string; value: number; lower: number; upper: number }[];
  busiest_hours: string[];
  top_regulars: Relationship[];
  anomaly: { description: string; severity: string } | null;
  churn_alerts: Relationship[];
  cashflow_note: string;
  briefing: string;
};

/**
 * One illustrative demo comparison platform's price for a SKU.
 * ZipKart / SpeedBasket / CityMart Express / QuickHive are fictional platforms
 * invented for this prototype - not live data, and never used by the pricing logic.
 */
export type DemoPlatformPrice = {
  platform: string;
  price: number;
  was_price: number;
  illustrative: boolean;
};

export type PricingInsight = {
  sku: string;
  your_price: number;
  /** Genuinely computed: mean price across SVD-similar peer merchants in our own network. */
  benchmark_price: number;
  peer_count?: number;
  peer_prices?: { merchant_id: number; label: string; price: number }[];
  demo_platforms?: DemoPlatformPrice[];
  flag: "green" | "red";
  comparison_shopped: boolean;
  recommendation: string;
  suggested_points: number;
};

export type RewardOffer = {
  customer_id: number;
  tier: string;
  selected_arm: string;
  multiplier: number;
  last_purchase_amount: number;
  points_earned: number;
  points_balance: number;
  redemption_rates: Record<string, number>;
  explanation: string;
  redeemed_points?: number;
};

export type MerchantRewardSummary = {
  merchant_id: number;
  points_issued_this_month: number;
  estimated_cost: number;
  estimated_retained_revenue: number;
  assumption: string;
};

export type LoanReadiness = {
  merchant_id: number;
  tier: string;
  tier_index: number;
  progress_to_next_tier: number;
  next_tier_probability: number;
  coaching: string[];
  top_factors: { feature: string; value: number }[];
};

export type PaymentStatus = "CREATED" | "INITIATED" | "PENDING" | "CONFIRMED" | "FAILED" | "CANCELLED";
export type PaymentResult = {
  id: string; created_at: string; customer_id: number; merchant_id: number;
  order_id: string | null; amount_paise: number; currency: "INR";
  status: PaymentStatus; mode: "DEMO_SIMULATED"; externally_verified: false;
  refund_status: string; dispute_status: string;
};
export type Order = {
  id: string; customer_id: number; merchant_id: number; mission_id: string | null;
  total_paise: number; currency: "INR";
  status: "DRAFT" | "AWAITING_APPROVAL" | "CONFIRMED" | "FULFILLMENT_PENDING" | "FULFILLED" | "CANCELLED" | "FAILED";
  items: { offer_id: string; quantity: number; unit_price_paise: number }[];
};
export type MissionStatus = "CREATED" | "PLANNING" | "AWAITING_APPROVAL" | "EXECUTING" | "REPLANNING" | "VERIFYING" | "COMPLETED" | "BLOCKED" | "FAILED" | "CANCELLED";
export type Mission = {
  id: string; goal: string; budget_paise: number; status: MissionStatus;
  authorization_scope: Record<string, unknown>; requirements: Record<string, unknown>;
};
export type DemoWallet = { display_balance_paise: number; source: string };

export const mutationKey = () => crypto.randomUUID();
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? "/api"}${path}`, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.error?.message === "string" ? body.error.message : `API request failed: ${response.status}`);
  return body as T;
}
function scoped(role: Role, id: number, data?: unknown, key?: string): RequestInit {
  return { method: data === undefined ? "GET" : "POST", headers: {
    "Content-Type": "application/json", "X-Demo-Role": role, "X-Demo-Id": String(id),
    ...(key ? { "Idempotency-Key": key } : {})
  }, ...(data === undefined ? {} : { body: JSON.stringify(data) }) };
}

export const api = {
  customers: () => request<Customer[]>("/customers"),
  merchants: () => request<Merchant[]>("/merchants"),
  stats: () => request<DemoStats>("/stats"),
  customer: (id: number) => request<Customer>(`/customers/${id}`),
  merchant: (id: number) => request<Merchant>(`/merchants/${id}`),
  customerTransactions: (id: number) => request<Transaction[]>(`/customers/${id}/transactions`, scoped("customer", id)),
  merchantTransactions: (id: number) => request<Transaction[]>(`/merchants/${id}/transactions`, scoped("merchant", id)),
  relationship: (customerId: number, merchantId: number) => request<Relationship>(`/relationship/${customerId}/${merchantId}`),
  pulse: (merchantId: number) => request<Pulse>(`/merchant/${merchantId}/pulse`),
  pricing: (merchantId: number) => request<PricingInsight[]>(`/merchant/${merchantId}/pricing`),
  rewardOffer: (customerId: number) => request<RewardOffer>(`/rewards/${customerId}/multiplier`, scoped("customer", customerId)),
  merchantRewards: (merchantId: number) => request<MerchantRewardSummary>(`/merchant/${merchantId}/rewards`),
  loanReadiness: (merchantId: number) => request<LoanReadiness>(`/merchant/${merchantId}/loan-readiness`),
  wallet: (id: number) => request<DemoWallet>(`/customers/${id}/wallet`, scoped("customer", id)),
  resetDemo: () => request<{ ok: boolean }>("/reset-demo", { method: "POST", headers: { "X-Reset-Token": import.meta.env.VITE_RESET_TOKEN ?? "local-reset" } }),
  createPayment: (customerId: number, merchantId: number, amountPaise: number, key: string) =>
    request<PaymentResult>("/payments", scoped("customer", customerId, { merchant_id: merchantId, amount_paise: amountPaise, currency: "INR" }, key)),
  payment: (id: string, customerId: number) => request<PaymentResult>(`/payments/${id}`, scoped("customer", customerId)),
  simulatePayment: (id: string, customerId: number, status: "CONFIRMED" | "FAILED" | "CANCELLED", key: string) =>
    request<PaymentResult>(`/payments/${id}/simulate`, scoped("customer", customerId, { status, event_key: key }, key)),
  payments: (role: Role, id: number) => request<PaymentResult[]>("/payments", scoped(role, id)),
  orders: (role: Role, id: number) => request<Order[]>("/orders", scoped(role, id)),
  createMission: (customerId: number, goal: string, key: string) => request<Mission>("/missions", scoped("customer", customerId, {
    goal, budget_paise: 250000,
    requirements: { products: [{ product_id: "projector-rental-01", quantity: 1 }, { product_id: "snack-box", quantity: 10 }, { product_id: "drink-bottle", quantity: 10 }] }
  }, key)),
  redeemReward: (customerId: number, offer: string, points: number) =>
    request<{ ok: boolean; reward: RewardOffer }>(`/rewards/${customerId}/redeem`, scoped("customer", customerId, { offer, points }, mutationKey())),
  pricingActions: (merchantId: number) => request<{ sku: string }[]>(`/merchant/${merchantId}/pricing/actions`, scoped("merchant", merchantId)),
  acceptPricing: (merchantId: number, sku: string) =>
    request<{ ok: boolean }>(`/merchant/${merchantId}/pricing/actions`, scoped("merchant", merchantId, { sku, action: "accept" }, mutationKey()))
};

export const rupees = (amount: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount);

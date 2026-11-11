import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  ArrowLeft,
  Banknote,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Check,
  Gift,
  Info,
  LineChart,
  Mic,
  PhoneCall,
  QrCode,
  ReceiptText,
  Send,
  Smartphone,
  Sparkles,
  Tag,
  WalletCards,
  Zap,
  TrendingDown,
  TrendingUp
} from "lucide-react";
import { useApp } from "./context/useApp";
import {
  api,
  Customer,
  LoanReadiness,
  Merchant,
  MerchantRewardSummary,
  PaymentResult,
  PricingInsight,
  Pulse,
  RewardOffer,
  rupees,
  Transaction
} from "./lib/api";
import { paymentIntents } from "./lib/upi";
import {
  AIBadge,
  AnimatedNumber,
  Avatar,
  BottomNav,
  Card,
  CategoryChip,
  InsightCard,
  LocalTopBar,
  MerchantSelect,
  MetaChip,
  NavKey,
  Pill,
  PlatformBadge,
  ProgressBar,
  ScreenTransition,
  SkeletonBlock,
  StatBadge,
  tapProps,
  TopBar
} from "./components/ui";

type CustomerScreen = "home" | "scan" | "amount" | "processing" | "success" | "bills" | "recharge" | "tx";
type MerchantScreen = "home" | "insights" | "call-list" | "pricing" | "rewards" | "loan";

type DataState = {
  customers: Customer[];
  merchants: Merchant[];
  customer?: Customer;
  merchant?: Merchant;
  customerTx: Transaction[];
  merchantTx: Transaction[];
  relationship?: import("./lib/api").Relationship;
  pulse?: Pulse;
  pricing: PricingInsight[];
  rewardOffer?: RewardOffer;
  merchantRewards?: MerchantRewardSummary;
  loan?: LoanReadiness;
  loading: boolean;
  error?: string;
};

const emptyData: DataState = { customers: [], merchants: [], customerTx: [], merchantTx: [], pricing: [], loading: true };
type Toast = { id: number; message: string };

function App({ onExitToLanding }: { onExitToLanding?: () => void }) {
  const { role, setRole, customerId, setCustomerId, merchantId, setMerchantId } = useApp();
  const [nav, setNav] = useState<NavKey>("home");
  const [customerScreen, setCustomerScreen] = useState<CustomerScreen>("home");
  const [merchantScreen, setMerchantScreen] = useState<MerchantScreen>("home");
  const [selectedMerchant, setSelectedMerchant] = useState<Merchant>();
  const [selectedTx, setSelectedTx] = useState<Transaction>();
  const [paymentResult, setPaymentResult] = useState<PaymentResult>();
  const [data, setData] = useState<DataState>(emptyData);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string) => {
    const id = Date.now();
    setToasts((items) => [...items, { id, message }]);
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 2600);
  }, []);

  const loadData = useCallback(async () => {
    setData((previous) => ({ ...previous, loading: true, error: undefined }));
    try {
      const [customers, merchants, customer, merchant, customerTx, merchantTx, relationship, pulse, pricing, rewardOffer, merchantRewards, loan] = await Promise.all([
        api.customers(),
        api.merchants(),
        api.customer(customerId),
        api.merchant(merchantId),
        api.customerTransactions(customerId),
        api.merchantTransactions(merchantId),
        api.relationship(customerId, merchantId),
        api.pulse(merchantId),
        api.pricing(merchantId),
        api.rewardOffer(customerId),
        api.merchantRewards(merchantId),
        api.loanReadiness(merchantId)
      ]);
      setData({ customers, merchants, customer, merchant, customerTx, merchantTx, relationship, pulse, pricing, rewardOffer, merchantRewards, loan, loading: false });
    } catch (error) {
      setData((previous) => ({ ...previous, loading: false, error: error instanceof Error ? error.message : "Unable to load data" }));
    }
  }, [customerId, merchantId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    setNav("home");
    setCustomerScreen("home");
    setMerchantScreen("home");
  }, [role]);

  const resetDemo = async () => {
    await api.resetDemo();
    setPaymentResult(undefined);
    setSelectedTx(undefined);
    setCustomerScreen("home");
    setMerchantScreen("home");
    await loadData();
  };

  const handleBottomNav = (next: NavKey) => {
    setNav(next);
    setCustomerScreen("home");
    setMerchantScreen(next === "home" ? "home" : (next as MerchantScreen));
  };

  return (
    <div className="min-h-screen bg-bg text-text-primary">
      <TopBar role={role} onRoleChange={setRole} onReset={resetDemo} onHome={onExitToLanding} />
      <main className="relative mx-auto max-w-[430px] px-4 pb-28 pt-4">
        {data.error ? <OfflineHint message={data.error} /> : null}
        <AnimatePresence mode="wait">
          <ScreenTransition id={`${role}-${nav}-${customerScreen}-${merchantScreen}-${customerId}-${merchantId}`}>
            {role === "customer" ? (
              <CustomerView
                nav={nav}
                screen={customerScreen}
                setScreen={setCustomerScreen}
                data={data}
                setCustomerId={setCustomerId}
                setMerchantId={setMerchantId}
                setNav={handleBottomNav}
                selectedMerchant={selectedMerchant}
                setSelectedMerchant={setSelectedMerchant}
                selectedTx={selectedTx}
                setSelectedTx={setSelectedTx}
                paymentResult={paymentResult}
                setPaymentResult={setPaymentResult}
                reload={loadData}
                resetDemo={resetDemo}
                showToast={showToast}
              />
            ) : (
              <MerchantView
                screen={merchantScreen}
                setScreen={(screen) => {
                  setMerchantScreen(screen);
                  if (screen !== "home") setNav(screen as NavKey);
                }}
                data={data}
                setMerchantId={setMerchantId}
                showToast={showToast}
              />
            )}
          </ScreenTransition>
        </AnimatePresence>
      </main>
      {role === "merchant" ? <SoundboxCopilot pulse={data.pulse} pricing={data.pricing} loan={data.loan} /> : null}
      <ToastViewport toasts={toasts} />
      <BottomNav role={role} active={nav} onChange={handleBottomNav} />
    </div>
  );
}

function ToastViewport({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="pointer-events-none fixed inset-x-4 bottom-24 z-50 mx-auto max-w-[430px] space-y-2">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.98 }}
            className="rounded-2xl border border-success bg-surface px-4 py-3 text-sm font-black text-success shadow-soft"
          >
            {toast.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function OfflineHint({ message }: { message: string }) {
  return (
    <Card className="mb-4 border-danger">
      <p className="text-sm font-black text-danger">Backend not reachable</p>
      <p className="mt-1 text-xs text-text-muted">{message}</p>
    </Card>
  );
}

function CustomerView(props: {
  nav: NavKey;
  screen: CustomerScreen;
  setScreen: (screen: CustomerScreen) => void;
  data: DataState;
  setCustomerId: (id: number) => void;
  setMerchantId: (id: number) => void;
  setNav: (nav: NavKey) => void;
  selectedMerchant?: Merchant;
  setSelectedMerchant: (merchant?: Merchant) => void;
  selectedTx?: Transaction;
  setSelectedTx: (tx?: Transaction) => void;
  paymentResult?: PaymentResult;
  setPaymentResult: (result?: PaymentResult) => void;
  reload: () => Promise<void>;
  resetDemo: () => Promise<void>;
  showToast: (message: string) => void;
}) {
  if (props.nav === "profile") return <ProfileScreen data={props.data} setCustomerId={props.setCustomerId} resetDemo={props.resetDemo} />;
  if (props.nav === "rewards") return <CustomerRewards customer={props.data.customer} rewardOffer={props.data.rewardOffer} reload={props.reload} showToast={props.showToast} />;
  if (props.nav === "pay") {
    if (props.screen === "amount") return <AmountEntry customer={props.data.customer} merchant={props.selectedMerchant} setScreen={props.setScreen} setPaymentResult={props.setPaymentResult} reload={props.reload} />;
    if (props.screen === "processing") return <ProcessingScreen />;
    if (props.screen === "success") return <PaymentSuccess result={props.paymentResult} rewardOffer={props.data.rewardOffer} goHome={() => props.setNav("home")} />;
    return <ScanQrScreen data={props.data} selectMerchant={(merchant) => { props.setSelectedMerchant(merchant); props.setScreen("amount"); }} />;
  }
  if (props.screen === "bills") return <StaticCustomerScreen title="Bills" icon={<ReceiptText />} back={() => props.setScreen("home")} text="Bill payments are coming soon in the full product." />;
  if (props.screen === "recharge") return <StaticCustomerScreen title="Recharge" icon={<Zap />} back={() => props.setScreen("home")} text="Mobile recharge rewards will plug into the same wallet." />;
  if (props.screen === "tx") return <TransactionDetail tx={props.selectedTx} back={() => props.setScreen("home")} />;
  return <CustomerHome data={props.data} setCustomerId={props.setCustomerId} setMerchantId={props.setMerchantId} setNav={props.setNav} setScreen={props.setScreen} setSelectedTx={props.setSelectedTx} resetDemo={props.resetDemo} />;
}

function CustomerHome({ data, setCustomerId, setMerchantId, setNav, setScreen, setSelectedTx, resetDemo }: {
  data: DataState;
  setCustomerId: (id: number) => void;
  setMerchantId: (id: number) => void;
  setNav: (nav: NavKey) => void;
  setScreen: (screen: CustomerScreen) => void;
  setSelectedTx: (tx: Transaction) => void;
  resetDemo: () => Promise<void>;
}) {
  const spend = data.customerTx.slice(0, 20).reduce((sum, tx) => sum + tx.amount, 0);
  const wallet = Math.max(120, 7500 - spend);
  const points = data.rewardOffer?.points_balance ?? 0;
  return (
    <div className="space-y-4">
      <LocalTopBar name={data.customer?.name ?? "Demo Customer"} onProfile={() => setNav("profile")} onReset={resetDemo} />
      <div>
        <p className="mb-2 px-1 text-[11px] font-bold uppercase tracking-wide text-text-muted">Demo customer</p>
        <select value={data.customer?.id ?? 6} onChange={(event) => setCustomerId(Number(event.target.value))} className="w-full rounded-full border border-border bg-surface px-4 py-3 text-sm font-bold text-text-primary shadow-soft">
          {data.customers.slice(0, 25).map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}
        </select>
      </div>
      <Card className="wallet-card border-paytm-navy text-text-inverse" delay={0.02}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-text-inverse/70">Wallet balance</p>
            <h1 className="mt-1 text-3xl font-black text-text-inverse"><AnimatedNumber value={wallet} prefix="₹" /></h1>
          </div>
          <WalletCards className="text-paytm-cyan" size={38} />
        </div>
        <motion.button
          {...tapProps}
          onClick={() => setNav("rewards")}
          className="mt-4 flex w-full items-center justify-between rounded-full border border-text-inverse/25 bg-text-inverse/10 px-4 py-2 text-left text-xs font-black text-text-inverse"
        >
          <span className="flex items-center gap-2"><Gift size={15} className="text-paytm-cyan" /> Rewards points</span>
          <span><AnimatedNumber value={points} /> pts</span>
        </motion.button>
        <div className="mt-5 grid grid-cols-3 gap-2 text-center text-xs font-bold">
          <Pill onClick={() => setNav("pay")} className="bg-paytm-cyan text-paytm-navy">UPI</Pill>
          <Pill onClick={() => setScreen("bills")} className="border border-text-inverse text-text-inverse">Bills</Pill>
          <Pill onClick={() => setNav("rewards")} className="border border-text-inverse text-text-inverse">Offers</Pill>
        </div>
      </Card>
      <MerchantSelect
        merchants={data.merchants}
        value={data.merchant?.id}
        onChange={setMerchantId}
        label="Store you're shopping at"
      />
      <Card className="border-paytm-cyan" delay={0.08}>
        <div className="flex items-start gap-3">
          <div className="rounded-full bg-paytm-cyan px-3 py-1 text-xs font-black text-paytm-navy">AI</div>
          <div className="flex-1">
            <h2 className="text-base font-black text-paytm-navy">Your Paytm Grow Insight</h2>
            <p className="mt-1 text-sm leading-6 text-text-muted">
              You are a {data.relationship?.tier ?? "New"} at {data.merchant?.name ?? "this store"} with <AnimatedNumber value={Math.round((data.relationship?.p_alive ?? 0) * 100)} suffix="%" /> Loyalty Points health.
            </p>
            <div className="mt-3">
              <ProgressBar value={data.relationship?.next_tier_threshold ? (data.relationship.visit_count / data.relationship.next_tier_threshold) * 100 : 100} label={data.relationship?.next_tier_threshold ? `${data.relationship.visits_to_next_tier} visits to next tier` : "VIP rewards unlocked"} />
            </div>
            {data.relationship?.postpaid_eligible ? <p className="mt-3 rounded-2xl border border-success p-3 text-xs font-bold text-success">Interest-free Postpaid is available at this trusted store.</p> : null}
          </div>
        </div>
      </Card>
      <div className="grid grid-cols-4 gap-2">
        <QuickAction icon={<QrCode />} label="Scan & Pay" onClick={() => setNav("pay")} />
        <QuickAction icon={<Zap />} label="Recharge" onClick={() => setScreen("recharge")} />
        <QuickAction icon={<ReceiptText />} label="Bills" onClick={() => setScreen("bills")} />
        <QuickAction icon={<Gift />} label="Rewards" onClick={() => setNav("rewards")} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <StatBadge label="Home store" value={data.customer?.home_merchant_name ?? "Loading"} />
        <StatBadge label="Recent spend" value={<AnimatedNumber value={spend} prefix="₹" />} tone="green" />
      </div>
      <TransactionList transactions={data.customerTx} empty="Recent customer payments will appear here." onClick={(tx) => { setSelectedTx(tx); setScreen("tx"); }} />
    </div>
  );
}

function QuickAction({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <motion.button {...tapProps} whileHover={{ y: -3 }} onClick={onClick} className="flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl border border-border bg-surface p-2 text-center text-xs font-black text-paytm-navy shadow-soft">
      <span className="grid h-11 w-11 place-items-center rounded-full border border-paytm-cyan text-paytm-navy">{icon}</span>
      {label}
    </motion.button>
  );
}

function ScanQrScreen({ data, selectMerchant }: { data: DataState; selectMerchant: (merchant: Merchant) => void }) {
  return (
    <div className="space-y-4">
      <Card className="text-center">
        <div className="mx-auto grid h-52 w-52 place-items-center rounded-2xl border-4 border-paytm-cyan">
          <QrCode size={118} className="text-paytm-navy" />
        </div>
        <h2 className="mt-5 text-xl font-black text-text-primary">Scan QR</h2>
        <p className="mt-2 text-sm text-text-muted">Scanning for nearby Paytm QR codes...</p>
      </Card>
      <Card>
        <h3 className="text-base font-black text-text-primary">Nearby merchants</h3>
        <p className="mt-1 text-xs text-text-muted">One shop from each category, so any category can be paid and compared.</p>
        <div className="mt-3 space-y-2">
          {nearbyMerchants(data.merchants).map((merchant) => (
            <button key={merchant.id} onClick={() => selectMerchant(merchant)} className="flex w-full items-center gap-3 rounded-2xl border border-border bg-surface p-3 text-left">
              <Avatar name={merchant.name} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-black text-text-primary">{merchant.name}</p>
                <div className="mt-1 flex items-center gap-2">
                  <CategoryChip category={merchant.category} />
                  <span className="truncate text-xs text-text-muted">{merchant.locality}</span>
                </div>
              </div>
              <ChevronRight className="shrink-0 text-text-muted" size={18} />
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}

/** One merchant per category, so the Pay flow can reach every category from this list. */
function nearbyMerchants(merchants: Merchant[]) {
  const seen = new Set<string>();
  return merchants.filter((merchant) => {
    if (seen.has(merchant.category)) return false;
    seen.add(merchant.category);
    return true;
  });
}

function AmountEntry({ customer, merchant, setScreen, setPaymentResult, reload }: {
  customer?: Customer;
  merchant?: Merchant;
  setScreen: (screen: CustomerScreen) => void;
  setPaymentResult: (result?: PaymentResult) => void;
  reload: () => Promise<void>;
}) {
  const [amount, setAmount] = useState("");
  const numeric = Number(amount || 0);
  const txnNote = `Paytm Grow payment to ${merchant?.name ?? "merchant"}`;
  const press = (key: string) => {
    if (key === "del") setAmount((value) => value.slice(0, -1));
    else if (key === "." && amount.includes(".")) return;
    else setAmount((value) => `${value}${key}`);
  };
  const pay = async () => {
    if (!customer || !merchant || numeric <= 0) return;
    setScreen("processing");
    await new Promise((resolve) => setTimeout(resolve, 900));
    const result = await api.createPayment(customer.id, merchant.id, numeric, txnNote);
    setPaymentResult(result);
    await reload();
    setScreen("success");
  };
  return (
    <div className="space-y-4">
      <button onClick={() => setScreen("scan")} className="flex items-center gap-2 text-sm font-black text-paytm-navy"><ArrowLeft size={17} /> Back</button>
      <Card className="text-center">
        <div className="mx-auto w-fit"><Avatar name={merchant?.name ?? "Merchant"} /></div>
        <h2 className="mt-3 text-xl font-black text-text-primary">{merchant?.name ?? "Merchant"}</h2>
        <div className="mt-2 flex items-center justify-center gap-2">
          <CategoryChip category={merchant?.category} />
          {merchant?.vpa ? <span className="text-xs font-bold text-text-muted">{merchant.vpa}</span> : null}
        </div>
        <p className="mt-2 text-sm text-text-muted">Paying as {customer?.name ?? "demo customer"}</p>
        <div className="mt-6 text-4xl font-black text-paytm-navy">{rupees(numeric)}</div>
      </Card>
      <div className="grid grid-cols-3 gap-3">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "0", "del"].map((key) => (
          <button key={key} onClick={() => press(key)} className="h-14 rounded-2xl border border-border bg-surface text-xl font-black text-text-primary shadow-soft">{key === "del" ? "⌫" : key}</button>
        ))}
      </div>
      <button disabled={numeric <= 0} onClick={pay} className="w-full rounded-full bg-paytm-navy py-4 text-sm font-black text-text-inverse disabled:border disabled:border-border disabled:bg-bg disabled:text-text-muted">
        Pay {numeric > 0 ? rupees(numeric) : ""}
      </button>
      <UpiIntentPanel merchant={merchant} amount={numeric} note={txnNote} />
    </div>
  );
}

/**
 * Secondary, genuinely real payment affordance.
 *
 * The link below is a real UPI deep link in the NPCI URI format, built from this
 * merchant's actual VPA. On a phone with Paytm installed, tapping it hands off to
 * the real Paytm app. On a demo laptop no app is registered for the scheme, so it
 * simply will not resolve - which is why the simulated in-browser payment above
 * stays the primary demo path. The link string is shown in full so it can be
 * checked as a correctly-formed intent.
 */
function UpiIntentPanel({ merchant, amount, note }: { merchant?: Merchant; amount: number; note: string }) {
  const [open, setOpen] = useState(false);
  if (!merchant?.vpa) return null;
  const payable = amount > 0 ? amount : 0;
  const { paytmIntent, upiIntent } = paymentIntents({
    payeeVpa: merchant.vpa,
    payeeName: merchant.name,
    amount: payable,
    note
  });
  return (
    <Card className="border-paytm-cyan">
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-paytm-cyan text-paytm-navy">
          <Smartphone size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-black text-text-primary">Pay with Paytm</h3>
          <p className="mt-1 text-xs leading-5 text-text-muted">
            This is a real Paytm-compatible UPI payment link. It opens the Paytm app on a phone; on this laptop nothing is
            registered to handle it.
          </p>
        </div>
      </div>
      <motion.a
        {...tapProps}
        href={paytmIntent}
        onClick={() => {
          // A real handoff attempt, not a mock: assigning the URI is exactly how a
          // web page invokes an installed UPI app.
          window.location.href = paytmIntent;
        }}
        className="mt-3 block rounded-full bg-paytm-cyan py-3 text-center text-sm font-black text-paytm-navy"
      >
        Pay {payable > 0 ? rupees(payable) : ""} with Paytm
      </motion.a>
      <button
        onClick={() => setOpen((value) => !value)}
        className="mt-3 flex w-full items-center justify-between gap-2 text-left text-xs font-black text-paytm-navy"
      >
        View UPI payment link
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={16} />
        </motion.span>
      </button>
      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-3">
              <div>
                <p className="text-[10px] font-black uppercase tracking-wide text-text-muted">Paytm app scheme</p>
                <p className="mt-1 break-all rounded-2xl border border-border bg-bg p-3 font-mono text-[10px] leading-4 text-paytm-navy">{paytmIntent}</p>
              </div>
              <div>
                <p className="text-[10px] font-black uppercase tracking-wide text-text-muted">Universal NPCI UPI scheme</p>
                <p className="mt-1 break-all rounded-2xl border border-border bg-bg p-3 font-mono text-[10px] leading-4 text-paytm-navy">{upiIntent}</p>
              </div>
              <p className="text-[11px] leading-5 text-text-muted">
                Standard UPI parameters: <span className="font-bold">pa</span> payee VPA, <span className="font-bold">pn</span> payee
                name, <span className="font-bold">am</span> amount, <span className="font-bold">cu</span> currency,{" "}
                <span className="font-bold">tn</span> note. The backend adds <span className="font-bold">tr</span> (its orderId) when
                the payment is created.
              </p>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </Card>
  );
}

function ProcessingScreen() {
  return (
    <Card className="min-h-72 text-center">
      <div className="mx-auto mt-10 h-16 w-16 animate-pulse rounded-full bg-paytm-cyan" />
      <h2 className="mt-6 text-xl font-black text-text-primary">Processing payment</h2>
      <p className="mt-2 text-sm text-text-muted">Updating transaction history and Loyalty Points...</p>
    </Card>
  );
}

function PaymentSuccess({ result, rewardOffer, goHome }: { result?: PaymentResult; rewardOffer?: RewardOffer; goHome: () => void }) {
  const relationship = result?.relationship;
  const pointsEarned = rewardOffer?.points_earned ?? Math.max(1, Math.round((result?.transaction.amount ?? 0) / 10));
  return (
    <div className="space-y-4">
      <Card className="border-success text-center">
        <CheckCircle2 className="mx-auto text-success" size={58} />
        <h2 className="mt-4 text-2xl font-black text-text-primary">Payment Success</h2>
        <p className="mt-2 text-3xl font-black text-paytm-navy"><AnimatedNumber value={result?.transaction.amount ?? 0} prefix="₹" /></p>
        <p className="mt-3 text-sm leading-6 text-text-muted">
          This is your {ordinal(relationship?.visit_count ?? 1)} payment to {relationship?.merchant_name ?? "this merchant"} — you're now a {relationship?.tier ?? "New"}.
        </p>
        {relationship?.postpaid_eligible ? <p className="mt-4 rounded-2xl border border-success p-3 text-xs font-bold text-success">Postpaid nudge: interest-free Pay Later is available at this trusted store.</p> : null}
      </Card>
      <Card className="relative overflow-hidden border-paytm-cyan text-center">
        <CelebrationBurst />
        <motion.div className="mx-auto grid h-16 w-16 place-items-center rounded-full border-4 border-paytm-cyan text-paytm-navy" initial={{ scale: 0.82 }} animate={{ scale: [0.82, 1.08, 1] }} transition={{ duration: 0.75 }}>
          <Gift size={28} />
        </motion.div>
        <p className="mt-3 text-xs font-black uppercase text-text-muted">Points earned</p>
        <p className="mt-1 text-3xl font-black text-paytm-navy"><AnimatedNumber value={pointsEarned} suffix=" pts" duration={0.8} /></p>
        <p className="mt-2 text-xs font-bold text-success">{rewardOffer?.selected_arm ?? `${rewardOffer?.multiplier ?? 1}x`} Rewards Boost applied</p>
      </Card>
      <PaymentReceiptPanel result={result} />
      <motion.button {...tapProps} onClick={goHome} className="w-full rounded-full bg-paytm-navy py-4 text-sm font-black text-text-inverse">Back to Home</motion.button>
    </div>
  );
}

/**
 * The order the backend actually recorded, shown with Paytm-style field names and
 * the real UPI deep link generated for it (`tr` carries our orderId).
 */
function PaymentReceiptPanel({ result }: { result?: PaymentResult }) {
  const [open, setOpen] = useState(false);
  const payment = result?.payment;
  if (!payment) return null;
  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-black uppercase tracking-wide text-text-muted">Order</p>
          <p className="truncate text-sm font-black text-text-primary">{payment.orderId}</p>
        </div>
        <MetaChip tone="live">{payment.txnStatus}</MetaChip>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
        <div className="rounded-2xl border border-border p-2">
          <p className="font-bold uppercase text-text-muted">payerVpa</p>
          <p className="truncate font-mono text-paytm-navy">{payment.payerVpa}</p>
        </div>
        <div className="rounded-2xl border border-border p-2">
          <p className="font-bold uppercase text-text-muted">payeeVpa</p>
          <p className="truncate font-mono text-paytm-navy">{payment.payeeVpa}</p>
        </div>
      </div>
      <button onClick={() => setOpen((value) => !value)} className="mt-3 flex w-full items-center justify-between gap-2 text-left text-xs font-black text-paytm-navy">
        View UPI payment link
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={16} />
        </motion.span>
      </button>
      <AnimatePresence>
        {open ? (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <p className="mt-3 break-all rounded-2xl border border-border bg-bg p-3 font-mono text-[10px] leading-4 text-paytm-navy">{payment.paytmIntent}</p>
            <p className="mt-2 break-all rounded-2xl border border-border bg-bg p-3 font-mono text-[10px] leading-4 text-paytm-navy">{payment.upiIntent}</p>
            <p className="mt-2 text-[11px] leading-5 text-text-muted">
              Generated by the backend for this order in the standard NPCI UPI URI format that the Paytm app resolves.
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </Card>
  );
}

function CelebrationBurst() {
  const dots = Array.from({ length: 10 });
  return (
    <div className="pointer-events-none absolute inset-0">
      {dots.map((_, index) => {
        const angle = (index / dots.length) * Math.PI * 2;
        return (
          <motion.span
            key={index}
            initial={{ opacity: 0, x: 0, y: 0, scale: 0.4 }}
            animate={{ opacity: [0, 1, 0], x: Math.cos(angle) * 74, y: Math.sin(angle) * 44, scale: [0.4, 1, 0.2] }}
            transition={{ duration: 0.82, delay: 0.08 }}
            className="absolute left-1/2 top-14 h-2 w-2 rounded-full bg-paytm-cyan"
          />
        );
      })}
    </div>
  );
}

function CustomerRewards({ customer, rewardOffer, reload, showToast }: { customer?: Customer; rewardOffer?: RewardOffer; reload: () => Promise<void>; showToast: (message: string) => void }) {
  const [balanceStart, setBalanceStart] = useState(0);
  const [balanceEnd, setBalanceEnd] = useState(rewardOffer?.points_balance ?? 0);
  useEffect(() => {
    setBalanceStart(0);
    setBalanceEnd(rewardOffer?.points_balance ?? 0);
  }, [customer?.id]);
  useEffect(() => {
    if (rewardOffer?.points_balance !== undefined && rewardOffer.points_balance !== balanceEnd) {
      setBalanceStart(balanceEnd);
      setBalanceEnd(rewardOffer.points_balance);
    }
  }, [rewardOffer?.points_balance]);
  const offers = [
    { name: "₹25 mobile recharge discount", points: 120 },
    { name: "₹40 bill payment credit", points: 180 },
    { name: "Travel voucher starter pack", points: 260 },
    { name: "Local store cashback token", points: 90 }
  ];
  const redeem = async (offer: { name: string; points: number }) => {
    if (!customer) return;
    const previousBalance = rewardOffer?.points_balance ?? balanceEnd;
    const result = await api.redeemReward(customer.id, offer.name, offer.points);
    setBalanceStart(previousBalance);
    setBalanceEnd(result.reward.points_balance);
    showToast(`Redeemed! ${offer.name} is ready for your next bill.`);
    await reload();
  };
  return (
    <div className="space-y-4">
      <Card className="wallet-card border-paytm-navy text-text-inverse">
        <p className="text-xs font-bold text-text-inverse/70">Rewards wallet</p>
        <h2 className="mt-1 text-3xl font-black text-text-inverse"><AnimatedNumber start={balanceStart} value={balanceEnd} suffix=" points" /></h2>
        <p className="mt-2 text-sm text-text-inverse/70">Redeemable in your wallet for recharges, bills, travel.</p>
      </Card>
      <div className="live-glow rounded-2xl">
        <InsightCard icon={<Sparkles size={20} />} headline={`${rewardOffer?.selected_arm ?? "1x"} active multiplier`} subtext={rewardOffer?.explanation ?? "Rewards Boost is loading."} />
      </div>
      <div className="space-y-2">
        {offers.map((offer) => (
          <Card key={offer.name} className="flex items-center gap-3 py-3">
            <Gift className="text-paytm-cyan" size={24} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-black text-text-primary">{offer.name}</p>
              <p className="text-xs text-text-muted">{offer.points} points</p>
            </div>
            <motion.button {...tapProps} disabled={(rewardOffer?.points_balance ?? 0) < offer.points} onClick={() => redeem(offer)} className="rounded-full bg-paytm-navy px-4 py-2 text-xs font-black text-text-inverse disabled:border disabled:border-border disabled:bg-bg disabled:text-text-muted">Redeem</motion.button>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ProfileScreen({ data, setCustomerId, resetDemo }: { data: DataState; setCustomerId: (id: number) => void; resetDemo: () => Promise<void> }) {
  const loyaltyRows = data.customerTx.reduce<Record<string, number>>((acc, tx) => {
    acc[tx.merchant_name] = (acc[tx.merchant_name] ?? 0) + 1;
    return acc;
  }, {});
  return (
    <div className="space-y-4">
      <Card className="text-center">
        <div className="mx-auto w-fit"><Avatar name={data.customer?.name ?? "Customer"} /></div>
        <h2 className="mt-3 text-2xl font-black text-text-primary">{data.customer?.name}</h2>
        <p className="text-sm text-text-muted">{data.customer?.phone}</p>
        <p className="mt-2 text-sm font-bold text-paytm-navy">Home store: {data.customer?.home_merchant_name}</p>
      </Card>
      <select value={data.customer?.id ?? 6} onChange={(event) => setCustomerId(Number(event.target.value))} className="w-full rounded-full border border-border bg-surface px-4 py-3 text-sm font-bold text-text-primary shadow-soft">
        {data.customers.slice(0, 25).map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}
      </select>
      <Card>
        <h3 className="text-base font-black text-text-primary">Loyalty across merchants</h3>
        <div className="mt-3 space-y-2">
          {Object.entries(loyaltyRows).slice(0, 5).map(([name, count]) => (
            <div key={name} className="flex justify-between rounded-2xl border border-border p-3 text-sm">
              <span className="font-bold text-text-primary">{name}</span>
              <span className="text-text-muted">{count} visits</span>
            </div>
          ))}
        </div>
      </Card>
      <button onClick={resetDemo} className="w-full rounded-full bg-paytm-navy py-4 text-sm font-black text-text-inverse">Reset Demo Data</button>
    </div>
  );
}

function StaticCustomerScreen({ title, icon, text, back }: { title: string; icon: React.ReactNode; text: string; back: () => void }) {
  return (
    <div className="space-y-4">
      <button onClick={back} className="flex items-center gap-2 text-sm font-black text-paytm-navy"><ArrowLeft size={17} /> Back</button>
      <Card className="min-h-56 text-center">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-full border border-paytm-cyan text-paytm-navy">{icon}</div>
        <h2 className="mt-4 text-2xl font-black text-text-primary">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-text-muted">{text}</p>
      </Card>
    </div>
  );
}

function TransactionDetail({ tx, back }: { tx?: Transaction; back: () => void }) {
  if (!tx) return <StaticCustomerScreen title="Transaction" icon={<ReceiptText />} text="Select a transaction from recent activity." back={back} />;
  return (
    <div className="space-y-4">
      <button onClick={back} className="flex items-center gap-2 text-sm font-black text-paytm-navy"><ArrowLeft size={17} /> Back</button>
      <Card>
        <h2 className="text-2xl font-black text-text-primary">{rupees(tx.amount)}</h2>
        <p className="mt-1 text-sm text-text-muted">{tx.merchant_name}</p>
        <p className="text-xs text-text-muted">{new Date(tx.timestamp).toLocaleString("en-IN")}</p>
        <div className="mt-4 space-y-2">
          {tx.items.map((item) => (
            <div key={`${item.sku}-${item.unit_price}`} className="flex justify-between rounded-2xl border border-border p-3 text-sm">
              <span className="font-bold text-text-primary">{item.sku} × {item.quantity}</span>
              <span className="text-text-muted">{rupees(item.unit_price)}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function MerchantView({ screen, setScreen, data, setMerchantId, showToast }: { screen: MerchantScreen; setScreen: (screen: MerchantScreen) => void; data: DataState; setMerchantId: (id: number) => void; showToast: (message: string) => void }) {
  if (screen === "insights") return <InsightsTab pulse={data.pulse} merchant={data.merchant} />;
  if (screen === "call-list") return <CallListTab pulse={data.pulse} />;
  if (screen === "pricing") return <PricingTab merchant={data.merchant} pricing={data.pricing} showToast={showToast} />;
  if (screen === "rewards") return <MerchantRewardsTab summary={data.merchantRewards} />;
  if (screen === "loan") return <LoanReadinessTab loan={data.loan} />;
  return <MerchantHome data={data} setMerchantId={setMerchantId} setScreen={setScreen} />;
}

function MerchantHome({ data, setMerchantId, setScreen }: { data: DataState; setMerchantId: (id: number) => void; setScreen: (screen: MerchantScreen) => void }) {
  const redCount = data.pricing.filter((item) => item.flag === "red").length;
  const todayRevenue = data.merchantTx
    .filter((tx) => new Date(tx.timestamp).toDateString() === new Date().toDateString())
    .reduce((sum, tx) => sum + tx.amount, 0);
  const fallbackRevenue = data.merchantTx.slice(0, 12).reduce((sum, tx) => sum + tx.amount, 0);
  const activeRegulars = data.pulse?.top_regulars.length ?? 0;
  const pointsIssued = data.merchantRewards?.points_issued_this_month ?? 0;
  return (
    <div className="space-y-4">
      <MerchantSelect merchants={data.merchants} value={data.merchant?.id} onChange={setMerchantId} label="Demo merchant" />
      <div className="grid grid-cols-2 gap-2">
        <SummaryTile label="Today's revenue" value={<AnimatedNumber value={todayRevenue || fallbackRevenue} prefix="₹" />} trend="up" delay={0.02} />
        <SummaryTile label="Active regulars" value={<AnimatedNumber value={activeRegulars} />} trend="up" delay={0.08} />
        <SummaryTile label="Churn risk" value={<AnimatedNumber value={data.pulse?.churn_alerts.length ?? 0} />} trend={data.pulse?.churn_alerts.length ? "down" : "up"} delay={0.14} />
        <SummaryTile label="Points issued" value={<AnimatedNumber value={pointsIssued} />} trend="up" delay={0.2} />
      </div>
      <AICard hero title="Merchant Pulse briefing" icon={<LineChart />} onClick={() => setScreen("insights")} text={data.pulse?.briefing ?? "Pulse loading"} footer={<ForecastChart forecast={data.pulse?.forecast_30d ?? []} compact />} />
      <div className="grid grid-cols-2 gap-3">
        <AICard title="Loyalty call-list" icon={<PhoneCall />} onClick={() => setScreen("call-list")} text={`${data.pulse?.churn_alerts.length ?? 0} regulars need attention: ${(data.pulse?.churn_alerts ?? []).slice(0, 1).map((r) => r.customer_name).join(", ") || "none right now"}`} />
        <AICard title="Market Match" icon={<Tag />} onClick={() => setScreen("pricing")} text={redCount ? `${redCount} items need pricing attention.` : "You're competitive on every item this week."} />
        <AICard title="Rewards Boost" icon={<Gift />} onClick={() => setScreen("rewards")} text={`${pointsIssued.toLocaleString("en-IN")} points issued this month.`} />
        <AICard title="Loan Coach" icon={<Banknote />} onClick={() => setScreen("loan")} text={`${data.loan?.tier ?? "Loading"} · ${data.loan?.progress_to_next_tier ?? 0}% to next tier.`} />
      </div>
      <AICard title="Soundbox Copilot" icon={<Mic />} onClick={() => window.dispatchEvent(new Event("open-soundbox"))} text="Ask by voice or type from the floating Soundbox button." />
    </div>
  );
}

function SummaryTile({ label, value, trend, delay }: { label: string; value: React.ReactNode; trend: "up" | "down"; delay: number }) {
  return (
    <Card delay={delay} className="px-3 py-3">
      <div className="flex items-start justify-between">
        <p className="text-[11px] font-bold uppercase text-text-muted">{label}</p>
        {trend === "up" ? <TrendingUp size={15} className="text-success" /> : <TrendingDown size={15} className="text-warning" />}
      </div>
      <p className="mt-1 text-lg font-black text-paytm-navy">{value}</p>
    </Card>
  );
}

function AICard({ title, text, icon, onClick, footer, hero = false }: { title: string; text: string; icon: React.ReactNode; onClick: () => void; footer?: React.ReactNode; hero?: boolean }) {
  return (
    <motion.button {...tapProps} whileHover={{ y: -3, boxShadow: "0 16px 34px rgba(0, 46, 110, 0.13)" }} onClick={onClick} className={`w-full rounded-2xl border border-border bg-surface p-4 text-left shadow-soft ${hero ? "" : "min-h-40"}`}>
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 place-items-center rounded-full border border-paytm-cyan text-paytm-navy">{icon}</div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-black text-text-primary">{title}</h3>
            <AIBadge />
          </div>
          <p className="mt-2 text-xs leading-5 text-text-muted">{text}</p>
        </div>
      </div>
      {footer ? <div className="mt-3">{footer}</div> : null}
    </motion.button>
  );
}

function ForecastChart({ forecast, compact = false }: { forecast: Pulse["forecast_30d"]; compact?: boolean }) {
  const rows = forecast.map((item) => ({
    ...item,
    dateLabel: new Date(item.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
    band: Math.max(0, item.upper - item.lower)
  }));
  if (!rows.length) return <SkeletonBlock className={compact ? "h-28 w-full" : "h-52 w-full"} />;
  return (
    <div className={compact ? "h-36 w-full" : "h-64 w-full"}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 8, right: 4, left: -22, bottom: 0 }}>
          <defs>
            <linearGradient id="forecastLine" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00BAF2" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#00BAF2" stopOpacity={0.08} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="dateLabel" hide={compact} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
          <YAxis hide={compact} tick={{ fontSize: 10 }} tickFormatter={(value) => `₹${Math.round(Number(value) / 1000)}k`} tickLine={false} axisLine={false} />
          <Tooltip formatter={(value, name) => [rupees(Number(value ?? 0)), name === "value" ? "Forecast" : String(name)]} labelFormatter={(label) => `Date: ${label}`} />
          <Area type="monotone" dataKey="lower" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
          <Area type="monotone" dataKey="band" stackId="band" stroke="none" fill="url(#forecastLine)" name="Confidence band" animationDuration={650} />
          <Area type="monotone" dataKey="value" stroke="#002E6E" strokeWidth={3} fill="transparent" dot={false} animationDuration={900} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function InsightsTab({ pulse, merchant }: { pulse?: Pulse; merchant?: Merchant }) {
  const forecastTotal = pulse?.forecast_30d.reduce((sum, item) => sum + item.value, 0) ?? 0;
  const ready = useDelayedReveal(!!pulse, `${merchant?.id}-pulse`, 420);
  return (
    <div className="space-y-4">
      <Card className="wallet-card border-paytm-navy text-text-inverse">
        <p className="text-xs font-bold text-text-inverse/70">Merchant Pulse</p>
        <h2 className="text-xl font-black text-text-inverse">{merchant?.name ?? "Merchant"} briefing</h2>
        <div className="mt-4 text-sm leading-6 text-text-inverse/70">
          {ready ? <TextReveal text={pulse?.briefing ?? ""} /> : <SkeletonBlock className="h-24 bg-text-inverse/20" />}
        </div>
      </Card>
      <Card>
        <ForecastChart forecast={pulse?.forecast_30d ?? []} />
      </Card>
      <div className="grid grid-cols-2 gap-3">
        <StatBadge label="30d forecast" value={<AnimatedNumber value={forecastTotal} prefix="₹" />} />
        <StatBadge label="Peak hours" value={pulse?.busiest_hours.join(", ") || "NA"} tone="amber" />
      </div>
      <CallListTab pulse={pulse} compact />
    </div>
  );
}

function useDelayedReveal(ready: boolean, key: string, delay = 420) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    setVisible(false);
    if (!ready) return;
    const timer = window.setTimeout(() => setVisible(true), delay);
    return () => window.clearTimeout(timer);
  }, [ready, key, delay]);
  return visible;
}

function TextReveal({ text }: { text: string }) {
  const words = text.split(" ");
  return (
    <p>
      {words.map((word, index) => (
        <motion.span
          key={`${word}-${index}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.035, duration: 0.18 }}
          className="mr-1 inline-block"
        >
          {word}
        </motion.span>
      ))}
    </p>
  );
}

function CallListTab({ pulse, compact = false }: { pulse?: Pulse; compact?: boolean }) {
  const ready = useDelayedReveal(!!pulse, `call-${pulse?.briefing ?? "none"}-${compact}`, 360);
  return (
    <Card>
      <h3 className="text-base font-black text-text-primary">Regulars to call</h3>
      <p className="mt-1 text-xs text-text-muted">Ranked by low BG/NBD P(alive), with CLV shown.</p>
      <div className="mt-3 space-y-3">
        {!ready ? (
          <>
            <SkeletonBlock className="h-14" />
            <SkeletonBlock className="h-14" />
            <SkeletonBlock className="h-14" />
          </>
        ) : (pulse?.churn_alerts ?? []).length ? (pulse?.churn_alerts ?? []).slice(0, compact ? 4 : 20).map((regular) => (
          <div key={`${regular.customer_id}-${regular.merchant_id}`} className="flex items-center gap-3">
            <Avatar name={regular.customer_name} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-black text-text-primary">{regular.customer_name}</p>
              <p className="text-xs text-text-muted">{regular.days_since_last_visit} days · P(alive) <AnimatedNumber value={Math.round(regular.p_alive * 100)} suffix="%" /> · CLV <AnimatedNumber value={regular.predicted_clv} prefix="₹" /></p>
            </div>
            <PhoneCall className="text-paytm-navy" size={18} />
          </div>
        )) : <p className="rounded-2xl border border-success p-3 text-sm font-bold text-success">No urgent churn-risk regulars right now.</p>}
      </div>
    </Card>
  );
}

function PricingTab({ merchant, pricing, showToast }: { merchant?: Merchant; pricing: PricingInsight[]; showToast: (message: string) => void }) {
  const [selectedSku, setSelectedSku] = useState<string>("all");
  const [showInfo, setShowInfo] = useState(false);
  const [accepted, setAccepted] = useState<Record<string, boolean>>(() => {
    const key = merchant ? `pricing-actions-${merchant.id}` : "";
    if (!key) return {};
    try {
      return JSON.parse(localStorage.getItem(key) ?? "{}") as Record<string, boolean>;
    } catch {
      return {};
    }
  });
  useEffect(() => {
    if (!merchant) return;
    try {
      setAccepted(JSON.parse(localStorage.getItem(`pricing-actions-${merchant.id}`) ?? "{}") as Record<string, boolean>);
    } catch {
      setAccepted({});
    }
  }, [merchant?.id]);
  const ready = useDelayedReveal(!!pricing.length, `${merchant?.id}-pricing-${selectedSku}`, selectedSku === "all" ? 360 : 760);
  const selected = pricing.find((item) => item.sku === selectedSku);
  const acceptAction = async (item: PricingInsight) => {
    if (!merchant) return;
    await api.acceptPricing(merchant.id, item.sku);
    const next = { ...accepted, [item.sku]: true };
    setAccepted(next);
    localStorage.setItem(`pricing-actions-${merchant.id}`, JSON.stringify(next));
    showToast(`Action taken for ${item.sku}.`);
  };
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-black text-text-primary">Market Match</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <CategoryChip category={merchant?.category} />
              <span className="text-xs text-text-muted">{pricing.length} items tracked</span>
            </div>
            <p className="mt-2 text-sm text-text-muted">Your prices benchmarked against behaviorally similar peers, alongside an illustrative demo comparison set.</p>
          </div>
          <motion.button {...tapProps} onClick={() => setShowInfo((value) => !value)} className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-border text-paytm-navy">
            <Info size={16} />
          </motion.button>
        </div>
        <AnimatePresence>
          {showInfo ? (
            <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mt-3 rounded-2xl border border-paytm-cyan bg-bg p-3 text-xs font-bold leading-5 text-paytm-navy">
              Benchmarked against behaviorally similar shops in Paytm Grow's own merchant network - not live web prices.
            </motion.p>
          ) : null}
        </AnimatePresence>
      </Card>
      <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
        <SkuChip active={selectedSku === "all"} label="All items" onClick={() => setSelectedSku("all")} />
        {pricing.slice(0, 10).map((item) => <SkuChip key={item.sku} active={selectedSku === item.sku} label={item.sku} onClick={() => setSelectedSku(item.sku)} />)}
      </div>
      {!ready ? <PricingSkeleton focused={selectedSku !== "all"} /> : selected ? (
        <FocusedPriceView item={selected} merchant={merchant} accepted={!!accepted[selected.sku]} onAccept={() => acceptAction(selected)} />
      ) : (
        <div className="space-y-3">
          {pricing.length && pricing.every((item) => item.flag === "green") ? (
            <Card className="border-success">
              <div className="flex items-center gap-3 text-success"><Check /> <p className="text-sm font-black">You're competitive on every item this week.</p></div>
            </Card>
          ) : null}
          {pricing.map((item, index) => (
            <Card key={item.sku} className="py-3" delay={index * 0.05}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-black text-text-primary">{item.sku}</p>
                  <p className="mt-1 text-xs text-text-muted">You <AnimatedNumber value={item.your_price} prefix="₹" /> · Network avg <AnimatedNumber value={item.benchmark_price} prefix="₹" /></p>
                </div>
                <span className={`rounded-full border px-3 py-1 text-xs font-black ${item.flag === "red" ? "border-danger text-danger" : "border-success text-success"}`}>{item.flag === "red" ? "Above" : "Good"}</span>
              </div>
              <p className="mt-3 text-xs leading-5 text-text-muted">{accepted[item.sku] ? "Action taken for this SKU." : item.recommendation}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function SkuChip({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <motion.button {...tapProps} onClick={onClick} className={`flex shrink-0 items-center gap-2 rounded-full border px-4 py-2 text-xs font-black ${active ? "border-paytm-cyan bg-paytm-navy text-text-inverse" : "border-border bg-surface text-paytm-navy"}`}>
      <span className="max-w-36 truncate">{label}</span>
    </motion.button>
  );
}

function PricingSkeleton({ focused }: { focused: boolean }) {
  return (
    <Card>
      <div className="flex items-center gap-3">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: "linear" }} className="grid h-11 w-11 place-items-center rounded-full border border-paytm-cyan text-paytm-navy">
          <Tag size={18} />
        </motion.div>
        <div className="flex-1">
          <p className="text-sm font-black text-paytm-navy">{focused ? "Checking nearby shops on Paytm Grow's network..." : "Loading price benchmarks..."}</p>
          <div className="mt-2 flex gap-1">
            {[0, 1, 2].map((dot) => <motion.span key={dot} animate={{ opacity: [0.25, 1, 0.25] }} transition={{ duration: 0.8, repeat: Infinity, delay: dot * 0.15 }} className="h-2 w-2 rounded-full bg-paytm-cyan" />)}
          </div>
        </div>
      </div>
      <SkeletonBlock className="mt-4 h-24" />
    </Card>
  );
}

/** One row in the Market Match comparison list. */
type ComparisonRow = {
  key: string;
  label: string;
  price: number;
  wasPrice?: number;
  /** True only for the two rows computed from real data: your shop and the network average. */
  real: boolean;
  kind: "mine" | "network" | "platform";
  meta: string;
  subtext?: string;
};

function buildComparisonRows(item: PricingInsight, merchant?: Merchant): ComparisonRow[] {
  const peerCount = item.peer_count ?? item.peer_prices?.length ?? 0;
  const rows: ComparisonRow[] = [
    {
      key: "mine",
      label: merchant?.name ?? "Your shop",
      price: item.your_price,
      real: true,
      kind: "mine",
      meta: "Your price",
      subtext: "Live from your own price list"
    },
    {
      key: "network",
      label: "Paytm Grow Network Avg",
      price: item.benchmark_price,
      real: true,
      kind: "network",
      meta: "Computed",
      subtext: peerCount
        ? `Mean of ${peerCount} behaviourally similar ${merchant?.category ?? "shops"} in our network`
        : "Mean across behaviourally similar shops in our network"
    },
    // Illustrative demo pricing, not live data.
    ...(item.demo_platforms ?? []).map((platform) => ({
      key: platform.platform,
      label: platform.platform,
      price: platform.price,
      wasPrice: platform.was_price,
      real: false,
      kind: "platform" as const,
      meta: "Updated recently"
    }))
  ];
  return rows.sort((a, b) => a.price - b.price);
}

function FocusedPriceView({ item, merchant, accepted, onAccept }: { item: PricingInsight; merchant?: Merchant; accepted: boolean; onAccept: () => void }) {
  const rows = buildComparisonRows(item, merchant);
  const hasDemoPlatforms = (item.demo_platforms ?? []).length > 0;
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase text-text-muted">Price comparison</p>
            <h3 className="mt-1 text-xl font-black text-paytm-navy">{item.sku}</h3>
          </div>
          <CategoryChip category={merchant?.category} />
        </div>
        <div className="mt-4 space-y-2">
          {rows.map((row, index) => (
            <motion.div
              key={row.key}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.07, duration: 0.28 }}
              className={`rounded-2xl border p-3 ${row.kind === "network" ? "border-paytm-cyan bg-paytm-cyan/5" : row.kind === "mine" ? "border-paytm-navy/40 bg-bg" : "border-border"}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  {row.kind === "platform" ? (
                    <PlatformBadge name={row.label} />
                  ) : (
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-black text-text-primary">{row.label}</p>
                      <MetaChip tone="live">{row.meta}</MetaChip>
                    </div>
                  )}
                  {row.subtext ? <p className="mt-1.5 text-[11px] leading-4 text-text-muted">{row.subtext}</p> : null}
                  {row.kind === "platform" ? <div className="mt-1.5"><MetaChip>{row.meta}</MetaChip></div> : null}
                </div>
                <div className="shrink-0 text-right">
                  {row.wasPrice ? <p className="text-[11px] font-bold text-text-muted line-through">{rupees(row.wasPrice)}</p> : null}
                  <p className="text-base font-black text-paytm-navy">
                    <AnimatedNumber value={row.price} prefix="₹" />
                  </p>
                  {index === 0 ? (
                    <span className="mt-1 inline-block rounded-full border border-success bg-success/10 px-2 py-0.5 text-[10px] font-black text-success">Best price</span>
                  ) : null}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
        {/* Permanent, always-visible disclosure - deliberately not hidden behind an info icon. */}
        {hasDemoPlatforms ? (
          <p className="mt-4 rounded-2xl border border-border bg-bg p-3 text-[11px] leading-5 text-text-muted">
            ZipKart, SpeedBasket, CityMart Express, and QuickHive are illustrative demo platforms for this prototype. The
            Paytm Grow Network Avg is a real benchmark computed from Paytm Grow's own merchant data using peer similarity.
          </p>
        ) : null}
      </Card>
      <Card className={item.flag === "green" ? "border-success" : "border-warning"}>
        <p className="text-xs font-black uppercase text-text-muted">Recommended action</p>
        <p className="mt-2 text-sm font-black text-text-primary">
          {accepted ? "Action taken for this SKU." : item.flag === "green" ? "You're competitive on this item." : item.recommendation}
        </p>
        <p className="mt-2 text-xs leading-5 text-text-muted">
          {item.flag === "red" && item.comparison_shopped ? `Comparison-shopped item: hold price and offer ${item.suggested_points} Loyalty Points instead.` : item.flag === "red" ? "Less comparison-shopped item: there is room to raise price safely." : "Keep the price steady and monitor peers next week."}
        </p>
        {/* The decision is driven only by the real computed benchmark, never by the illustrative platform prices. */}
        <p className="mt-3 rounded-2xl border border-border bg-bg p-3 text-[11px] leading-5 text-text-muted">
          Based on your {rupees(item.your_price)} against the {rupees(item.benchmark_price)} Paytm Grow Network Avg. The
          illustrative demo platform prices above are not used in this recommendation.
        </p>
        <motion.button {...tapProps} disabled={accepted} onClick={onAccept} className="mt-4 rounded-full bg-paytm-navy px-4 py-2 text-xs font-black text-text-inverse disabled:border disabled:border-border disabled:bg-bg disabled:text-text-muted">
          {accepted ? "Action taken" : "Accept action"}
        </motion.button>
      </Card>
    </div>
  );
}

function MerchantRewardsTab({ summary }: { summary?: MerchantRewardSummary }) {
  return (
    <div className="space-y-4">
      <Card className="wallet-card border-paytm-navy text-text-inverse">
        <p className="text-xs font-bold text-text-inverse/70">Rewards Boost spend</p>
        <h2 className="mt-1 text-2xl font-black text-text-inverse"><AnimatedNumber value={summary?.points_issued_this_month ?? 0} suffix=" points" /></h2>
        <p className="mt-2 text-sm text-text-inverse/70">Issued this month through the local Thompson Sampling offer engine.</p>
      </Card>
      <div className="grid grid-cols-2 gap-3">
        <StatBadge label="Est. cost" value={<AnimatedNumber value={summary?.estimated_cost ?? 0} prefix="₹" />} tone="amber" />
        <StatBadge label="Retained rev." value={<AnimatedNumber value={summary?.estimated_retained_revenue ?? 0} prefix="₹" />} tone="green" />
      </div>
      <InsightCard icon={<Sparkles size={20} />} headline="Simplified estimate" subtext={summary?.assumption ?? "Rewards summary is loading from cache."} />
    </div>
  );
}

function LoanReadinessTab({ loan }: { loan?: LoanReadiness }) {
  const ready = useDelayedReveal(!!loan, `loan-${loan?.merchant_id ?? "none"}`, 420);
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-full border border-paytm-cyan text-paytm-navy"><Banknote size={22} /></div>
          <div>
            <p className="text-xs font-bold text-text-muted">Loan Readiness</p>
            <h2 className="text-2xl font-black text-paytm-navy">{loan?.tier ?? "Loading"}</h2>
          </div>
        </div>
        <div className="mt-5"><ProgressBar value={loan?.progress_to_next_tier ?? 0} label="Progress to next tier" /></div>
      </Card>
      <Card>
        <h3 className="text-base font-black text-text-primary">Coach says</h3>
        <div className="mt-3 space-y-3">
          {!ready ? (
            <>
              <SkeletonBlock className="h-16" />
              <SkeletonBlock className="h-16" />
            </>
          ) : (loan?.coaching ?? []).map((item) => <p key={item} className="rounded-2xl border border-border p-3 text-sm leading-6 text-text-muted">{item}</p>)}
        </div>
      </Card>
    </div>
  );
}

function TransactionList({ transactions, empty, onClick }: { transactions: Transaction[]; empty: string; onClick: (tx: Transaction) => void }) {
  if (!transactions.length) return <Card><p className="text-sm text-text-muted">{empty}</p></Card>;
  return (
    <div className="space-y-2">
      {transactions.slice(0, 12).map((transaction) => (
        <button key={transaction.id} onClick={() => onClick(transaction)} className="flex w-full items-center gap-3 rounded-2xl border border-border bg-surface p-3 text-left shadow-soft">
          <Avatar name={transaction.customer_name} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-black text-text-primary">{transaction.merchant_name}</p>
            <p className="truncate text-xs text-text-muted">{new Date(transaction.timestamp).toLocaleDateString("en-IN")} · {transaction.items[0]?.sku ?? "Payment"}</p>
          </div>
          <p className="text-sm font-black text-paytm-navy">{rupees(transaction.amount)}</p>
        </button>
      ))}
    </div>
  );
}

function SoundboxCopilot({ pulse, pricing, loan }: { pulse?: Pulse; pricing: PricingInsight[]; loan?: LoanReadiness }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [response, setResponse] = useState("Ask for a business update, call list, price check, or loan status.");
  const supported = typeof window !== "undefined" && Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  function speak(message: string) {
    setResponse(message);
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(message));
    }
  }
  function answer(input: string) {
    const lower = input.toLowerCase();
    let message = "I could not match that yet. Try business update, who should I call, am I priced right on milk, or loan readiness.";
    // All spoken responses are read directly from the ML engine's outputs
    // - this component never invents a number, it only phrases existing ones.
    // Intent keywords cover both the plain phrasing a merchant would use and the
    // new module names (Merchant Pulse, Market Match, Loyalty Points).
    if (/how am i doing|business update|merchant pulse|pulse|briefing/.test(lower)) message = pulse?.briefing ?? "Merchant Pulse is still loading.";
    else if (/who should i call|call list|call-list|loyalty points|regulars/.test(lower)) {
      const names = (pulse?.churn_alerts ?? []).slice(0, 2).map((item) => `${item.customer_name}, ${item.days_since_last_visit} days since last visit`);
      message = names.length ? `Call ${names.join(" and ")}.` : "No urgent churn-risk regulars are showing right now.";
    } else if (/priced right|price right|market match|price|rate/.test(lower)) {
      // Match on any whole word of the SKU, so "priced right on milk" finds
      // "Amul milk 1L" and "cricket bat" finds the sports SKU. Whole-word matching
      // keeps "market match" from accidentally matching "Yoga mat".
      const found = pricing.find((item) =>
        item.sku
          .toLowerCase()
          .split(/[^a-z0-9]+/)
          .some((word) => word.length >= 3 && new RegExp(`\\b${word}\\b`).test(lower))
      );
      if (found) {
        message = `${found.sku}: ${found.recommendation} Your price is ${rupees(found.your_price)} vs the Paytm Grow Network Avg of ${rupees(found.benchmark_price)}.`;
      } else if (pricing.length) {
        // No specific item named: summarise the real computed benchmarks instead.
        const above = pricing.filter((item) => item.flag === "red");
        const widest = above.reduce<PricingInsight | undefined>(
          (worst, item) => (!worst || item.your_price - item.benchmark_price > worst.your_price - worst.benchmark_price ? item : worst),
          undefined
        );
        message = above.length
          ? `${above.length} of ${pricing.length} items are above the Paytm Grow Network Avg. The widest gap is ${widest?.sku} at ${rupees(widest?.your_price ?? 0)} against ${rupees(widest?.benchmark_price ?? 0)}.`
          : `All ${pricing.length} items are at or below the Paytm Grow Network Avg. You are competitive this week.`;
      } else {
        message = "Market Match is still loading.";
      }
    } else if (/loan status|loan readiness|loan/.test(lower)) message = loan ? `Loan tier is ${loan.tier}. ${loan.coaching[0] ?? "No coaching needed right now."}` : "Loan readiness is still loading.";
    speak(message);
  }
  function listen() {
    setOpen(true);
    if (!supported) {
      return;
    }
    const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new Recognition();
    recognition.lang = "en-IN";
    recognition.onresult = (event: any) => {
      const spoken = event.results[0][0].transcript;
      setText(spoken);
      answer(spoken);
    };
    recognition.start();
  }
  useEffect(() => {
    const openPanel = () => setOpen(true);
    window.addEventListener("open-soundbox", openPanel);
    return () => window.removeEventListener("open-soundbox", openPanel);
  }, []);
  return (
    <>
      <motion.button {...tapProps} onClick={listen} className="fixed bottom-24 right-4 z-30 grid h-12 w-12 place-items-center rounded-full bg-paytm-cyan text-paytm-navy shadow-soft"><Mic size={22} /></motion.button>
      {open ? (
        <div className="fixed inset-x-4 bottom-40 z-30 mx-auto max-w-[430px] rounded-2xl border border-border bg-surface p-4 shadow-soft">
          <p className="text-xs font-black text-paytm-navy">Soundbox Copilot</p>
          <p className="mt-2 text-sm leading-6 text-text-muted">{response}</p>
          {!supported ? <p className="mt-2 text-xs text-warning">Voice input is not supported here. Typed fallback is active.</p> : null}
          <div className="mt-3 flex gap-2">
            <input value={text} onChange={(event) => setText(event.target.value)} className="min-w-0 flex-1 rounded-full border border-border px-4 py-2 text-sm text-text-primary" placeholder="Ask Soundbox" />
            <motion.button {...tapProps} onClick={() => answer(text)} className="grid h-10 w-10 place-items-center rounded-full bg-paytm-navy text-text-inverse"><Send size={16} /></motion.button>
          </div>
        </div>
      ) : null}
    </>
  );
}

function ordinal(value: number) {
  const suffix = value % 10 === 1 && value % 100 !== 11 ? "st" : value % 10 === 2 && value % 100 !== 12 ? "nd" : value % 10 === 3 && value % 100 !== 13 ? "rd" : "th";
  return `${value}${suffix}`;
}

export default App;

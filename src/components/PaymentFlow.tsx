import { useEffect, useRef, useState } from "react";
import { ArrowLeft, CheckCircle2, ChevronDown, Smartphone } from "lucide-react";
import { api, mutationKey, type Customer, type Merchant, type PaymentResult, rupees } from "../lib/api";
import { paymentIntents } from "../lib/upi";
import { Avatar, Card, CategoryChip, MetaChip } from "./ui";

type Screen = "home" | "scan" | "amount" | "processing" | "success" | "bills" | "recharge" | "tx";
export function AmountEntry({ customer, merchant, setScreen, setPaymentResult }: {
  customer?: Customer; merchant?: Merchant; setScreen: (s: Screen) => void;
  setPaymentResult: (p?: PaymentResult) => void; reload: () => Promise<void>;
}) {
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const key = useRef(mutationKey());
  const numeric = Number(amount || 0);
  const press = (value: string) => {
    const next = value === "del" ? amount.slice(0, -1) : `${amount}${value}`;
    if (/^\d{0,6}(\.\d{0,2})?$/.test(next)) {
      setAmount(next); key.current = mutationKey(); setError("");
    }
  };
  const pay = async () => {
    if (!customer || !merchant || numeric <= 0 || busy) return;
    setBusy(true); setError("");
    try {
      const [whole = "0", cents = ""] = amount.split(".");
      const paise = Number(whole) * 100 + Number(cents.padEnd(2, "0"));
      const result = await api.createPayment(customer.id, merchant.id, paise, key.current);
      setPaymentResult(result); setScreen("success");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to create payment session"); }
    finally { setBusy(false); }
  };
  return <div className="space-y-4">
    <button onClick={() => setScreen("scan")} className="flex items-center gap-2 text-sm font-black text-paytm-navy"><ArrowLeft size={17} /> Back</button>
    <Card className="text-center">
      <div className="mx-auto w-fit"><Avatar name={merchant?.name ?? "Merchant"} /></div>
      <h2 className="mt-3 text-xl font-black text-text-primary">{merchant?.name ?? "Merchant"}</h2>
      <div className="mt-2 flex items-center justify-center gap-2"><CategoryChip category={merchant?.category} /><span className="text-xs text-text-muted">Synthetic recipient</span></div>
      <p className="mt-2 text-sm text-text-muted">Paying as {customer?.name ?? "demo customer"}</p>
      <div className="mt-6 text-4xl font-black text-paytm-navy">₹{numeric.toFixed(2)}</div>
      <p className="mt-2 text-xs font-bold text-text-muted">DEMO_SIMULATED · No real money moves</p>
    </Card>
    <div className="grid grid-cols-3 gap-3">{["1","2","3","4","5","6","7","8","9",".","0","del"].map(k =>
      <button key={k} disabled={busy} onClick={() => press(k)} className="h-14 rounded-2xl border border-border bg-surface text-xl font-black text-text-primary shadow-soft">{k === "del" ? "⌫" : k}</button>)}</div>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    <button disabled={numeric <= 0 || busy} onClick={pay} className="w-full rounded-full bg-paytm-navy py-4 text-sm font-black text-text-inverse disabled:opacity-50">{busy ? "Creating session…" : `Create demo payment ${numeric > 0 ? rupees(numeric) : ""}`}</button>
    <UpiIntentPanel merchant={merchant} amount={numeric} />
  </div>;
}

export function UpiIntentPanel({ merchant, amount }: { merchant?: Merchant; amount: number }) {
  const [open, setOpen] = useState(false);
  if (!merchant) return null;
  const intents = paymentIntents({ payeeVpa: merchant.vpa, payeeName: merchant.name, amount, note: "Lucy synthetic preview only" });
  return <Card className="border-paytm-cyan">
    <div className="flex gap-3"><Smartphone className="text-paytm-navy" /><div>
      <h3 className="text-sm font-black text-text-primary">UPI intent preview</h3>
      <p className="mt-1 text-xs leading-5 text-text-muted">Synthetic recipient. Live payment handoff is disabled. This preview does not verify or settle a payment.</p>
    </div></div>
    <button onClick={() => setOpen(v => !v)} className="mt-3 flex w-full justify-between text-xs font-black text-paytm-navy">View UPI payment link <ChevronDown size={16} /></button>
    {open ? <div className="mt-3 space-y-2">{Object.values(intents).map(link => <p key={link} className="break-all rounded-2xl border border-border bg-bg p-3 font-mono text-[10px] text-paytm-navy">{link}</p>)}</div> : null}
  </Card>;
}

export function PaymentStatusScreen({ result, setResult, reload, goHome }: {
  result?: PaymentResult; setResult: (p?: PaymentResult) => void; reload: () => Promise<void>; goHome: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const keys = useRef({ CONFIRMED: mutationKey(), FAILED: mutationKey(), CANCELLED: mutationKey() });
  useEffect(() => {
    if (!result || result.status !== "PENDING") return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      api.payment(result.id, result.customer_id).then(p => { if (!cancelled) { setResult(p); if (p.status !== result.status) void reload(); } })
        .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : "Status unavailable"); });
    }, 2500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [result?.id, result?.status, result?.customer_id, setResult, reload]);
  if (!result) return <Card>No payment session selected.</Card>;
  const simulate = async (status: "CONFIRMED" | "FAILED" | "CANCELLED") => {
    if (busy) return;
    setBusy(true); setError("");
    try { const p = await api.simulatePayment(result.id, result.customer_id, status, keys.current[status]); setResult(p); await reload(); }
    catch (err) { setError(err instanceof Error ? err.message : "Simulation failed"); }
    finally { setBusy(false); }
  };
  return <div className="space-y-4">
    <Card className={`${result.status === "CONFIRMED" ? "border-success" : "border-paytm-cyan"} text-center`}>
      {result.status === "CONFIRMED" ? <CheckCircle2 className="mx-auto text-success" size={58} /> : <Smartphone className="mx-auto text-paytm-cyan" size={48} />}
      <h2 className="mt-4 text-2xl font-black text-text-primary">{result.status === "CONFIRMED" ? "Demo payment confirmed" : result.status === "PENDING" ? "Payment pending" : `Payment ${result.status.toLowerCase()}`}</h2>
      <p className="mt-2 text-3xl font-black text-paytm-navy">₹{(result.amount_paise / 100).toFixed(2)}</p>
      <p className="mt-3 text-sm text-text-muted">DEMO_SIMULATED · No real Paytm settlement. External verification: false.</p>
      {result.status === "CONFIRMED" ? <p className="mt-2 text-xs text-text-muted">Demo points earned: {Math.floor(result.amount_paise / 1000)}. History and demo allowance updated.</p> : null}
    </Card>
    <Card><p className="text-xs font-bold text-text-muted">Payment session</p><p className="mt-1 break-all text-sm font-black">{result.id}</p>
      <div className="mt-3"><MetaChip>{result.status}</MetaChip></div>
      <p className="mt-3 text-xs text-text-muted">Order: {result.order_id ?? "Standalone demo QR payment"}</p>
    </Card>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    {result.status === "PENDING" ? <Card className="space-y-3">
      <p className="text-xs text-text-muted">Session creation has not moved money. Choose a controlled simulation outcome.</p>
      <button disabled={busy} onClick={() => simulate("CONFIRMED")} className="w-full rounded-full bg-paytm-navy py-4 text-sm font-black text-text-inverse">Simulate confirmation</button>
      <div className="flex gap-3"><button disabled={busy} onClick={() => simulate("FAILED")} className="flex-1 rounded-full border border-border p-3 text-xs font-bold">Simulate failure</button><button disabled={busy} onClick={() => simulate("CANCELLED")} className="flex-1 rounded-full border border-border p-3 text-xs font-bold">Cancel payment</button></div>
    </Card> : null}
    <button onClick={goHome} className="w-full rounded-full bg-paytm-navy py-4 text-sm font-black text-text-inverse">Back to Home</button>
  </div>;
}

export function ProcessingScreen() {
  return <Card className="min-h-72 text-center"><h2 className="mt-6 text-xl font-black">Loading payment status</h2></Card>;
}

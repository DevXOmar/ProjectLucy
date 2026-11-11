import { useEffect, useRef, useState } from "react";
import { api, mutationKey, type Mission, type Order, type PaymentResult, type Role, rupees } from "../lib/api";
import { Card } from "./ui";

export function LucyEntry({ customerId }: { customerId: number }) {
  const [goal, setGoal] = useState("Movie Night: projector, snacks and drinks for ten people within ₹2,500");
  const [mission, setMission] = useState<Mission>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const key = useRef(mutationKey());
  const create = async () => {
    setBusy(true); setError("");
    try { setMission(await api.createMission(customerId, goal, key.current)); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to create mission"); }
    finally { setBusy(false); }
  };
  return <Card className="border-paytm-cyan">
    <details>
    <summary className="cursor-pointer text-base font-black text-paytm-navy">Ask Lucy <span className="text-xs font-bold text-text-muted">· Movie Night foundation</span></summary>
    <p className="mt-1 text-xs text-text-muted">Foundation preview · Records a structured mission. Autonomous planning is the next phase.</p>
    <label className="mt-3 block text-xs font-bold" htmlFor="lucy-goal">Your goal</label>
    <textarea id="lucy-goal" value={goal} onChange={e => { setGoal(e.target.value); key.current = mutationKey(); setMission(undefined); }} className="mt-1 w-full rounded-2xl border border-border bg-bg p-3 text-sm" />
    <p className="mb-3 text-xs text-text-muted">Movie Night template · ₹2,500 cap · projector rental, 10 snack boxes, 10 drinks</p>
    <button disabled={busy || !!mission || goal.length < 3} onClick={create} className="rounded-full bg-paytm-navy px-4 py-3 text-xs font-black text-text-inverse disabled:opacity-50">{busy ? "Recording…" : "Create Movie Night mission"}</button>
    {mission ? <p className="mt-3 break-all text-xs">Mission {mission.id} · {mission.status}</p> : null}
    {error ? <p role="alert" className="mt-3 text-xs text-danger">{error}</p> : null}
    </details>
  </Card>;
}

export function OperationalActivity({ role, id, onPayment }: { role: Role; id: number; onPayment?: (p: PaymentResult) => void }) {
  const [payments, setPayments] = useState<PaymentResult[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    const refresh = () => Promise.all([api.payments(role, id), api.orders(role, id)])
      .then(([p, o]) => { if (!cancelled) { setPayments(p); setOrders(o); setError(""); } })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : "Activity unavailable"); });
    void refresh();
    const timer = window.setInterval(refresh, 4000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [role, id]);
  if (!payments.length && !orders.length && !error) return null;
  return <Card>
    <h2 className="text-sm font-black text-paytm-navy">Lucy commerce activity</h2>
    <p className="mt-1 text-xs text-text-muted">Orders and simulated payments for this demo identity</p>
    {error ? <p role="alert" className="mt-2 text-xs text-danger">{error}</p> : null}
    {!payments.length && !orders.length ? <p className="mt-3 text-xs text-text-muted">No operational activity yet.</p> : null}
    {orders.slice(0, 5).map(o => <p key={o.id} className="mt-3 break-all text-xs">Order {o.id.slice(0, 8)} · {rupees(o.total_paise / 100)} · {o.status}</p>)}
    {payments.slice(0, 5).map(p => <button disabled={!onPayment} onClick={() => onPayment?.(p)} key={p.id} className="mt-3 block w-full rounded-xl border border-border p-2 text-left text-xs">Payment {p.id.slice(0, 8)} · {rupees(p.amount_paise / 100)} · {p.status}<span className="block text-text-muted">DEMO_SIMULATED</span></button>)}
  </Card>;
}

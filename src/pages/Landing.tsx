import { ReactNode, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Banknote, Gift, LineChart, Mic, QrCode, Sparkles, Tag, Users } from "lucide-react";
import { api, DemoStats } from "../lib/api";
import { AIBadge, Wordmark, tapProps } from "../components/ui";

/**
 * Marketing-style landing page in Paytm's visual language: top nav, bold hero with
 * a soft animated colour wash, feature grid, stats strip, footer. All copy is
 * original and describes only what this prototype actually does.
 */

const NAV_LINKS = [
  { href: "#for-merchants", label: "For Merchants" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#about", label: "About" }
];

const FEATURES = [
  {
    name: "Loyalty Points",
    icon: <Sparkles size={20} />,
    text: "Scores every customer-shop relationship with BG/NBD survival modelling, so a merchant can see who is quietly drifting away before they stop coming."
  },
  {
    name: "Market Match",
    icon: <Tag size={20} />,
    text: "Benchmarks each item against behaviourally similar shops in our own merchant network, found with SVD peer embeddings rather than a scraped price feed."
  },
  {
    name: "Merchant Pulse",
    icon: <LineChart size={20} />,
    text: "Forecasts the next 30 days of revenue with Holt-Winters weekly seasonality and calls out the days that break the shop's own pattern."
  },
  {
    name: "Rewards Boost",
    icon: <Gift size={20} />,
    text: "Chooses a points multiplier per customer with Thompson Sampling, instead of handing every customer the same blanket discount."
  },
  {
    name: "Loan Readiness Coach",
    icon: <Banknote size={20} />,
    text: "Turns synthetic historical transactions into a readiness tier, with SHAP-derived coaching on the two factors worth improving next."
  },
  {
    name: "Soundbox Copilot",
    icon: <Mic size={20} />,
    text: "Answers spoken questions like \"how am I doing\" by reading back the numbers the models already computed, with a typed fallback when voice is unavailable."
  }
];

const STEPS = [
  {
    title: "Payments already happen",
    text: "Every QR payment a shop already accepts becomes a row of history: who paid, when, and what was in the basket."
  },
  {
    title: "Models read that history",
    text: "Precomputed survival, forecast, peer-similarity and readiness insights remain available from synthetic shop history."
  },
  {
    title: "The shop gets one next action",
    text: "Each module ends in something a merchant can do today: a regular to call, a price to hold, a tier to reach."
  }
];

const FALLBACK_STATS: DemoStats = {
  merchants: 24,
  customers: 400,
  categories: 6,
  transactions: 14304,
  category_names: ["Chemist", "Clothing Shop", "Distributor", "Kirana", "Salon", "Sports Shop"],
  history_months: 6
};

function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 26 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/** Soft drifting colour washes behind the hero - Paytm's hero sections layer light
 * gradients rather than flat blocks. */
function HeroBackdrop() {
  const blobs = [
    { color: "rgba(0, 186, 242, 0.26)", size: 440, top: "-18%", left: "-12%", drift: { x: [0, 42, 0], y: [0, 28, 0] }, duration: 15 },
    { color: "rgba(0, 46, 110, 0.16)", size: 400, top: "12%", left: "68%", drift: { x: [0, -36, 0], y: [0, 34, 0] }, duration: 18 },
    { color: "rgba(0, 186, 242, 0.16)", size: 300, top: "62%", left: "22%", drift: { x: [0, 30, 0], y: [0, -26, 0] }, duration: 21 }
  ];
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {blobs.map((blob) => (
        <motion.div
          key={`${blob.top}-${blob.left}`}
          className="absolute rounded-full blur-3xl"
          style={{ width: blob.size, height: blob.size, top: blob.top, left: blob.left, background: blob.color }}
          animate={{ ...blob.drift, scale: [1, 1.08, 1] }}
          transition={{ duration: blob.duration, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}
      {/* Soft light pool so the headline stays crisp over the colour wash. */}
      <div
        className="absolute inset-0"
        style={{ background: "radial-gradient(closest-side at 50% 46%, rgba(245, 247, 250, 0.88), rgba(245, 247, 250, 0) 72%)" }}
      />
    </div>
  );
}

/** Floating module icons around the hero copy. */
function FloatingIcons() {
  const icons = [
    { icon: <LineChart size={22} />, className: "left-[4%] top-[16%]", delay: 0 },
    { icon: <Tag size={22} />, className: "right-[6%] top-[10%]", delay: 0.6 },
    { icon: <Gift size={22} />, className: "left-[10%] bottom-[12%]", delay: 1.2 },
    { icon: <Banknote size={22} />, className: "right-[9%] bottom-[18%]", delay: 1.8 },
    { icon: <QrCode size={22} />, className: "right-[20%] top-[46%]", delay: 2.4 }
  ];
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 hidden lg:block">
      {icons.map((item) => (
        <motion.div
          key={item.className}
          className={`absolute grid h-12 w-12 place-items-center rounded-2xl border border-paytm-cyan/50 bg-surface/80 text-paytm-navy shadow-soft backdrop-blur ${item.className}`}
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1, y: [0, -12, 0] }}
          transition={{
            opacity: { duration: 0.5, delay: item.delay * 0.2 },
            scale: { duration: 0.5, delay: item.delay * 0.2 },
            y: { duration: 5.5, repeat: Infinity, ease: "easeInOut", delay: item.delay }
          }}
        >
          {item.icon}
        </motion.div>
      ))}
    </div>
  );
}

function FeatureCard({ name, icon, text, delay }: { name: string; icon: ReactNode; text: string; delay: number }) {
  return (
    <Reveal delay={delay}>
      <motion.div
        whileHover={{ y: -4, boxShadow: "0 18px 38px rgba(0, 46, 110, 0.14)" }}
        transition={{ type: "spring", stiffness: 300, damping: 26 }}
        className="h-full rounded-2xl border border-border bg-surface p-5 shadow-soft"
      >
        <div className="flex items-start gap-3">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-paytm-cyan text-paytm-navy">{icon}</div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-black text-text-primary">{name}</h3>
              <AIBadge />
            </div>
            <p className="mt-2 text-xs leading-5 text-text-muted">{text}</p>
          </div>
        </div>
      </motion.div>
    </Reveal>
  );
}

export default function Landing({ onLaunch }: { onLaunch: () => void }) {
  const [stats, setStats] = useState<DemoStats>(FALLBACK_STATS);

  useEffect(() => {
    // Real counts from the seeded local dataset. If the backend is not up yet the
    // deterministic seed's own numbers are used instead.
    api
      .stats()
      .then(setStats)
      .catch(() => setStats(FALLBACK_STATS));
  }, []);

  const statTiles = [
    { value: `${stats.merchants}`, label: "Demo merchants" },
    { value: `${stats.customers}`, label: "Demo customers" },
    { value: `${stats.categories}`, label: "Shop categories" },
    { value: `${stats.history_months} months`, label: "Seeded history" }
  ];

  return (
    <div className="min-h-screen bg-bg text-text-primary">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5">
          <Wordmark />
          <nav className="hidden items-center gap-7 md:flex">
            {NAV_LINKS.map((link) => (
              <a key={link.href} href={link.href} className="text-sm font-bold text-text-muted transition hover:text-paytm-navy">
                {link.label}
              </a>
            ))}
          </nav>
          <motion.button
            {...tapProps}
            onClick={onLaunch}
            className="rounded-full border border-paytm-navy px-4 py-2 text-xs font-black text-paytm-navy transition hover:bg-paytm-navy hover:text-text-inverse"
          >
            Launch Demo
          </motion.button>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <HeroBackdrop />
        <FloatingIcons />
        <div className="relative mx-auto max-w-3xl px-5 py-20 text-center md:py-28">
          <motion.span
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 rounded-full border border-paytm-cyan bg-surface/80 px-4 py-1.5 text-[11px] font-black uppercase tracking-wide text-paytm-navy backdrop-blur"
          >
            <Sparkles size={13} className="text-paytm-cyan" /> Adaptive commerce orchestration
          </motion.span>
          <motion.h1
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
            className="mt-6 text-4xl font-black leading-tight text-paytm-navy md:text-6xl"
          >
            Every payment is the start of a<span className="text-paytm-cyan"> relationship</span>, not the end of one.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto mt-6 max-w-2xl text-base leading-7 text-text-muted md:text-lg"
          >
            Project Lucy is building an AI teammate for customer and merchant goals, coordinated through CrewOS.
            This foundation connects durable orders, inventory reservations and approval tools with historical merchant
            insights. Autonomous planning across buying, group offers, surplus and rentals comes next.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="mt-9 flex flex-col items-center gap-3"
          >
            <motion.button
              {...tapProps}
              whileHover={{ y: -2, boxShadow: "0 18px 38px rgba(0, 46, 110, 0.28)" }}
              onClick={onLaunch}
              className="rounded-full bg-paytm-navy px-10 py-4 text-sm font-black text-text-inverse shadow-soft"
            >
              Launch Demo
            </motion.button>
            <p className="text-xs font-bold text-text-muted">No sign-in. Opens in Customer view, switch to Merchant any time.</p>
          </motion.div>
        </div>
      </section>

      <section className="border-y border-border bg-surface">
        <div className="mx-auto max-w-6xl px-5 py-10">
          <Reveal>
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
              {statTiles.map((tile) => (
                <div key={tile.label} className="text-center">
                  <p className="text-3xl font-black text-paytm-navy md:text-4xl">{tile.value}</p>
                  <p className="mt-1 text-[11px] font-bold uppercase tracking-wide text-text-muted">{tile.label}</p>
                </div>
              ))}
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <p className="mt-7 text-center text-xs leading-5 text-text-muted">
              These are the real counts in this prototype's own seeded dataset — {stats.transactions.toLocaleString("en-IN")} synthetic
              transactions across {stats.category_names.join(", ")}. They describe our demo data, not Paytm's production scale.
            </p>
          </Reveal>
        </div>
      </section>

      <section id="for-merchants" className="scroll-mt-20">
        <div className="mx-auto max-w-6xl px-5 py-16 md:py-20">
          <Reveal>
            <h2 className="text-center text-2xl font-black text-paytm-navy md:text-4xl">Six modules, one merchant dashboard</h2>
            <p className="mx-auto mt-4 max-w-2xl text-center text-sm leading-6 text-text-muted md:text-base">
              Each module answers one question a shopkeeper actually asks out loud. Nothing here is a static mock: every
              number on the merchant screens is computed locally from the transaction history.
            </p>
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature, index) => (
              <FeatureCard key={feature.name} name={feature.name} icon={feature.icon} text={feature.text} delay={index * 0.06} />
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-20 border-y border-border bg-surface">
        <div className="mx-auto max-w-6xl px-5 py-16 md:py-20">
          <Reveal>
            <h2 className="text-center text-2xl font-black text-paytm-navy md:text-4xl">How it works</h2>
          </Reveal>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <Reveal key={step.title} delay={index * 0.08}>
                <div className="h-full rounded-2xl border border-border bg-bg p-6">
                  <span className="grid h-10 w-10 place-items-center rounded-full bg-paytm-navy text-sm font-black text-text-inverse">
                    {index + 1}
                  </span>
                  <h3 className="mt-4 text-base font-black text-text-primary">{step.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-text-muted">{step.text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section id="about" className="scroll-mt-20">
        <div className="mx-auto max-w-4xl px-5 py-16 md:py-20">
          <Reveal>
            <div className="rounded-2xl border border-paytm-cyan bg-surface p-7 shadow-soft md:p-10">
              <div className="flex items-center gap-3">
                <div className="grid h-11 w-11 place-items-center rounded-full border border-paytm-cyan text-paytm-navy">
                  <Users size={20} />
                </div>
                <h2 className="text-xl font-black text-paytm-navy md:text-2xl">About this prototype</h2>
              </div>
              <p className="mt-5 text-sm leading-7 text-text-muted">
                Project Lucy is an independent hackathon prototype, not an official Paytm product. Lucy is the customer-facing
                lead; CrewOS provides the commerce tools and persisted mission state. Historical ML insights use the preserved
                synthetic snapshot. Operational orders, reservations and payments use SQL storage. All payments are DEMO_SIMULATED;
                synthetic UPI recipients are preview-only and live handoff is disabled.
              </p>
              <p className="mt-4 text-sm leading-7 text-text-muted">
                Where a number is an estimate or a label is synthetic, the app says so on the screen it appears on.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 px-5 py-10 text-center">
          <Wordmark />
          <p className="text-xs font-bold text-text-muted">Built for the Paytm Build for India AI Hackathon.</p>
          <p className="text-[11px] text-text-muted">Prototype running on synthetic demo data.</p>
        </div>
      </footer>
    </div>
  );
}

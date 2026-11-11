import { ReactNode } from "react";
import CountUp from "react-countup";
import { motion } from "framer-motion";
import { Banknote, Bell, Home, LineChart, QrCode, RotateCcw, Store, Tag, Trophy, UserRound } from "lucide-react";
import type { Role } from "../lib/api";

export const tapProps = { whileTap: { scale: 0.97 }, transition: { type: "spring", stiffness: 420, damping: 28 } } as const;

export function Card({ children, className = "", interactive = false, delay = 0 }: { children: ReactNode; className?: string; interactive?: boolean; delay?: number }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, delay }}
      whileHover={interactive ? { y: -3, boxShadow: "0 16px 34px rgba(0, 46, 110, 0.13)" } : undefined}
      className={`rounded-2xl border border-border bg-surface p-4 shadow-soft ${interactive ? "cursor-pointer transition-shadow" : ""} ${className}`}
    >
      {children}
    </motion.section>
  );
}

export function Pill({ children, className = "", onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  return (
    <motion.button {...tapProps} onClick={onClick} className={`rounded-full px-4 py-2 text-xs font-black transition ${className}`}>
      {children}
    </motion.button>
  );
}

export function AnimatedNumber({
  value,
  prefix = "",
  suffix = "",
  decimals = 0,
  className = "",
  duration = 0.85,
  start = 0,
  preserveValue = false
}: {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  className?: string;
  duration?: number;
  start?: number;
  preserveValue?: boolean;
}) {
  return (
    <CountUp
      key={preserveValue ? undefined : `${start}-${value}-${prefix}-${suffix}-${decimals}`}
      start={start}
      end={Number.isFinite(value) ? value : 0}
      duration={duration}
      decimals={decimals}
      separator=","
      prefix={prefix}
      suffix={suffix}
      className={className}
    />
  );
}

export function StatBadge({ label, value, tone = "cyan" }: { label: string; value: ReactNode; tone?: "cyan" | "green" | "amber" | "red" }) {
  const tones = {
    cyan: "border-paytm-cyan text-paytm-navy",
    green: "border-success text-success",
    amber: "border-warning text-paytm-navy",
    red: "border-danger text-danger"
  };
  return (
    <div className={`rounded-2xl border bg-surface px-3 py-2 ${tones[tone]}`}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      <p className="text-sm font-extrabold">{value}</p>
    </div>
  );
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  return (
    <div>
      {label ? <div className="mb-2 text-xs font-bold text-text-muted">{label}</div> : null}
      <div className="h-3 overflow-hidden rounded-full bg-bg">
        <motion.div className="h-full rounded-full bg-paytm-cyan" initial={{ width: 0 }} animate={{ width: `${Math.max(0, Math.min(value, 100))}%` }} transition={{ duration: 0.65 }} />
      </div>
    </div>
  );
}

export function Toggle({ role, onChange }: { role: Role; onChange: (role: Role) => void }) {
  return (
    <div className="grid grid-cols-2 rounded-full border border-border bg-bg p-1 text-[11px] font-extrabold">
      {(["customer", "merchant"] as Role[]).map((item) => (
        <motion.button
          {...tapProps}
          key={item}
          onClick={() => onChange(item)}
          className={`rounded-full px-3 py-2 transition ${role === item ? "bg-paytm-navy text-text-inverse shadow" : "text-text-muted"}`}
        >
          {item === "customer" ? "Customer view" : "Merchant view"}
        </motion.button>
      ))}
    </div>
  );
}

export function Avatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0])
    .join("");
  return <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-paytm-navy text-sm font-black text-text-inverse">{initials}</div>;
}

/** Two-line navy/cyan wordmark used by the app top bar and the landing page. */
export function Wordmark({ size = "md", onClick, title }: { size?: "md" | "lg"; onClick?: () => void; title?: string }) {
  const text = size === "lg" ? "text-2xl" : "text-lg";
  const mark = (
    <div className="text-left">
      <div className={`${text} font-black leading-none text-paytm-navy`}>Project</div>
      <div className={`-mt-0.5 ${text} font-black leading-none text-paytm-cyan`}>Lucy</div>
    </div>
  );
  if (!onClick) return mark;
  return (
    <motion.button {...tapProps} onClick={onClick} title={title} className="shrink-0">
      {mark}
    </motion.button>
  );
}

/**
 * Per-category colour so a category is identifiable at a glance in dropdowns and
 * merchant rows. Inline styles keep the palette in one place without fighting the
 * Tailwind class scanner over dynamic names.
 */
const CATEGORY_COLORS: Record<string, string> = {
  Kirana: "#0E8FBF",
  Chemist: "#1DA466",
  Salon: "#8B5CF6",
  Distributor: "#002E6E",
  "Sports Shop": "#C97A00",
  "Clothing Shop": "#E23744"
};

export function categoryColor(category?: string) {
  return CATEGORY_COLORS[category ?? ""] ?? "#6B7280";
}

export function CategoryChip({ category, className = "" }: { category?: string; className?: string }) {
  if (!category) return null;
  const color = categoryColor(category);
  return (
    <span
      className={`inline-block shrink-0 rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-wide ${className}`}
      style={{ color, backgroundColor: `${color}1A`, border: `1px solid ${color}44` }}
    >
      {category}
    </span>
  );
}

type SelectableMerchant = { id: number; name: string; category: string };

/**
 * Merchant picker grouped by category, so switching the demo merchant can jump
 * from a Kirana to a Sports Shop and show Market Match adapting to that catalogue.
 */
export function MerchantSelect({
  merchants,
  value,
  onChange,
  label = "Demo merchant"
}: {
  merchants: SelectableMerchant[];
  value?: number;
  onChange: (id: number) => void;
  label?: string;
}) {
  const groups = merchants.reduce<Record<string, SelectableMerchant[]>>((acc, merchant) => {
    (acc[merchant.category] ??= []).push(merchant);
    return acc;
  }, {});
  const current = merchants.find((merchant) => merchant.id === value);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <p className="text-[11px] font-bold uppercase tracking-wide text-text-muted">{label}</p>
        <CategoryChip category={current?.category} />
      </div>
      <select
        value={value ?? ""}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full rounded-full border border-border bg-surface px-4 py-3 text-sm font-bold text-text-primary shadow-soft"
      >
        {Object.entries(groups).map(([category, list]) => (
          <optgroup key={category} label={category}>
            {list.map((merchant) => (
              <option key={merchant.id} value={merchant.id}>
                {merchant.name} · {category}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}

export function TopBar({ role, onRoleChange, onReset, onHome }: { role: Role; onRoleChange: (role: Role) => void; onReset: () => void; onHome?: () => void }) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/95 px-4 py-3 backdrop-blur">
      <div className="mx-auto flex max-w-[430px] items-center justify-between gap-3">
        <Wordmark onClick={onHome} title="Back to Project Lucy home" />
        <Toggle role={role} onChange={onRoleChange} />
        <motion.button
          {...tapProps}
          onClick={onReset}
          className="grid h-10 w-10 place-items-center rounded-full border border-border bg-bg text-paytm-navy"
          title="Reset Demo Data"
        >
          <RotateCcw size={17} />
        </motion.button>
      </div>
    </header>
  );
}

export type NavKey = "home" | "pay" | "rewards" | "profile" | "insights" | "pricing" | "loan";

export function BottomNav({ role, active, onChange }: { role: Role; active: NavKey; onChange: (nav: NavKey) => void }) {
  const customerItems = [
    { key: "home" as NavKey, label: "Home", icon: Home },
    { key: "pay" as NavKey, label: "Pay", icon: QrCode },
    { key: "rewards" as NavKey, label: "Rewards", icon: Trophy },
    { key: "profile" as NavKey, label: "Profile", icon: UserRound }
  ];
  const merchantItems = [
    { key: "home" as NavKey, label: "Home", icon: Store },
    { key: "insights" as NavKey, label: "Insights", icon: LineChart },
    { key: "pricing" as NavKey, label: "Pricing", icon: Tag },
    { key: "rewards" as NavKey, label: "Rewards", icon: Trophy },
    { key: "loan" as NavKey, label: "Loan", icon: Banknote }
  ];
  const items = role === "customer" ? customerItems : merchantItems;
  return (
    <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-surface px-4 py-2">
      <div className={`mx-auto grid max-w-[430px] gap-1 ${role === "merchant" ? "grid-cols-5" : "grid-cols-4"}`}>
        {items.map(({ key, label, icon: Icon }) => (
          <motion.button
            {...tapProps}
            key={key}
            onClick={() => onChange(key)}
            className={`flex min-h-14 flex-col items-center justify-center rounded-2xl text-[11px] font-bold ${active === key ? "border border-paytm-cyan bg-surface text-paytm-navy" : "text-text-muted"}`}
          >
            <Icon size={19} />
            <span>{label}</span>
          </motion.button>
        ))}
      </div>
    </nav>
  );
}

export function InsightCard({ icon, headline, subtext }: { icon: ReactNode; headline: string; subtext: string }) {
  return (
    <Card className="flex items-start gap-3">
      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-paytm-cyan bg-surface text-paytm-navy">{icon}</div>
      <div>
        <h3 className="text-sm font-black text-text-primary">{headline}</h3>
        <p className="mt-1 text-xs leading-5 text-text-muted">{subtext}</p>
      </div>
    </Card>
  );
}

export function AIBadge() {
  return (
    <motion.span
      animate={{ boxShadow: ["0 0 0 rgba(0,186,242,0)", "0 0 16px rgba(0,186,242,0.38)", "0 0 0 rgba(0,186,242,0)"] }}
      transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
      className="rounded-full bg-paytm-cyan px-2 py-1 text-[10px] font-black text-paytm-navy"
    >
      AI
    </motion.span>
  );
}

export function SkeletonBlock({ className = "" }: { className?: string }) {
  return <div className={`skeleton-shimmer rounded-2xl bg-border/70 ${className}`} />;
}

/**
 * Brand colours for the fictional demo comparison platforms in Market Match.
 * These are invented brands for this prototype - no real company names or logos.
 */
const DEMO_PLATFORM_COLORS: Record<string, string> = {
  ZipKart: "#EA580C",
  SpeedBasket: "#0E7C4A",
  "CityMart Express": "#6D28D9",
  QuickHive: "#BE185D"
};

/** Colored pill badge for one comparison source row. */
export function PlatformBadge({ name, color }: { name: string; color?: string }) {
  const tone = color ?? DEMO_PLATFORM_COLORS[name] ?? "#002E6E";
  return (
    <span
      className="inline-block max-w-full truncate rounded-full px-2.5 py-1 text-[11px] font-black text-text-inverse"
      style={{ backgroundColor: tone }}
    >
      {name}
    </span>
  );
}

/** Small neutral metadata chip, e.g. a freshness indicator on a price row. */
export function MetaChip({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "live" }) {
  const styles =
    tone === "live"
      ? "border-paytm-cyan bg-paytm-cyan/10 text-paytm-navy"
      : "border-border bg-bg text-text-muted";
  return <span className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold ${styles}`}>{children}</span>;
}

export function ScreenTransition({ children, id }: { children: ReactNode; id: string }) {
  return (
    <motion.div key={id} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.2 }}>
      {children}
    </motion.div>
  );
}

export function LocalTopBar({ name, onProfile, onReset }: { name: string; onProfile: () => void; onReset: () => void }) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <motion.button {...tapProps} onClick={onProfile} className="flex min-w-0 items-center gap-3">
        <Avatar name={name} />
        <div className="min-w-0 text-left">
          <p className="truncate text-sm font-black text-text-primary">{name}</p>
          <p className="text-xs text-text-muted">View profile</p>
        </div>
        <span className="text-text-muted">›</span>
      </motion.button>
      <div className="flex gap-2">
        <motion.button {...tapProps} className="grid h-10 w-10 place-items-center rounded-full border border-border bg-surface text-paytm-navy">
          <Bell size={17} />
        </motion.button>
        <motion.button {...tapProps} onClick={onReset} className="grid h-10 w-10 place-items-center rounded-full border border-border bg-surface text-paytm-navy">
          <RotateCcw size={17} />
        </motion.button>
      </div>
    </div>
  );
}

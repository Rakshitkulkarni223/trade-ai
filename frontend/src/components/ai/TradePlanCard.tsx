import type { Plan } from "../../types";
import { cx, fmtPrice } from "../../lib/format";
import { useWorkspace } from "../../store/useWorkspace";

export default function TradePlanCard({ plan, precision, compact }: { plan: Plan; precision: number; compact?: boolean }) {
  const { setHighlight } = useWorkspace();
  const scenario = plan.status === "conditional";
  const long = plan.direction === "long";
  const Row = ({ label, value, tone, sub, id }: { label: string; value: number; tone?: string; sub?: string; id: string }) => (
    <button onClick={() => setHighlight({ kind: "plan", id })} className="flex w-full items-baseline justify-between gap-3 rounded-md px-1 py-0.5 text-left hover:bg-raised">
      <span className="text-xs text-mute">{label}</span>
      <span className="text-right"><span className={cx("tnum text-sm font-semibold", tone ?? "text-ink")}>{fmtPrice(value, precision)}</span>
        {sub && <span className="ml-2 text-[11px] text-faint">{sub}</span>}</span>
    </button>
  );
  return (
    <div className={cx("rounded-xl border p-3", scenario ? "border-dashed border-warn/40 bg-warn/5" : "border-line bg-raised/60")}>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="label">{scenario ? "Scenario — not triggered" : "Potential setup"}</span>
        <span className={cx("rounded px-1.5 py-0.5 text-[10px] font-bold", long ? "bg-up/15 text-up" : "bg-down/15 text-down")}>{plan.direction.toUpperCase()}</span>
      </div>
      <Row label={`Entry · ${String(plan.assumptions.entry_basis ?? "")}`} value={plan.entry} tone="text-primary" id="entry" />
      <Row label="Invalidation (SL)" value={plan.stop} tone="text-down" id="stop" sub={`${fmtPrice(plan.risk_per_unit, precision)} risk`} />
      {plan.targets.map((t) => <Row key={t.name} label={t.name} value={t.price} tone="text-up" id="targets" sub={`${t.r}R${t.note ? ` · ${t.note}` : ""}`} />)}
      {plan.warnings.map((w, i) => <p key={i} className="mt-1.5 text-[11px] text-warn">⚠ {w}</p>)}
      {!compact && <p className="mt-2 text-[11px] leading-snug text-faint">{plan.disclaimer}</p>}
    </div>
  );
}

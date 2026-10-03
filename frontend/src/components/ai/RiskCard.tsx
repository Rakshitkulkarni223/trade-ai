import { useState } from "react";
import type { Plan } from "../../types";
import { useWorkspace } from "../../store/useWorkspace";
import { fmtPrice } from "../../lib/format";

/** Position sizing with every assumption visible and editable. Nothing is hidden behind a default. */
export default function RiskCard({ plan, currency }: { plan: Plan; currency: string }) {
  const { accountSize, riskPct, setRisk } = useWorkspace();
  const [size, setSize] = useState(String(accountSize));
  const [risk, setRiskText] = useState(String(riskPct));
  const apply = () => { const a = Number(size), r = Number(risk); if (a > 0 && r > 0 && r <= 10) setRisk(a, r); };
  const s = plan.sizing;
  return (
    <div className="rounded-xl border border-line bg-raised/60 p-3">
      <div className="label mb-2">Risk &amp; position size (what-if)</div>
      <div className="mb-2 grid grid-cols-2 gap-2">
        <label className="text-[11px] text-mute">Account size
          <input className="input mt-1 !py-1.5 tnum" inputMode="decimal" value={size} onChange={(e) => setSize(e.target.value)} onBlur={apply} onKeyDown={(e) => e.key === "Enter" && apply()} />
        </label>
        <label className="text-[11px] text-mute">Risk per trade %
          <input className="input mt-1 !py-1.5 tnum" inputMode="decimal" value={risk} onChange={(e) => setRiskText(e.target.value)} onBlur={apply} onKeyDown={(e) => e.key === "Enter" && apply()} />
        </label>
      </div>
      <dl className="space-y-1 text-xs">
        <div className="flex justify-between"><dt className="text-mute">Quantity</dt><dd className="tnum font-medium">{s.quantity || "—"}</dd></div>
        <div className="flex justify-between"><dt className="text-mute">Loss if stopped out</dt><dd className="tnum font-medium text-down">{currency}{fmtPrice(s.risk_amount, 2)}</dd></div>
        <div className="flex justify-between"><dt className="text-mute">Position value</dt><dd className="tnum font-medium">{currency}{fmtPrice(s.position_value, 2)} ({s.position_pct}%)</dd></div>
      </dl>
      {s.note && <p className="mt-1.5 text-[11px] text-warn">⚠ {s.note}</p>}
      <p className="mt-2 text-[11px] text-faint">Max position {String(plan.assumptions.max_position_pct)}% of account. A gap through the stop can lose more than planned.</p>
    </div>
  );
}

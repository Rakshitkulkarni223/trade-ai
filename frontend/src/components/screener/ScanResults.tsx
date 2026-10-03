import { useNavigate } from "react-router-dom";
import type { ScanResponse, ScanResult } from "../../types";
import { cx, fmtPrice, precisionFor } from "../../lib/format";
import { useWorkspace } from "../../store/useWorkspace";
import { ActionBadge } from "../common/ui";

export function ScannerCard({ r }: { r: ScanResult }) {
  const nav = useNavigate();
  const { setSymbol } = useWorkspace();
  const p = precisionFor(r.price);
  return (
    <div className="card rise p-4">
      <div className="flex items-start justify-between gap-3">
        <div><div className="font-semibold">{r.name}</div><div className="text-xs text-faint">{r.symbol} · {r.category}</div></div>
        <div className="text-right"><ActionBadge action={r.action} /><div className="tnum mt-1 text-sm">{r.currency_symbol}{fmtPrice(r.price, p)}</div></div>
      </div>
      <p className="mt-2 text-[13px] leading-snug text-mute">{r.summary}</p>
      {r.checks.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-line pt-3">
          {r.checks.map((c) => (
            <li key={c.rule} className="flex items-start gap-2 text-xs"><span className={c.ok ? "text-up" : "text-down"}>{c.ok ? "✓" : "✗"}</span>
              <span className="text-ink">{c.label}<span className="ml-1.5 text-faint">{c.detail}</span></span></li>
          ))}
        </ul>
      )}
      {r.plan && (
        <div className="tnum mt-3 grid grid-cols-3 gap-2 rounded-xl bg-raised/70 p-2 text-center text-[11px]">
          <div><div className="text-faint">Entry</div><div className="font-medium text-primary">{fmtPrice(r.plan.entry, p)}</div></div>
          <div><div className="text-faint">SL</div><div className="font-medium text-down">{fmtPrice(r.plan.stop, p)}</div></div>
          <div><div className="text-faint">TP1</div><div className="font-medium text-up">{fmtPrice(r.plan.tp1, p)}</div></div>
        </div>
      )}
      {r.action === "WAIT" && r.waiting_for.length > 0 && <p className="mt-3 text-xs text-warn">Waiting for: {r.waiting_for.join("; ").toLowerCase()}</p>}
      <button className="btn-ghost mt-3 w-full !py-1.5" onClick={() => { setSymbol(r.symbol); nav("/chart"); }}>Open chart</button>
    </div>
  );
}

export default function ScanResults({ data }: { data: ScanResponse }) {
  const f = data.funnel;
  const steps: [string, number][] = [["Scanned", f.scanned], ["Liquidity events", f.liquidity_events], ["Structure confirmations", f.structure_confirmations], ["Potential setups", f.potential_setups], ["Matches", f.matched]];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {steps.map(([k, v], i) => (
          <div key={k} className={cx("card p-3", i === steps.length - 1 && "border-ai/40")}><div className="tnum text-xl font-semibold">{v}</div><div className="text-[11px] text-mute">{k}</div></div>
        ))}
      </div>
      {data.results.length === 0 ? (
        <div className="card p-6 text-center text-sm text-mute">Nothing matched these rules right now. That is a valid result: loosening a filter or switching timeframe may help.</div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{data.results.map((r) => <ScannerCard key={r.symbol} r={r} />)}</div>
      )}
      {data.unavailable.length > 0 && (
        <p className="text-xs text-faint">Skipped (no data): {data.unavailable.map((u) => u.symbol).join(", ")}</p>
      )}
    </div>
  );
}

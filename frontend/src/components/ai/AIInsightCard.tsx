import { useState } from "react";
import { trackSetup } from "../../api/ai";
import { useWorkspace } from "../../store/useWorkspace";
import type { Analysis, ChartRef } from "../../types";
import { cx } from "../../lib/format";
import EvidencePanel from "./EvidencePanel";
import RiskCard from "./RiskCard";
import TradePlanCard from "./TradePlanCard";

const VERDICT = {
  LONG: { label: "LONG setup", tone: "text-up border-up/40 bg-up/10", bar: "bg-up" },
  SHORT: { label: "SHORT setup", tone: "text-down border-down/40 bg-down/10", bar: "bg-down" },
  WAIT: { label: "WAIT", tone: "text-warn border-warn/40 bg-warn/10", bar: "bg-warn" },
} as const;

/** The verdict at a glance: status, how many required conditions are met, and what is still missing.
 *  Evidence, the plan and sizing are one tap away under "Details". */
export default function AIInsightCard({ analysis, onExplain, onWhy }: {
  analysis: Analysis; onExplain: () => void; onWhy: (r: ChartRef) => void;
}) {
  const { timeframe, symbol, setHighlight } = useWorkspace();
  const [details, setDetails] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const sig = analysis.signal, v = VERDICT[sig.action];
  const wait = sig.action === "WAIT";
  const done = sig.waiting_for.filter((w) => w.done).length, total = sig.waiting_for.length;

  const track = async () => {
    try { await trackSetup(symbol, timeframe); setMsg("Saved. Follow it on the Paper analysis page."); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't save."); }
  };

  return (
    <section className="rise rounded-2xl border border-ai/30 bg-gradient-to-b from-ai/[0.09] to-panel p-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ai">
          <span className="dot-live h-1.5 w-1.5 rounded-full bg-ai" />AI insight
        </span>
        <span className={cx("rounded-lg border px-2.5 py-1 text-xs font-bold tracking-wide", v.tone)}>{v.label}</span>
      </div>

      <p className="mt-3 text-[15px] font-medium leading-snug text-ink">{wait ? "Not ready yet. " : ""}{sig.summary}</p>

      <div className="mt-3">
        <div className="mb-1.5 flex items-center justify-between text-xs">
          <span className="text-mute">Required conditions</span>
          <span className={cx("tnum font-semibold", done === total ? "text-up" : "text-warn")}>{done} of {total} met</span>
        </div>
        <div className="flex gap-1">
          {sig.waiting_for.map((w, i) => <span key={i} className={cx("h-1.5 flex-1 rounded-full", w.done ? v.bar : "bg-line")} />)}
        </div>
        <ul className="mt-2.5 space-y-1.5">
          {sig.waiting_for.map((w) => (
            <li key={w.label} className="flex items-start gap-2 text-[13px] leading-snug">
              <span className={cx("mt-px w-4 shrink-0 text-center font-bold", w.done ? "text-up" : "text-faint")}>{w.done ? "✓" : "○"}</span>
              <span className={w.done ? "text-mute" : "text-ink"}>{w.label}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-3 rounded-lg bg-bg/50 px-3 py-2 text-xs leading-snug text-mute">
        <span className="font-semibold text-ink">Invalidation: </span>{sig.invalidation}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button className="btn-ai !py-1.5" onClick={onExplain}>Explain this</button>
        <button className="btn-ghost !py-1.5" onClick={track} disabled={wait} title={wait ? "Nothing to track while the status is WAIT" : undefined}>Track on paper</button>
        <button className="ml-auto text-xs font-medium text-mute hover:text-ink" onClick={() => setDetails(!details)} aria-expanded={details}>
          {details ? "Hide details ▴" : "Evidence & plan ▾"}
        </button>
      </div>
      {msg && <p className="mt-2 text-xs text-mute">{msg}</p>}

      {details && (
        <div className="mt-4 space-y-3 border-t border-line pt-4">
          <EvidencePanel evidence={sig.evidence} onWhy={(r) => { setHighlight(r); onWhy(r); }} />
          <TradePlanCard plan={analysis.plan} precision={analysis.precision} compact />
          <RiskCard plan={analysis.plan} currency={analysis.instrument.currency_symbol} />
        </div>
      )}
    </section>
  );
}

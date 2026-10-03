import { useState } from "react";
import { trackSetup } from "../../api/ai";
import { useWorkspace } from "../../store/useWorkspace";
import type { Analysis, ChartRef } from "../../types";
import { ActionBadge } from "../common/ui";
import EvidencePanel from "./EvidencePanel";
import RiskCard from "./RiskCard";
import TradePlanCard from "./TradePlanCard";

export default function AIInsightCard({ analysis, onExplain, onWhy }: {
  analysis: Analysis; onExplain: () => void; onWhy: (r: ChartRef) => void;
}) {
  const { timeframe, symbol, setHighlight } = useWorkspace();
  const [open, setOpen] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const sig = analysis.signal;
  const wait = sig.action === "WAIT";

  const track = async () => {
    try { await trackSetup(symbol, timeframe); setMsg("Saved to Paper Analysis. Open that page to follow how it plays out."); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't save."); }
  };

  return (
    <section className="rise rounded-2xl border border-ai/30 bg-gradient-to-b from-ai/10 to-panel shadow-glow">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-4 pt-3 text-left" aria-expanded={open}>
        <span className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ai">
          <span className="dot-live h-1.5 w-1.5 rounded-full bg-ai" />AI insight
        </span>
        <span className="flex items-center gap-2"><ActionBadge action={sig.action} /><span className="text-faint">{open ? "−" : "+"}</span></span>
      </button>
      <div className="px-4 pb-4 pt-2">
        <p className="text-sm leading-snug text-ink">{sig.summary}</p>
        {open && (
          <div className="mt-3 space-y-3">
            {wait && (
              <div className="rounded-xl border border-warn/30 bg-warn/5 p-3">
                <div className="label mb-1.5 !text-warn">Waiting for</div>
                <ul className="space-y-1">
                  {sig.waiting_for.map((w) => (
                    <li key={w.label} className="flex items-center gap-2 text-[13px]"><span className={w.done ? "text-up" : "text-faint"}>{w.done ? "✓" : "○"}</span>
                      <span className={w.done ? "text-mute line-through decoration-faint" : "text-ink"}>{w.label}</span></li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-mute">{sig.invalidation}</p>
              </div>
            )}
            <EvidencePanel evidence={sig.evidence} onWhy={(r) => { setHighlight(r); onWhy(r); }} compact />
            <TradePlanCard plan={analysis.plan} precision={analysis.precision} compact />
            <RiskCard plan={analysis.plan} currency={analysis.instrument.currency_symbol} />
            {!wait && <p className="text-xs text-mute">{sig.invalidation}</p>}
            <div className="flex flex-wrap gap-2">
              <button className="btn-ai !py-1.5" onClick={onExplain}>Explain</button>
              <button className="btn-ghost !py-1.5" onClick={track} disabled={wait} title={wait ? "Nothing to track while the status is WAIT" : undefined}>Track on paper</button>
            </div>
            {msg && <p className="text-xs text-mute">{msg}</p>}
          </div>
        )}
      </div>
    </section>
  );
}

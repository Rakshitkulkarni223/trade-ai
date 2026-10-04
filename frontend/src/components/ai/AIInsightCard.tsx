import { useState } from "react";
import { trackSetup } from "../../api/ai";
import { useWorkspace } from "../../store/useWorkspace";
import type { Analysis, ChartRef } from "../../types";
import { cx } from "../../lib/format";
import EvidencePanel from "./EvidencePanel";
import RiskCard from "./RiskCard";
import TradePlanCard from "./TradePlanCard";

const VERDICT = {
  LONG: { label: "LONG", tone: "text-up border-up/40 bg-up/10", bar: "bg-up" },
  SHORT: { label: "SHORT", tone: "text-down border-down/40 bg-down/10", bar: "bg-down" },
  WAIT: { label: "WAIT", tone: "text-warn border-warn/40 bg-warn/10", bar: "bg-warn" },
} as const;

/** The verdict in one glance: status, why, and how close it is. Collapses to a slim bar once you start chatting,
 *  so the conversation gets the room; the checklist (with what would satisfy each missing item) is one tap away. */
export default function AIInsightCard({ analysis, onExplain, onWhy, open, onOpenChange }: {
  analysis: Analysis; onExplain: () => void; onWhy: (r: ChartRef) => void; open: boolean; onOpenChange: (open: boolean) => void;
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
    <section className="rise rounded-2xl border border-ai/30 bg-gradient-to-b from-ai/[0.09] to-panel">
      <button onClick={() => onOpenChange(!open)} aria-expanded={open} className="block w-full px-4 pb-3 pt-3 text-left">
        <span className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ai">
            <span className="dot-live h-1.5 w-1.5 rounded-full bg-ai" />AI insight
          </span>
          <span className="flex items-center gap-2">
            <span className={cx("rounded-md border px-2 py-0.5 text-[11px] font-bold tracking-wide", v.tone)}>{v.label}</span>
            <span aria-hidden className="text-xs text-faint">{open ? "▴" : "▾"}</span>
          </span>
        </span>
        <span className={cx("mt-2 block text-[13.5px] font-medium leading-snug text-ink", !open && "line-clamp-2")}>{sig.headline}</span>
        <span className="mt-2.5 flex items-center gap-2">
          <span className="flex flex-1 gap-1">
            {sig.waiting_for.map((w, i) => <span key={i} className={cx("h-1 flex-1 rounded-full", w.done ? v.bar : "bg-line")} />)}
          </span>
          <span className={cx("tnum text-[11px] font-semibold", done === total ? "text-up" : "text-warn")}>{done}/{total}</span>
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-line/60 px-4 pb-4 pt-3">
          {sig.market_read?.length > 0 && (
            <ul className="space-y-1">
              {sig.market_read.map((r, i) => (
                <li key={i} className="flex gap-2 text-[12.5px] leading-snug text-mute"><span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-faint" />{r}</li>
              ))}
            </ul>
          )}

          <ul className="space-y-2">
            {sig.waiting_for.map((w) => (
              <li key={w.label} className="flex items-start gap-2 text-[13px] leading-snug">
                <span className={cx("mt-px w-4 shrink-0 text-center font-bold", w.done ? "text-up" : "text-faint")}>{w.done ? "✓" : "○"}</span>
                <span className="min-w-0">
                  <span className={w.done ? "text-mute" : "text-ink"}>{w.label}</span>
                  {!w.done && w.hint && <span className="mt-0.5 block text-[11.5px] leading-snug text-faint">{w.hint}</span>}
                </span>
              </li>
            ))}
          </ul>

          {!wait && (
            <p className="rounded-lg bg-bg/50 px-3 py-2 text-xs leading-snug text-mute">
              <span className="font-semibold text-ink">Invalidation: </span>{sig.invalidation}
              {sig.state && <span className="mt-1 block text-faint">Triggered {sig.state.age_bars} candle{sig.state.age_bars === 1 ? "" : "s"} ago. Levels are fixed until stopped, completed or expired.</span>}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <button className="btn-ai !py-1.5" onClick={onExplain}>Explain this</button>
            <button className="btn-ghost !py-1.5" onClick={track} disabled={wait} title={wait ? "Nothing to track while the status is WAIT" : undefined}>Track on paper</button>
            <button className="ml-auto text-xs font-medium text-mute hover:text-ink" onClick={() => setDetails(!details)} aria-expanded={details}>
              {details ? "Hide evidence ▴" : "Evidence & plan ▾"}
            </button>
          </div>
          {msg && <p className="text-xs text-mute">{msg}</p>}

          {details && (
            <div className="space-y-3 border-t border-line pt-3">
              <EvidencePanel evidence={sig.evidence} onWhy={(r) => { setHighlight(r); onWhy(r); }} />
              {wait ? (
                <p className="rounded-xl border border-dashed border-warn/40 bg-warn/5 p-3 text-xs leading-relaxed text-mute">
                  <span className="font-semibold text-warn">No entry yet.</span> Entry, stop and targets are shown only once every required condition is met on a
                  closed candle; then they stay fixed until the setup is stopped, completed or expires.
                </p>
              ) : (<>
                <TradePlanCard plan={analysis.plan} precision={analysis.precision} compact />
                <RiskCard plan={analysis.plan} currency={analysis.instrument.currency_symbol} />
              </>)}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

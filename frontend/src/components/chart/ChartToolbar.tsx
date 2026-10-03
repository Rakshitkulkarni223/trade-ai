import { useEffect, useMemo, useRef, useState } from "react";
import { GROUP_COLOR, LAYER_DEFS, type LayerDef, type LayerGroup } from "../../lib/layers";
import { cx, hexA } from "../../lib/format";
import { useWorkspace } from "../../store/useWorkspace";
import { TIMEFRAMES } from "../../types";

/** The picker: searchable list grouped like TradingView's indicator dialog. Clicking a row applies it immediately. */
function Picker({ onClose }: { onClose: () => void }) {
  const { layers, toggleLayer, setAllLayers, resetLayers } = useWorkspace();
  const [q, setQ] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    input.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  const groups = useMemo(() => {
    const t = q.trim().toLowerCase();
    const list = LAYER_DEFS.filter((d) => !t || `${d.label} ${d.desc} ${d.group}`.toLowerCase().includes(t));
    return (["Liquidity", "Overlays", "Indicators"] as LayerGroup[]).map((g) => [g, list.filter((d) => d.group === g)] as const).filter(([, l]) => l.length);
  }, [q]);

  return (
    <div className="flex max-h-[min(70vh,560px)] flex-col">
      <div className="flex items-center justify-between px-4 pb-2 pt-3">
        <h3 className="text-sm font-semibold">Indicators &amp; overlays</h3>
        <button onClick={onClose} className="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-raised hover:text-ink" aria-label="Close">✕</button>
      </div>
      <div className="px-4 pb-2">
        <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="input !py-2" />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {groups.length === 0 && <p className="px-3 py-6 text-center text-sm text-faint">Nothing matches “{q}”.</p>}
        {groups.map(([g, defs]) => (
          <div key={g} className="mb-2">
            <div className="flex items-center justify-between px-2 pb-1 pt-2">
              <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: GROUP_COLOR[g] }}>{g}</span>
              <span className="tnum text-[10px] text-faint">{defs.filter((d) => layers[d.key]).length}/{defs.length}</span>
            </div>
            {defs.map((d) => <Row key={d.key} d={d} on={layers[d.key]} onToggle={() => toggleLayer(d.key)} />)}
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between border-t border-line px-4 py-2.5 text-xs">
        <span className="flex gap-3">
          <button onClick={() => setAllLayers(false)} className="text-mute hover:text-ink">Clear all</button>
          <button onClick={resetLayers} className="text-mute hover:text-ink">Defaults</button>
        </span>
        <button onClick={onClose} className="btn-primary !px-4 !py-1.5">Done</button>
      </div>
    </div>
  );
}

function Row({ d, on, onToggle }: { d: LayerDef; on: boolean; onToggle: () => void }) {
  return (
    <button onClick={onToggle} aria-pressed={on} className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-raised"
      style={on ? { background: hexA(d.color, 0.1) } : undefined}>
      <span className="h-8 w-1 shrink-0 rounded-full" style={{ background: on ? d.color : "rgb(var(--line))" }} />
      <span className="min-w-0 flex-1">
        <span className={cx("block text-[13px]", on ? "font-semibold text-ink" : "text-mute")}>{d.label}</span>
        <span className="block truncate text-[11px] text-faint">{d.desc}</span>
      </span>
      <span aria-hidden className="grid h-5 w-5 shrink-0 place-items-center rounded-full border text-[11px] font-bold"
        style={on ? { background: d.color, borderColor: d.color, color: "#0a0c11" } : { borderColor: "rgb(var(--faint))" }}>{on ? "✓" : ""}</span>
    </button>
  );
}

export default function ChartToolbar() {
  const { timeframe, setTimeframe, layers, toggleLayer } = useWorkspace();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const active = LAYER_DEFS.filter((d) => layers[d.key]);

  useEffect(() => {          // click outside closes the desktop popover
    if (!open) return;
    const h = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1 overflow-x-auto pb-0.5">
        {TIMEFRAMES.map((tf) => (
          <button key={tf} onClick={() => setTimeframe(tf)}
            className={cx("rounded-lg px-3 py-1.5 text-xs font-semibold tnum transition", tf === timeframe ? "bg-primary text-white" : "text-mute hover:bg-raised hover:text-ink")}>{tf}</button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <div ref={box} className="relative shrink-0">
          <button onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="dialog"
            className={cx("flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-semibold transition",
              open ? "border-primary/70 bg-primary/10 text-ink" : "border-line bg-raised text-ink hover:border-faint")}>
            <span aria-hidden className="font-serif text-[15px] font-bold italic leading-none text-primary">ƒx</span>
            Indicators
            <span className="tnum grid h-[18px] min-w-[18px] place-items-center rounded-full bg-primary/20 px-1 text-[10px] text-primary">{active.length}</span>
          </button>

          {open && (<>
            {/* phone: bottom sheet; desktop: popover under the button */}
            <button className="fixed inset-0 z-40 bg-black/60 md:hidden" onClick={() => setOpen(false)} aria-label="Close" />
            <div role="dialog" aria-label="Indicators and overlays"
              className="fixed inset-x-0 bottom-0 z-50 rounded-t-3xl border-t border-line bg-panel pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-2xl
                         md:absolute md:inset-x-auto md:bottom-auto md:left-0 md:top-full md:mt-2 md:w-[400px] md:rounded-2xl md:border md:pb-0">
              <Picker onClose={() => setOpen(false)} />
            </div>
          </>)}
        </div>

        {/* applied layers, horizontally, each removable */}
        <div className="scroll-fade flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto py-0.5 pr-6" aria-label="Active indicators">
          {active.length === 0 && <span className="text-xs text-faint">Nothing added. Open Indicators to add liquidity, overlays and indicators.</span>}
          {active.map((d) => (
            <span key={d.key} className="flex shrink-0 items-center gap-1.5 rounded-full border py-1 pl-2.5 pr-1 text-xs font-medium text-ink"
              style={{ background: hexA(d.color, 0.14), borderColor: hexA(d.color, 0.55) }}>
              <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />
              {d.label}
              <button onClick={() => toggleLayer(d.key)} aria-label={`Remove ${d.label}`}
                className="grid h-4 w-4 place-items-center rounded-full text-[10px] text-mute transition hover:bg-bg/60 hover:text-ink">✕</button>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

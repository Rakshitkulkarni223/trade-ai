import { useState, type ReactNode } from "react";
import { TIMEFRAMES } from "../../types";
import { LAYER_COLOR } from "../../lib/liquidityStyle";
import { useWorkspace, type Layers } from "../../store/useWorkspace";
import { cx } from "../../lib/format";
import { Toggle } from "../common/ui";

function Group({ title, color, keys, layers, children }: { title: string; color: string; keys: (keyof Layers)[]; layers: Layers; children: ReactNode }) {
  const on = keys.filter((k) => layers[k]).length;
  return (
    <div className="rounded-xl border border-line bg-panel/60 p-2.5" style={{ borderTop: `2px solid ${color}` }}>
      <div className="mb-2 flex items-center justify-between px-0.5">
        <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color }}>{title}</span>
        <span className="tnum text-[10px] text-faint">{on}/{keys.length} on</span>
      </div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

export default function ChartToolbar() {
  const { timeframe, setTimeframe, layers, toggleLayer } = useWorkspace();
  const [showLayers, setShowLayers] = useState(false);
  const T = (k: keyof Layers, label: string, color: string) => <Toggle key={k} on={layers[k]} onChange={() => toggleLayer(k)} label={label} color={color} />;
  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        <button onClick={() => setShowLayers(!showLayers)} aria-expanded={showLayers}
          className="mr-1 shrink-0 rounded-lg border border-line px-2.5 py-1.5 text-xs font-semibold text-mute md:hidden">Layers {showLayers ? "−" : "+"}</button>
        {TIMEFRAMES.map((tf) => (
          <button key={tf} onClick={() => setTimeframe(tf)}
            className={cx("rounded-lg px-3 py-1.5 text-xs font-semibold tnum transition",
              tf === timeframe ? "bg-primary text-white" : "text-mute hover:bg-raised hover:text-ink")}>
            {tf}
          </button>
        ))}
      </div>
      <div className={cx("gap-2.5 md:grid md:grid-cols-3", showLayers ? "grid" : "hidden")}>
        <Group title="Liquidity" color="#38bdf8" keys={["prevDay", "prevWeek", "swing", "equal"]} layers={layers}>
          {T("prevDay", "Prev day", LAYER_COLOR.prevDay)}{T("prevWeek", "Prev week", LAYER_COLOR.prevWeek)}
          {T("swing", "Swing", LAYER_COLOR.swing)}{T("equal", "Equal H/L", LAYER_COLOR.equal)}
        </Group>
        <Group title="Overlays" color="#fb923c" keys={["fvg", "structure", "plan"]} layers={layers}>
          {T("fvg", "FVG", "#fb923c")}{T("structure", "BOS / CHoCH", "#a78bfa")}{T("plan", "Entry / SL / TP", "#5b7cff")}
        </Group>
        <Group title="Indicators" color="#26be82" keys={["supertrend", "ema", "vwap", "bb", "volume", "rsi"]} layers={layers}>
          {T("supertrend", "Supertrend", "#26be82")}{T("ema", "EMA", "#f5c451")}{T("vwap", "VWAP", "#e879f9")}
          {T("bb", "Bollinger", "#94a3b8")}{T("volume", "Volume", "#64748b")}{T("rsi", "RSI", "#8b5cf6")}
        </Group>
      </div>
    </div>
  );
}

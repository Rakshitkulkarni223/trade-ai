import { useState } from "react";
import { TIMEFRAMES } from "../../types";
import { useWorkspace } from "../../store/useWorkspace";
import { Toggle } from "../common/ui";
import { cx } from "../../lib/format";

export default function ChartToolbar() {
  const { timeframe, setTimeframe, layers, toggleLayer } = useWorkspace();
  const [showLayers, setShowLayers] = useState(false);
  return (
    <div className="space-y-2">
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
      <div className={cx("flex-wrap items-center gap-x-1 gap-y-1 md:flex", showLayers ? "flex" : "hidden")}>
        <span className="label mr-1">Liquidity</span>
        <Toggle on={layers.prevDay} onChange={() => toggleLayer("prevDay")} label="Prev day" color="#38bdf8" />
        <Toggle on={layers.prevWeek} onChange={() => toggleLayer("prevWeek")} label="Prev week" color="#38bdf8" />
        <Toggle on={layers.swing} onChange={() => toggleLayer("swing")} label="Swing" color="#38bdf8" />
        <Toggle on={layers.equal} onChange={() => toggleLayer("equal")} label="Equal H/L" color="#38bdf8" />
        <span className="label mx-1 ml-3">Overlays</span>
        <Toggle on={layers.fvg} onChange={() => toggleLayer("fvg")} label="FVG" color="#fb923c" />
        <Toggle on={layers.structure} onChange={() => toggleLayer("structure")} label="BOS / CHoCH" color="#a78bfa" />
        <Toggle on={layers.plan} onChange={() => toggleLayer("plan")} label="Entry / SL / TP (when active)" color="#5b7cff" />
        <span className="label mx-1 ml-3">Indicators</span>
        <Toggle on={layers.supertrend} onChange={() => toggleLayer("supertrend")} label="Supertrend" color="#26be82" />
        <Toggle on={layers.ema} onChange={() => toggleLayer("ema")} label="EMA" color="#f5c451" />
        <Toggle on={layers.vwap} onChange={() => toggleLayer("vwap")} label="VWAP" color="#e879f9" />
        <Toggle on={layers.bb} onChange={() => toggleLayer("bb")} label="Bollinger" color="#64748b" />
        <Toggle on={layers.volume} onChange={() => toggleLayer("volume")} label="Volume" color="#64748b" />
        <Toggle on={layers.rsi} onChange={() => toggleLayer("rsi")} label="RSI" color="#8b5cf6" />
      </div>
    </div>
  );
}

import type { Layers } from "../store/useWorkspace";
import { LAYER_COLOR } from "./liquidityStyle";

export type LayerGroup = "Liquidity" | "Overlays" | "Indicators";

export interface LayerDef { key: keyof Layers; label: string; group: LayerGroup; color: string; desc: string }

/** Everything that can be switched on the chart, in one place: the picker, the chips and the swatches all read this. */
export const LAYER_DEFS: LayerDef[] = [
  { key: "prevDay", label: "Previous day", group: "Liquidity", color: LAYER_COLOR.prevDay, desc: "Previous day high & low (PDH / PDL)" },
  { key: "prevWeek", label: "Previous week", group: "Liquidity", color: LAYER_COLOR.prevWeek, desc: "Previous week high & low (PWH / PWL)" },
  { key: "swing", label: "Swing levels", group: "Liquidity", color: LAYER_COLOR.swing, desc: "Swing highs & lows where stops rest (BSL / SSL)" },
  { key: "equal", label: "Equal highs / lows", group: "Liquidity", color: LAYER_COLOR.equal, desc: "Clusters of equal highs & lows (EQH / EQL)" },
  { key: "fvg", label: "Fair value gaps", group: "Overlays", color: "#fb923c", desc: "Three-candle imbalances and whether they are filled" },
  { key: "structure", label: "BOS / CHoCH", group: "Overlays", color: "#a78bfa", desc: "Break of structure and change of character" },
  { key: "plan", label: "Entry / SL / TP", group: "Overlays", color: "#5b7cff", desc: "Levels for a confirmed setup (none while waiting)" },
  { key: "supertrend", label: "Supertrend", group: "Indicators", color: "#26be82", desc: "Trend line with Buy / Sell signals (ATR 10 × 3)" },
  { key: "ema", label: "EMA 20 / 50", group: "Indicators", color: "#f5c451", desc: "Exponential moving averages" },
  { key: "vwap", label: "VWAP", group: "Indicators", color: "#e879f9", desc: "Volume-weighted average price, resets daily" },
  { key: "bb", label: "Bollinger Bands", group: "Indicators", color: "#94a3b8", desc: "20-period bands, 2 standard deviations" },
  { key: "volume", label: "Volume", group: "Indicators", color: "#64748b", desc: "Volume bars under the candles" },
  { key: "rsi", label: "RSI 14", group: "Indicators", color: "#8b5cf6", desc: "Momentum pane below the chart" },
];

export const GROUP_COLOR: Record<LayerGroup, string> = { Liquidity: "#38bdf8", Overlays: "#fb923c", Indicators: "#26be82" };

import type { LiquidityLevel } from "../types";

/** One look per kind of level, shared by the toolbar swatches, the chart lines and the liquidity map, so a colour
 *  or line style means the same thing everywhere. */
export type LevelLayer = "prevDay" | "prevWeek" | "swing" | "equal";

export interface LevelStyle {
  color: string;
  layer: LevelLayer;
  name: string;
  width: number;
  dash: number[];       // [] = solid
  double?: boolean;     // two thin parallel lines: "equal" highs / lows
}

export const LEVEL_STYLE: Record<LiquidityLevel["kind"], LevelStyle> = {
  PDH: { color: "#38bdf8", layer: "prevDay", name: "Prev day high", width: 1.6, dash: [] },
  PDL: { color: "#38bdf8", layer: "prevDay", name: "Prev day low", width: 1.6, dash: [] },
  PWH: { color: "#818cf8", layer: "prevWeek", name: "Prev week high", width: 2.6, dash: [] },
  PWL: { color: "#818cf8", layer: "prevWeek", name: "Prev week low", width: 2.6, dash: [] },
  BSL: { color: "#22d3ee", layer: "swing", name: "Swing high", width: 1.8, dash: [1.5, 5] },
  SSL: { color: "#22d3ee", layer: "swing", name: "Swing low", width: 1.8, dash: [1.5, 5] },
  EQH: { color: "#2dd4bf", layer: "equal", name: "Equal highs", width: 1, dash: [], double: true },
  EQL: { color: "#2dd4bf", layer: "equal", name: "Equal lows", width: 1, dash: [], double: true },
};

/** Swatch colour for a layer toggle in the toolbar. */
export const LAYER_COLOR: Record<LevelLayer, string> = { prevDay: "#38bdf8", prevWeek: "#818cf8", swing: "#22d3ee", equal: "#2dd4bf" };

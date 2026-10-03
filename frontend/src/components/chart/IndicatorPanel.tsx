import type { Analysis } from "../../types";
import { fmtPrice } from "../../lib/format";
import { cx } from "../../lib/format";

export default function IndicatorPanel({ analysis }: { analysis: Analysis }) {
  const i = analysis.indicators, p = analysis.precision;
  const rows: [string, string, string?][] = [
    ["RSI 14", i.rsi === null ? "—" : i.rsi.toFixed(1), i.rsi === null ? undefined : i.rsi > 50 ? "text-up" : "text-down"],
    ["EMA 20", fmtPrice(i.ema20, p), analysis.price > (i.ema20 ?? Infinity) ? "text-up" : "text-down"],
    ["EMA 50", fmtPrice(i.ema50, p), analysis.price > (i.ema50 ?? Infinity) ? "text-up" : "text-down"],
    ["EMA alignment", i.ema_alignment, i.ema_alignment === "bullish" ? "text-up" : i.ema_alignment === "bearish" ? "text-down" : "text-mute"],
    ["ATR", i.atr_pct === null ? "—" : `${i.atr_pct.toFixed(2)}%`],
    ["VWAP", fmtPrice(i.vwap, p)],
    ["Volume", i.volume_ratio === null ? "—" : `${i.volume_ratio.toFixed(2)}× avg`, (i.volume_ratio ?? 0) >= 1.2 ? "text-up" : (i.volume_ratio ?? 0) < 0.8 ? "text-down" : "text-warn"],
    ["MACD hist", i.macd_hist === null ? "—" : i.macd_hist > 0 ? "positive" : "negative", (i.macd_hist ?? 0) > 0 ? "text-up" : "text-down"],
  ];
  return (
    <div className="card p-3">
      <h3 className="mb-2 px-1 text-sm font-semibold">Technical snapshot</h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 px-1">
        {rows.map(([k, v, c]) => (
          <div key={k} className="flex items-baseline justify-between gap-2 border-b border-line/50 pb-1">
            <dt className="text-xs text-mute">{k}</dt><dd className={cx("tnum text-xs font-medium capitalize", c ?? "text-ink")}>{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

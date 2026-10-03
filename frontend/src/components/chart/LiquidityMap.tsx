import { useWorkspace } from "../../store/useWorkspace";
import type { Analysis, LiquidityLevel } from "../../types";
import { cx, fmtPrice } from "../../lib/format";

const NAMES: Record<LiquidityLevel["kind"], string> = {
  PDH: "Prev day high", PDL: "Prev day low", PWH: "Prev week high", PWL: "Prev week low",
  BSL: "Swing high", SSL: "Swing low", EQH: "Equal highs", EQL: "Equal lows",
};

/** A dedicated ladder instead of dozens of chart lines: buy-side above price, sell-side below. */
export default function LiquidityMap({ analysis }: { analysis: Analysis }) {
  const { highlight, setHighlight } = useWorkspace();
  const price = analysis.price, p = analysis.precision;
  const levels = analysis.liquidity.levels.filter((l) => l.status !== "broken");
  const above = levels.filter((l) => l.price >= price).sort((a, b) => b.price - a.price);
  const below = levels.filter((l) => l.price < price).sort((a, b) => b.price - a.price);

  const Row = ({ l }: { l: LiquidityLevel }) => {
    const on = highlight?.kind === "liquidity" && highlight.id === l.id;
    const dist = ((l.price - price) / price) * 100;
    return (
      <button onClick={() => setHighlight(on ? null : { kind: "liquidity", id: l.id })}
        className={cx("group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-raised", on && "bg-raised ring-1 ring-liq/60")}>
        <span className="w-9 shrink-0 rounded bg-liq/10 px-1 py-0.5 text-center text-[10px] font-bold text-liq">{l.kind}</span>
        <span className="min-w-0 flex-1 text-xs leading-tight text-mute group-hover:text-ink">{NAMES[l.kind]}</span>
        {l.status === "swept" && <span className="rounded bg-liq/15 px-1 py-0.5 text-[9px] font-semibold text-liq">SWEPT ✓</span>}
        <span className="tnum w-[4.5rem] shrink-0 text-right text-xs text-ink">{fmtPrice(l.price, p)}</span>
        <span className="tnum w-12 shrink-0 text-right text-[11px] text-faint">{dist > 0 ? "+" : ""}{dist.toFixed(2)}%</span>
      </button>
    );
  };

  return (
    <div className="card p-3">
      <div className="mb-2 flex items-center justify-between px-1">
        <h3 className="text-sm font-semibold">Liquidity map</h3>
        <span className="label">chart shows nearest · click to locate</span>
      </div>
      <div className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wider text-liq/80">Buy-side · above price</div>
      {above.length ? above.map((l) => <Row key={l.id} l={l} />) : <p className="px-2 py-1 text-xs text-faint">No levels above.</p>}
      <div className="my-2 flex items-center gap-2 px-1">
        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
        <span className="tnum rounded-full border border-primary/40 bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">{fmtPrice(price, p)}</span>
        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
      </div>
      <div className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wider text-liq/80">Sell-side · below price</div>
      {below.length ? below.map((l) => <Row key={l.id} l={l} />) : <p className="px-2 py-1 text-xs text-faint">No levels below.</p>}
    </div>
  );
}

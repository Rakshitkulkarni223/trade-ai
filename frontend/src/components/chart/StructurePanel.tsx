import { useWorkspace } from "../../store/useWorkspace";
import type { Analysis, Fvg } from "../../types";
import { cx, fmtPrice } from "../../lib/format";
import { TrendText } from "../common/ui";

export default function StructurePanel({ analysis }: { analysis: Analysis }) {
  const { highlight, setHighlight } = useWorkspace();
  const { structure: s, fvg, precision: p } = analysis;
  const n = analysis.series.t.length;
  const ago = (t: number) => { const i = analysis.series.t.indexOf(t); return i < 0 ? "" : n - 1 - i === 0 ? "latest candle" : `${n - 1 - i} candles ago`; };
  const labels = s.swings.filter((x) => x.label).slice(-6);

  const Ev = ({ e, name }: { e: Analysis["structure"]["last_bos"]; name: string }) => {
    if (!e) return <div className="flex justify-between text-xs"><span className="text-mute">{name}</span><span className="text-faint">none</span></div>;
    const on = highlight?.kind === "structure" && highlight.id === e.id;
    return (
      <button onClick={() => setHighlight(on ? null : { kind: "structure", id: e.id })}
        className={cx("flex w-full items-center justify-between rounded-lg px-2 py-1 text-xs hover:bg-raised", on && "bg-raised ring-1 ring-struct/60")}>
        <span className="text-mute">{name}</span>
        <span><span className={e.direction === "bullish" ? "text-up" : "text-down"}>{e.direction}</span>
          <span className="ml-2 text-faint">{ago(e.t)}</span></span>
      </button>
    );
  };

  const FvgRow = ({ g }: { g: Fvg }) => {
    const on = highlight?.kind === "fvg" && highlight.id === g.id;
    return (
      <button onClick={() => setHighlight(on ? null : { kind: "fvg", id: g.id })}
        className={cx("flex w-full items-center justify-between rounded-lg px-2 py-1 text-xs hover:bg-raised", on && "bg-raised ring-1 ring-fvg/60")}>
        <span className={g.type === "bullish" ? "text-up" : "text-down"}>{g.type === "bullish" ? "Bullish" : "Bearish"} FVG</span>
        <span className="tnum text-ink">{fmtPrice(g.low, p)} – {fmtPrice(g.high, p)}</span>
        <span className={cx("text-[10px] uppercase", g.status === "unmitigated" ? "text-fvg" : "text-faint")}>{g.status.replace("_", " ")}</span>
      </button>
    );
  };

  return (
    <div className="card space-y-3 p-3">
      <div>
        <div className="mb-1 flex items-center justify-between px-1"><h3 className="text-sm font-semibold">Market structure</h3>
          <span className="text-xs">Trend: <TrendText trend={s.trend} /></span></div>
        <Ev e={s.last_bos} name="Last BOS" />
        <Ev e={s.last_choch} name="Last CHoCH" />
        {labels.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1 px-2 pt-1">
            {labels.map((x, i) => (
              <span key={i} className={cx("rounded px-1.5 py-0.5 text-[10px] font-bold", x.label === "HH" || x.label === "HL" ? "bg-up/10 text-up" : "bg-down/10 text-down")}>{x.label}</span>
            ))}
          </div>
        )}
      </div>
      <div>
        <h3 className="mb-1 px-1 text-sm font-semibold">Fair value gaps</h3>
        {fvg.length ? fvg.slice(-4).reverse().map((g) => <FvgRow key={g.id} g={g} />) : <p className="px-2 text-xs text-faint">No open gaps in range.</p>}
      </div>
    </div>
  );
}

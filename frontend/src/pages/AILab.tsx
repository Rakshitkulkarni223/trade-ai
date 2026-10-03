import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { aiScan } from "../api/ai";
import { ErrorState } from "../components/common/ui";
import ScanResults from "../components/screener/ScanResults";
import { TIMEFRAMES, type Timeframe } from "../types";
import { cx } from "../lib/format";

const MARKETS = [["India", "India — stocks"], ["US", "US — stocks"], ["Crypto", "Crypto"], ["Indices", "Indices"], ["Metals", "Metals"], ["All", "Everything"]];
const STRATEGIES: Record<string, Timeframe> = { Swing: "1D", Intraday: "1H", Position: "1W" };
const FILTERS = [["sweep", "Liquidity sweep"], ["structure", "Bullish / bearish structure"], ["volume", "Volume confirmation"], ["fvg", "Fair value gap"], ["rsi", "RSI confirmation"]];

export default function AILab() {
  const [market, setMarket] = useState("India");
  const [strategy, setStrategy] = useState("Swing");
  const [tf, setTf] = useState<Timeframe>("1D");
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [filters, setFilters] = useState<string[]>(["sweep", "structure", "volume"]);
  const scan = useMutation({ mutationFn: () => aiScan({ market, timeframe: tf, filters, direction }) });
  const toggle = (id: string) => setFilters((f) => (f.includes(id) ? f.filter((x) => x !== id) : [...f, id]));

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><span className="text-ai">✦</span> AI Lab</h1>
        <p className="mt-1 text-sm text-mute">Scan a market for setups. Every result lists the checks that produced it, so you can disagree with it.</p>
      </div>
      <div className="card grid gap-5 p-5 md:grid-cols-[1fr_1fr_1.2fr]">
        <div className="space-y-3">
          <label className="block"><span className="label">Market</span>
            <select className="input mt-1" value={market} onChange={(e) => setMarket(e.target.value)}>{MARKETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label className="block"><span className="label">Strategy</span>
            <select className="input mt-1" value={strategy} onChange={(e) => { setStrategy(e.target.value); setTf(STRATEGIES[e.target.value]); }}>{Object.keys(STRATEGIES).map((s) => <option key={s}>{s}</option>)}</select></label>
        </div>
        <div className="space-y-3">
          <label className="block"><span className="label">Timeframe</span>
            <select className="input mt-1" value={tf} onChange={(e) => setTf(e.target.value as Timeframe)}>{TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}</select></label>
          <div><span className="label">Direction</span>
            <div className="mt-1 grid grid-cols-2 gap-1 rounded-xl bg-raised p-1">
              {(["long", "short"] as const).map((d) => (
                <button key={d} onClick={() => setDirection(d)} className={cx("rounded-lg py-1.5 text-sm font-medium capitalize", direction === d ? (d === "long" ? "bg-up/20 text-up" : "bg-down/20 text-down") : "text-mute")}>{d}</button>
              ))}
            </div></div>
        </div>
        <div>
          <span className="label">Find</span>
          <div className="mt-2 space-y-2">
            {FILTERS.map(([id, label]) => (
              <label key={id} className="flex cursor-pointer items-center gap-2.5 text-sm">
                <input type="checkbox" className="h-4 w-4 accent-[rgb(139,92,246)]" checked={filters.includes(id)} onChange={() => toggle(id)} />{label}
              </label>
            ))}
          </div>
        </div>
        <div className="md:col-span-3">
          <button className="btn-ai w-full md:w-auto" onClick={() => scan.mutate()} disabled={scan.isPending}>{scan.isPending ? "Scanning… this fetches live data" : "RUN AI SCAN"}</button>
        </div>
      </div>
      {scan.error && <ErrorState error={scan.error} onRetry={() => scan.mutate()} />}
      {scan.data && <ScanResults data={scan.data} />}
      <p className="text-xs text-faint">Scan results describe current chart conditions. They are not recommendations.</p>
    </div>
  );
}

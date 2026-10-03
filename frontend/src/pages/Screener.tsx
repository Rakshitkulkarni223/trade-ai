import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { screenQuery, screenRules } from "../api/ai";
import { ErrorState } from "../components/common/ui";
import ScanResults from "../components/screener/ScanResults";
import { TIMEFRAMES, type Timeframe } from "../types";

const EXAMPLE = "Find Indian stocks with bullish structure, a recent sell-side liquidity sweep, volume above average, RSI between 50 and 65 and price above EMA 50";

type Form = Record<string, string>;
const num = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? undefined : Number(v));

function toRules(f: Form): Record<string, unknown> {
  const r: Record<string, unknown> = {};
  for (const k of ["trend", "sweep", "bos", "choch", "fvg", "ema_alignment", "action"]) if (f[k]) r[k] = f[k];
  for (const [k, from] of [["rsi_min", "rsiMin"], ["rsi_max", "rsiMax"], ["atr_pct_min", "atrMin"], ["atr_pct_max", "atrMax"],
    ["volume_ratio_min", "vol"], ["vwap_distance_pct_max", "vwap"], ["price_min", "pMin"], ["price_max", "pMax"]] as const) {
    const n = num(f[from] ?? ""); if (n !== undefined) r[k] = n;
  }
  if (f.ema50) r.above_ema50 = f.ema50 === "above";
  return r;
}

function Sel({ label, k, f, set, opts }: { label: string; k: string; f: Form; set: (k: string, v: string) => void; opts: [string, string][] }) {
  return (
    <label className="block"><span className="label">{label}</span>
      <select className="input mt-1" value={f[k] ?? ""} onChange={(e) => set(k, e.target.value)}>
        <option value="">Any</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
  );
}
function Num({ label, k, f, set, ph }: { label: string; k: string; f: Form; set: (k: string, v: string) => void; ph?: string }) {
  return (
    <label className="block"><span className="label">{label}</span>
      <input className="input tnum mt-1" inputMode="decimal" placeholder={ph ?? "Any"} value={f[k] ?? ""} onChange={(e) => set(k, e.target.value)} /></label>
  );
}

export default function Screener() {
  const [market, setMarket] = useState("India");
  const [tf, setTf] = useState<Timeframe>("1D");
  const [query, setQuery] = useState("");
  const [form, setForm] = useState<Form>({});
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const byQuery = useMutation({ mutationFn: () => screenQuery(query, tf) });
  const byForm = useMutation({ mutationFn: () => screenRules(market, tf, toRules(form)) });
  const active = byQuery.isPending || byQuery.isSuccess ? byQuery : byForm;
  const data = byForm.data && (!byQuery.data || byForm.submittedAt > byQuery.submittedAt) ? byForm.data : byQuery.data;
  const parsed = data === byQuery.data ? byQuery.data?.parsed : undefined;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">
      <div><h1 className="text-2xl font-semibold tracking-tight">Screener</h1>
        <p className="mt-1 text-sm text-mute">Filter by structure, liquidity and indicators, or describe what you want in plain English.</p></div>

      <div className="card space-y-3 p-5">
        <span className="label !text-ai">✦ Ask in plain English</span>
        <textarea className="input min-h-[84px]" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={EXAMPLE} />
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-ai" disabled={query.trim().length < 3 || byQuery.isPending} onClick={() => byQuery.mutate()}>{byQuery.isPending ? "Screening…" : "Screen with AI"}</button>
          <button className="chip" onClick={() => setQuery(EXAMPLE)}>Use example</button>
        </div>
        {parsed && (
          <div className="rounded-xl border border-line bg-raised/60 p-3 text-xs">
            <span className="text-mute">Interpreted as {parsed.source === "rules" ? "(pattern matching)" : `(${parsed.source})`}: </span>
            <b className="text-ink">{parsed.market}</b>
            {Object.entries(parsed.rules).map(([k, v]) => <span key={k} className="ml-2 rounded bg-bg px-1.5 py-0.5 text-ink">{k} = {String(v)}</span>)}
          </div>
        )}
      </div>

      <div className="card space-y-4 p-5">
        <span className="label">Filters</span>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block"><span className="label">Market</span>
            <select className="input mt-1" value={market} onChange={(e) => setMarket(e.target.value)}>{["India", "US", "Crypto", "Indices", "Metals", "All"].map((m) => <option key={m}>{m}</option>)}</select></label>
          <label className="block"><span className="label">Timeframe</span>
            <select className="input mt-1" value={tf} onChange={(e) => setTf(e.target.value as Timeframe)}>{TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}</select></label>
          <Sel label="Trend" k="trend" f={form} set={set} opts={[["bullish", "Bullish"], ["bearish", "Bearish"], ["neutral", "Neutral"]]} />
          <Sel label="AI status" k="action" f={form} set={set} opts={[["SETUP", "Any setup"], ["LONG", "Long"], ["SHORT", "Short"], ["WAIT", "Wait"]]} />
          <Sel label="Liquidity sweep" k="sweep" f={form} set={set} opts={[["any", "Any recent sweep"], ["sell_side", "Sell-side swept"], ["buy_side", "Buy-side swept"]]} />
          <Sel label="Recent BOS" k="bos" f={form} set={set} opts={[["bullish", "Bullish"], ["bearish", "Bearish"]]} />
          <Sel label="Recent CHoCH" k="choch" f={form} set={set} opts={[["bullish", "Bullish"], ["bearish", "Bearish"]]} />
          <Sel label="Open FVG" k="fvg" f={form} set={set} opts={[["any", "Any"], ["bullish", "Bullish"], ["bearish", "Bearish"]]} />
          <Num label="RSI min" k="rsiMin" f={form} set={set} /><Num label="RSI max" k="rsiMax" f={form} set={set} />
          <Num label="ATR % min" k="atrMin" f={form} set={set} /><Num label="ATR % max" k="atrMax" f={form} set={set} />
          <Num label="Volume ≥ (× avg)" k="vol" f={form} set={set} ph="e.g. 1.2" /><Num label="Within % of VWAP" k="vwap" f={form} set={set} />
          <Sel label="Price vs EMA 50" k="ema50" f={form} set={set} opts={[["above", "Above"], ["below", "Below"]]} />
          <Sel label="EMA alignment" k="ema_alignment" f={form} set={set} opts={[["bullish", "Bullish"], ["bearish", "Bearish"]]} />
          <Num label="Price min" k="pMin" f={form} set={set} /><Num label="Price max" k="pMax" f={form} set={set} />
        </div>
        <p className="text-xs text-faint">Sector and market-cap filters need fundamentals data that the free providers don't supply, so they aren't offered rather than faked.</p>
        <button className="btn-primary" onClick={() => byForm.mutate()} disabled={byForm.isPending}>{byForm.isPending ? "Screening…" : "Run screener"}</button>
      </div>

      {(byQuery.error || byForm.error) && <ErrorState error={byQuery.error ?? byForm.error} />}
      {active.isPending && <p className="text-sm text-mute">Analyzing instruments with live data…</p>}
      {data && <ScanResults data={data} />}
    </div>
  );
}

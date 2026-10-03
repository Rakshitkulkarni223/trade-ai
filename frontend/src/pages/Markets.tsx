import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchQuotes } from "../api/market";
import { Skeleton } from "../components/common/ui";
import { useUniverse } from "../hooks/useMarketData";
import { cx, fmtPct, fmtPrice, precisionFor, tone } from "../lib/format";
import { useWorkspace } from "../store/useWorkspace";

export default function Markets() {
  const uni = useUniverse();
  const [cat, setCat] = useState("Crypto");
  const nav = useNavigate();
  const setSymbol = useWorkspace((s) => s.setSymbol);
  const list = uni.data?.categories.find((c) => c.id === cat)?.instruments ?? [];
  const quotes = useQuery({ queryKey: ["quotes", cat], enabled: list.length > 0, queryFn: () => fetchQuotes(list.map((i) => i.symbol)), refetchInterval: 30_000 });
  const byS = new Map(quotes.data?.quotes.map((q) => [q.symbol, q]));

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-4 md:p-8">
      <h1 className="text-2xl font-semibold tracking-tight">Markets</h1>
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {uni.data?.categories.map((c) => (
          <button key={c.id} onClick={() => setCat(c.id)} className={cx("shrink-0 rounded-xl px-4 py-2 text-sm font-medium transition", c.id === cat ? "bg-primary text-white" : "bg-raised text-mute hover:text-ink")}>{c.label}</button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {uni.isPending && [0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-20" />)}
        {list.map((i) => {
          const q = byS.get(i.symbol);
          return (
            <button key={i.symbol} onClick={() => { setSymbol(i.symbol); nav("/chart"); }} className="card flex items-center justify-between p-4 text-left transition hover:border-faint">
              <span><span className="block font-medium">{i.name}</span><span className="text-xs text-faint">{i.symbol}</span></span>
              <span className="text-right">
                {q && !q.error ? (<><span className="tnum block text-sm font-semibold">{q.currency_symbol}{fmtPrice(q.price, precisionFor(q.price))}</span><span className={cx("tnum text-xs", tone(q.change_pct))}>{fmtPct(q.change_pct)}</span></>)
                  : <span className="text-xs text-faint">{quotes.isPending ? "…" : "n/a"}</span>}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

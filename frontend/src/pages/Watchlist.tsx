import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { addWatch, fetchWatchlist, removeWatch } from "../api/ai";
import { ActionBadge, ErrorState, Skeleton, TrendText } from "../components/common/ui";
import SymbolSearch from "../components/market/SymbolSearch";
import { cx, fmtPct, fmtPrice, precisionFor, tone } from "../lib/format";
import { useWorkspace } from "../store/useWorkspace";

export default function Watchlist() {
  const { timeframe, setSymbol } = useWorkspace();
  const qc = useQueryClient();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["watchlist", timeframe], queryFn: () => fetchWatchlist(timeframe), refetchInterval: 30_000 });
  const refresh = () => qc.invalidateQueries({ queryKey: ["watchlist"] });
  const add = useMutation({ mutationFn: addWatch, onSuccess: refresh });
  const del = useMutation({ mutationFn: removeWatch, onSuccess: refresh });
  const items = q.data?.items ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-4 md:p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-semibold tracking-tight">Watchlist</h1><p className="text-sm text-mute">AI status is computed on the {timeframe} chart.</p></div>
        <div className="w-full sm:w-72"><SymbolSearch placeholder="Add a symbol…" onPick={(s) => add.mutate(s)} /></div>
      </div>
      {q.error && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead><tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-faint">
            {["Symbol", "Price", "Change", "Trend", "Liquidity", "AI status", ""].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
          </tr></thead>
          <tbody>
            {q.isPending && <tr><td colSpan={7} className="p-4"><Skeleton className="h-10" /></td></tr>}
            {items.map((r) => (
              <tr key={r.symbol} className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-raised/50" onClick={() => { setSymbol(r.symbol); nav("/chart"); }}>
                <td className="px-4 py-3"><div className="font-medium">{r.symbol}</div><div className="text-xs text-faint">{r.name}</div></td>
                <td className="tnum px-4 py-3">{r.price === undefined ? "—" : `${r.currency_symbol}${fmtPrice(r.price, precisionFor(r.price))}`}</td>
                <td className={cx("tnum px-4 py-3", tone(r.change_pct))}>{fmtPct(r.change_pct)}</td>
                <td className="px-4 py-3"><TrendText trend={r.trend} /></td>
                <td className="px-4 py-3 text-xs text-mute">{r.liquidity ?? "—"}</td>
                <td className="px-4 py-3"><ActionBadge action={r.status} /></td>
                <td className="px-4 py-3 text-right"><button className="text-xs text-faint hover:text-down" onClick={(e) => { e.stopPropagation(); del.mutate(r.symbol); }}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {!q.isPending && items.length === 0 && <p className="p-6 text-center text-sm text-mute">Your watchlist is empty. Search above to add instruments.</p>}
      </div>
    </div>
  );
}

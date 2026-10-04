import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
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
  const refresh = () => { qc.invalidateQueries({ queryKey: ["watchlist"] }); qc.invalidateQueries({ queryKey: ["watchlist-symbols"] }); };
  const [note, setNote] = useState<{ kind: "ok" | "info" | "error"; text: string } | null>(null);
  useEffect(() => { if (!note) return; const id = setTimeout(() => setNote(null), 7000); return () => clearTimeout(id); }, [note]);
  const label = (r: { name: string; symbol: string }) => (r.name && r.name !== r.symbol ? `${r.name} (${r.symbol})` : r.symbol);
  const add = useMutation({
    mutationFn: addWatch,
    onSuccess: (r) => {
      refresh();
      setNote(r.added
        ? { kind: "ok", text: `Added ${label(r)}${r.resolved_from ? ` — “${r.resolved_from}” is listed on NSE as ${r.symbol}` : ""}.` }
        : { kind: "info", text: `${label(r)} is already in your watchlist.` });
    },
    onError: (e) => setNote({ kind: "error", text: e instanceof Error ? e.message : "Couldn't add that symbol." }),
  });
  const del = useMutation({ mutationFn: removeWatch, onSuccess: refresh });
  const items = q.data?.items ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-4 md:p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-semibold tracking-tight">Watchlist</h1><p className="text-sm text-mute">AI status is computed on the {timeframe} chart.</p></div>
        <div className="w-full sm:w-72"><SymbolSearch placeholder="Add a symbol…" onPick={(s) => add.mutate(s)} /></div>
      </div>
      {add.isPending && <p role="status" className="text-sm text-mute">Checking {add.variables}…</p>}
      {note && (
        <p role={note.kind === "error" ? "alert" : "status"}
          className={cx("rounded-xl border px-3 py-2 text-sm", note.kind === "ok" && "border-up/40 bg-up/10 text-up", note.kind === "info" && "border-line bg-raised text-mute", note.kind === "error" && "border-down/40 bg-down/10 text-down")}>
          {note.text}
        </p>
      )}
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
                <td className="px-4 py-3">
                  <div className="font-medium">{r.symbol}</div>{r.name !== r.symbol && <div className="text-xs text-faint">{r.name}</div>}
                  {r.error && <div className="mt-0.5 max-w-[260px] text-[11px] leading-snug text-down">{r.error} Remove it, or add the exchange suffix (e.g. .NS).</div>}
                </td>
                <td className="tnum px-4 py-3">
                  {r.price === undefined ? "—" : `${r.currency_symbol}${fmtPrice(r.price, precisionFor(r.price))}`}
                  {r.market_open === false && <span className="ml-1.5 rounded bg-raised px-1 py-px text-[10px] font-medium text-faint" title="Market closed: showing the last session">closed</span>}
                </td>
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

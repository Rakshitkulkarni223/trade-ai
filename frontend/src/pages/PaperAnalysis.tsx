import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { deleteSetup, fetchSetups } from "../api/ai";
import { ErrorState, Skeleton } from "../components/common/ui";
import type { TrackedSetup } from "../types";
import { cx, fmtPrice, precisionFor, timeAgo } from "../lib/format";
import { useWorkspace } from "../store/useWorkspace";

const STATE: Record<string, [string, string]> = {
  open: ["Open", "text-primary"], stopped: ["Stopped out", "text-down"], target_1: ["Target 1 hit", "text-up"],
  target_2: ["Target 2 hit", "text-up"], target_3: ["Target 3 hit", "text-up"],
  target_1_open: ["TP1 reached, still open", "text-up"], target_2_open: ["TP2 reached, still open", "text-up"], unknown: ["Unknown", "text-faint"],
};

function Row({ s, onDelete, onOpen }: { s: TrackedSetup; onDelete: () => void; onOpen: () => void }) {
  const [label, tone] = STATE[s.result.state] ?? [s.result.state, "text-mute"];
  const p = precisionFor(s.entry);
  const r = s.result.realised_r ?? (s.result.closed ? null : s.result.open_r);
  return (
    <div className="card rise p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button onClick={onOpen} className="text-left"><span className="font-semibold">{s.symbol}</span><span className="ml-2 text-xs text-faint">{s.timeframe} · saved {timeAgo(s.created_at)}</span></button>
        <div className="flex items-center gap-3">
          <span className={cx("rounded px-1.5 py-0.5 text-[10px] font-bold", s.direction === "long" ? "bg-up/15 text-up" : "bg-down/15 text-down")}>{s.direction.toUpperCase()}</span>
          <span className={cx("text-sm font-medium", tone)}>{label}</span>
          {r !== null && r !== undefined && <span className={cx("tnum text-sm font-semibold", r >= 0 ? "text-up" : "text-down")}>{r > 0 ? "+" : ""}{r}R{s.result.closed ? "" : " (open)"}</span>}
        </div>
      </div>
      <div className="tnum mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
        <div><div className="text-faint">Entry</div><div className="text-primary">{fmtPrice(s.entry, p)}</div></div>
        <div><div className="text-faint">Stop</div><div className="text-down">{fmtPrice(s.stop, p)}</div></div>
        {s.targets.map((t) => <div key={t.name}><div className="text-faint">{t.name} ({t.r}R)</div><div className="text-up">{fmtPrice(t.price, p)}</div></div>)}
      </div>
      {s.evidence && <p className="mt-3 text-xs text-mute">{s.evidence.summary}</p>}
      {s.note && <p className="mt-1 text-xs italic text-faint">“{s.note}”</p>}
      <div className="mt-3 flex justify-end"><button className="text-xs text-faint hover:text-down" onClick={onDelete}>Remove</button></div>
    </div>
  );
}

export default function PaperAnalysis() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const setSymbol = useWorkspace((s) => s.setSymbol);
  const q = useQuery({ queryKey: ["setups"], queryFn: fetchSetups, refetchInterval: 60_000 });
  const del = useMutation({ mutationFn: deleteSetup, onSuccess: () => qc.invalidateQueries({ queryKey: ["setups"] }) });
  const sum = q.data?.summary;

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-4 md:p-8">
      <div><h1 className="text-2xl font-semibold tracking-tight">Paper analysis</h1>
        <p className="mt-1 text-sm text-mute">Follow AI setups on paper and see what later candles did to them. No orders exist anywhere in this app.</p></div>
      {sum && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[["Tracked", sum.total], ["Open", sum.open], ["Closed", sum.closed], ["Net R (closed)", `${sum.net_r > 0 ? "+" : ""}${sum.net_r}R`]].map(([k, v]) => (
            <div key={String(k)} className="card p-3"><div className="tnum text-xl font-semibold">{v}</div><div className="text-[11px] text-mute">{k}</div></div>
          ))}
        </div>
      )}
      {q.error && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isPending && <Skeleton className="h-32" />}
      <div className="space-y-3">
        {q.data?.setups.map((s) => <Row key={s.id} s={s} onDelete={() => del.mutate(s.id)} onOpen={() => { setSymbol(s.symbol); nav("/chart"); }} />)}
      </div>
      {q.data && q.data.setups.length === 0 && (
        <div className="card p-8 text-center text-sm text-mute">Nothing tracked yet. When the copilot shows an active LONG or SHORT setup, press <b className="text-ink">Track on paper</b>.</div>
      )}
      {sum && <p className="text-xs text-faint">{sum.note} A handful of results says very little about a method; judge it over many.</p>}
    </div>
  );
}

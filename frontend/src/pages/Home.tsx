import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { fetchWatchlist } from "../api/ai";
import { ActionBadge, SectionTitle, Skeleton, TrendText } from "../components/common/ui";
import SymbolSearch from "../components/market/SymbolSearch";
import { usePulse } from "../hooks/useMarketData";
import { cx, fmtPct, fmtPrice, precisionFor, tone } from "../lib/format";
import { useWorkspace } from "../store/useWorkspace";

const greeting = () => { const h = new Date().getHours(); return h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; };

export default function Home() {
  const nav = useNavigate();
  const { setSymbol, timeframe } = useWorkspace();
  const pulse = usePulse();
  const watch = useQuery({ queryKey: ["watchlist", timeframe], queryFn: () => fetchWatchlist(timeframe), refetchInterval: 60_000 });
  const open = (s: string) => { setSymbol(s); nav("/chart"); };
  const items = watch.data?.items ?? [];
  const discoveries = [...items].filter((i) => i.status).sort((a, b) => Number(b.status !== "WAIT") - Number(a.status !== "WAIT")).slice(0, 4);

  return (
    <div className="mx-auto max-w-5xl space-y-10 p-4 md:p-8">
      <section className="pt-4 text-center md:pt-10">
        <p className="text-sm text-mute">{greeting()}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight md:text-4xl">What are you analyzing?</h1>
        <div className="mx-auto mt-6 max-w-2xl"><SymbolSearch large autoFocus placeholder="Search a stock, crypto or index…" /></div>
        <p className="mt-3 text-xs text-faint">Charts, liquidity, structure and an AI copilot that shows its evidence. Analysis only, no orders.</p>
      </section>

      <section>
        <SectionTitle>Market pulse</SectionTitle>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {pulse.isPending && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}
          {pulse.data?.quotes.map((q) => (
            <button key={q.symbol} onClick={() => open(q.symbol)} className="card p-4 text-left transition hover:border-faint">
              <div className="text-xs text-mute">{q.name ?? q.symbol}</div>
              {q.error ? <div className="mt-2 text-xs text-faint">unavailable</div> : (<>
                <div className="tnum mt-1 text-lg font-semibold">{q.currency_symbol}{fmtPrice(q.price, precisionFor(q.price))}</div>
                <div className={cx("tnum text-sm", tone(q.change_pct))}>{fmtPct(q.change_pct)}</div>
              </>)}
            </button>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle aside={<Link to="/lab" className="text-xs text-ai hover:underline">Run an AI scan →</Link>}>AI discoveries</SectionTitle>
        <div className="grid gap-3 md:grid-cols-2">
          {watch.isPending && [0, 1].map((i) => <Skeleton key={i} className="h-28" />)}
          {discoveries.map((d) => (
            <button key={d.symbol} onClick={() => open(d.symbol)} className="card p-4 text-left transition hover:border-ai/50">
              <div className="flex items-center justify-between"><span className="font-semibold">{d.name}</span><ActionBadge action={d.status} /></div>
              <p className="mt-2 line-clamp-2 text-sm text-mute">{d.summary}</p>
              <div className="mt-2 text-xs text-faint"><TrendText trend={d.trend} /> · {d.liquidity}</div>
            </button>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle aside={<Link to="/watchlist" className="text-xs text-ai hover:underline">Manage →</Link>}>Watchlist</SectionTitle>
        <div className="card divide-y divide-line">
          {items.map((r) => (
            <button key={r.symbol} onClick={() => open(r.symbol)} className="grid w-full grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-4 px-4 py-3 text-left hover:bg-raised/50 sm:grid-cols-[minmax(0,1fr)_120px_80px_70px]">
              <span className="min-w-0"><span className="font-medium">{r.symbol}</span><span className="ml-2 hidden text-xs text-faint sm:inline">{r.name}</span></span>
              <span className="tnum hidden text-right text-sm sm:block">{r.price === undefined ? "—" : `${r.currency_symbol}${fmtPrice(r.price, precisionFor(r.price))}`}</span>
              <span className={cx("tnum text-right text-sm", tone(r.change_pct))}>{fmtPct(r.change_pct)}</span>
              <span className="text-right"><ActionBadge action={r.status} /></span>
            </button>
          ))}
          {watch.isPending && <div className="p-4"><Skeleton className="h-10" /></div>}
        </div>
      </section>
    </div>
  );
}

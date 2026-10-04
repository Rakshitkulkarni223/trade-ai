import { useWatchToggle } from "../../hooks/useWatchlist";
import { liveKey } from "../../hooks/useLiveFeed";
import { useWorkspace } from "../../store/useWorkspace";
import type { Analysis } from "../../types";
import { cx, fmtPct, fmtPrice, tone } from "../../lib/format";
import { ActionBadge } from "../common/ui";

export default function MarketHeader({ analysis, symbol }: { analysis?: Analysis; symbol: string }) {
  const watch = useWatchToggle(symbol);
  const { live, timeframe } = useWorkspace();
  const q = analysis?.quote, inst = analysis?.instrument;
  const isLive = live.key === liveKey(symbol, timeframe);
  const price = (isLive && live.price !== null ? live.price : undefined) ?? q?.price ?? analysis?.price;
  const p = analysis?.precision ?? 2;
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight md:text-2xl">{inst?.name ?? symbol}</h1>
          <span className="rounded-md bg-raised px-1.5 py-0.5 text-[11px] text-mute">{symbol}</span>
          {inst && <span className="hidden text-[11px] text-faint sm:inline">{inst.category}</span>}
          {inst && (
            <span className="rounded-md border border-line px-1.5 py-0.5 text-[10px] text-mute"
              title="Prices differ slightly between exchanges and between USD and USDT pairs, so this can differ from other sites by a few dollars.">
              {inst.provider === "binance" ? `Price: Binance ${symbol}` : "Price: Yahoo Finance"}
            </span>
          )}
        </div>
        <div className="mt-1 flex items-baseline gap-3">
          <span className="tnum text-3xl font-semibold tracking-tight">{price === undefined ? "—" : `${inst?.currency_symbol ?? ""}${fmtPrice(price, p)}`}</span>
          {q && <span className={cx("tnum text-sm font-medium", tone(q.change_pct))}>{fmtPct(q.change_pct)} <span className="text-faint">24h</span></span>}
          <LivePill state={analysis?.data_status?.market_open === false ? "closed" : isLive ? live.state : "connecting"} opensAt={analysis?.data_status?.opens_at} />
        </div>
      </div>
      <div className="flex flex-col items-end gap-1">
       <div className="flex items-center gap-2">
        {analysis && <ActionBadge action={analysis.signal.action} className="!px-3 !py-1 !text-xs" />}
        <button onClick={watch.toggle} disabled={!watch.ready || watch.pending} aria-pressed={watch.watching}
          title={watch.watching ? "In your watchlist. Click to remove." : "Add to your watchlist"}
          className={cx("btn-ghost !py-1.5", watch.watching && "!border-warn/50 !bg-warn/10 !text-warn")}>
          <span aria-hidden>{watch.watching ? "★" : "☆"}</span>{watch.pending ? "Saving…" : watch.watching ? "Watching" : "Watch"}
        </button>
       </div>
       {watch.error && <p role="alert" className="max-w-[260px] text-right text-[11px] leading-snug text-down">{watch.error}</p>}
      </div>
    </div>
  );
}

const PILL: Record<string, [string, string, string]> = {
  live: ["LIVE", "text-up border-up/40 bg-up/10", "bg-up dot-live"],
  polling: ["LIVE · 5s", "text-warn border-warn/40 bg-warn/10", "bg-warn dot-live"],
  closed: ["Market closed", "text-mute border-line bg-raised", "bg-faint"],
  connecting: ["Connecting…", "text-mute border-line bg-raised", "bg-faint"],
  offline: ["Reconnecting…", "text-mute border-line bg-raised", "bg-faint"],
};

/** LIVE = streaming candle (crypto). LIVE · 5s = price polled every 5 s (stocks, indices, metals). */
function LivePill({ state, opensAt }: { state: string; opensAt?: number | null }) {
  const [label, tone, dot] = PILL[state] ?? PILL.connecting;
  return (
    <span className={cx("inline-flex items-center gap-1.5 self-center rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wide", tone)}
      title={state === "polling" ? "No free stream exists for this market, so the price refreshes every 5 seconds."
        : state === "closed" ? `Nothing is being fetched while the market is closed.${opensAt ? ` Opens ${new Date(opensAt * 1000).toLocaleString()}.` : ""}` : undefined}>
      <span className={cx("h-1.5 w-1.5 rounded-full", dot)} />{label}
    </span>
  );
}

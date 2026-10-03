import { useMutation, useQueryClient } from "@tanstack/react-query";
import { addWatch } from "../../api/ai";
import type { Analysis } from "../../types";
import { cx, fmtPct, fmtPrice, tone } from "../../lib/format";
import { ActionBadge } from "../common/ui";

export default function MarketHeader({ analysis, symbol }: { analysis?: Analysis; symbol: string }) {
  const qc = useQueryClient();
  const add = useMutation({ mutationFn: () => addWatch(symbol), onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }) });
  const q = analysis?.quote, inst = analysis?.instrument;
  const price = q?.price ?? analysis?.price;
  const p = analysis?.precision ?? 2;
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight md:text-2xl">{inst?.name ?? symbol}</h1>
          <span className="rounded-md bg-raised px-1.5 py-0.5 text-[11px] text-mute">{symbol}</span>
          {inst && <span className="hidden text-[11px] text-faint sm:inline">{inst.category}</span>}
        </div>
        <div className="mt-1 flex items-baseline gap-3">
          <span className="tnum text-3xl font-semibold tracking-tight">{price === undefined ? "—" : `${inst?.currency_symbol ?? ""}${fmtPrice(price, p)}`}</span>
          {q && <span className={cx("tnum text-sm font-medium", tone(q.change_pct))}>{fmtPct(q.change_pct)} <span className="text-faint">24h</span></span>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {analysis && <ActionBadge action={analysis.signal.action} className="!px-3 !py-1 !text-xs" />}
        <button className="btn-ghost !py-1.5" onClick={() => add.mutate()} disabled={add.isPending || add.isSuccess}>
          {add.isSuccess ? "★ In watchlist" : "☆ Watch"}
        </button>
      </div>
    </div>
  );
}

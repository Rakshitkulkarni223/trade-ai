import { useQuery } from "@tanstack/react-query";
import { aiStatus } from "../../api/ai";
import { useAI } from "../../hooks/useAI";
import { useAnalysisData } from "../../hooks/useMarketData";
import { useWorkspace } from "../../store/useWorkspace";
import { DataStatusBanner, ErrorState, Skeleton } from "../common/ui";
import AIChat from "./AIChat";
import AIInsightCard from "./AIInsightCard";

/** The copilot: insight card on top, conversation below. Rendered as a side panel, a drawer or a bottom sheet. */
export default function AICopilot({ onClose }: { onClose?: () => void }) {
  const { symbol, timeframe, accountSize, riskPct, setHighlight } = useWorkspace();
  const { data, error, isPending, refetch } = useAnalysisData(symbol, timeframe, accountSize, riskPct);
  const status = useQuery({ queryKey: ["ai-status"], queryFn: aiStatus, staleTime: 60_000 });
  const { send, why } = useAI();

  const header = (
    <>
      {isPending && <Skeleton className="h-56" />}
      {error && !data && <ErrorState error={error} onRetry={() => refetch()} />}
      {data && (<>
        <DataStatusBanner status={data.data_status} />
        <AIInsightCard analysis={data} onExplain={() => send("", "analyze")} onWhy={(r) => { setHighlight(r); why(r); }} />
      </>)}
    </>
  );

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><span className="grid h-6 w-6 place-items-center rounded-lg bg-ai text-[11px] font-bold text-white">AI</span>Market Copilot</h2>
          <p className="mt-0.5 truncate text-[11px] text-faint">{symbol} · {timeframe} · {status.data?.llm ? `${status.data.provider} model` : "offline explainer"}</p>
        </div>
        {onClose && <button onClick={onClose} className="btn-ghost !px-2.5 !py-1.5" aria-label="Close copilot">✕</button>}
      </div>
      <AIChat className="min-h-0 flex-1" header={header} />
    </div>
  );
}

import { useState } from "react";
import { Link } from "react-router-dom";
import AIChat from "../components/ai/AIChat";
import AIInsightCard from "../components/ai/AIInsightCard";
import ChatActions from "../components/ai/ChatActions";
import ChatHistory from "../components/ai/ChatHistory";
import { DataStatusBanner, ErrorState, Skeleton } from "../components/common/ui";
import { useAI } from "../hooks/useAI";
import { useAnalysisData } from "../hooks/useMarketData";
import { TIMEFRAMES } from "../types";
import { cx } from "../lib/format";
import { useWorkspace } from "../store/useWorkspace";

/** AI Workspace: same symbol, timeframe and conversation as the chart, with the chat given the whole page. */
export default function AIWorkspace() {
  const { symbol, timeframe, setTimeframe, accountSize, riskPct, setHighlight } = useWorkspace();
  const { data, error, isPending, refetch } = useAnalysisData(symbol, timeframe, accountSize, riskPct);
  const { send, why, newChat, open, conversationId } = useAI();
  const [insightOpen, setInsightOpen] = useState(true);
  const [view, setView] = useState<"chat" | "history">("chat");
  const startNew = () => { newChat(); setView("chat"); };
  const openSaved = async (id: number) => { await open(id); setView("chat"); };

  return (
    <div className="mx-auto grid h-full max-w-6xl gap-5 p-4 md:p-6 lg:grid-cols-[380px_minmax(0,1fr)]">
      <div className="space-y-3 lg:overflow-y-auto lg:pr-1">
        <div className="flex items-center justify-between">
          <div><h1 className="text-lg font-semibold">{data?.instrument.name ?? symbol}</h1><p className="text-xs text-faint">Shared with your chart · {symbol}</p></div>
          <Link to="/chart" className="btn-ghost !py-1.5 text-xs">Open chart →</Link>
        </div>
        <div className="flex gap-1 overflow-x-auto">
          {TIMEFRAMES.map((t) => <button key={t} onClick={() => setTimeframe(t)} className={cx("rounded-lg px-2.5 py-1 text-xs font-semibold", t === timeframe ? "bg-primary text-white" : "text-mute hover:bg-raised")}>{t}</button>)}
        </div>
        {isPending && <Skeleton className="h-64" />}
        {error && !data && <ErrorState error={error} onRetry={() => refetch()} />}
        {data && (<>
          <DataStatusBanner status={data.data_status} />
          <AIInsightCard analysis={data} open={insightOpen} onOpenChange={setInsightOpen} onExplain={() => send("", "analyze")} onWhy={(r) => { setHighlight(r); why(r); }} />
        </>)}
      </div>
      <div className="card flex min-h-[70vh] flex-col gap-3 p-4 lg:h-[calc(100vh-7rem)]">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">{view === "history" ? "Chat history" : "Conversation"}</h2>
          <ChatActions historyOpen={view === "history"} onNew={startNew} onToggleHistory={() => setView(view === "history" ? "chat" : "history")} />
        </div>
        {view === "history"
          ? <ChatHistory activeId={conversationId} onOpen={openSaved} onNew={startNew} onDeleted={(id) => { if (id === conversationId) newChat(); }} />
          : <AIChat className="min-h-0 flex-1" />}
      </div>
    </div>
  );
}

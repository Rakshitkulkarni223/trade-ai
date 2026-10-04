import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { aiStatus, listConversations } from "../../api/ai";
import { useAI } from "../../hooks/useAI";
import { useAnalysisData } from "../../hooks/useMarketData";
import { useWorkspace } from "../../store/useWorkspace";
import { DataStatusBanner, ErrorState, Skeleton } from "../common/ui";
import AIChat from "./AIChat";
import ChatActions from "./ChatActions";
import ChatHistory from "./ChatHistory";
import AIInsightCard from "./AIInsightCard";

/** The copilot: insight card on top, conversation below. Rendered as a side panel, a drawer or a bottom sheet. */
export default function AICopilot({ onClose }: { onClose?: () => void }) {
  const { symbol, timeframe, accountSize, riskPct, setHighlight } = useWorkspace();
  const { data, error, isPending, refetch } = useAnalysisData(symbol, timeframe, accountSize, riskPct);
  const status = useQuery({ queryKey: ["ai-status"], queryFn: aiStatus, staleTime: 60_000 });
  const { send, why, messages, newChat, open, conversationId } = useAI();
  const [view, setView] = useState<"chat" | "history">("chat");
  const title = useQuery({ queryKey: ["conversations"], queryFn: listConversations, staleTime: 5_000 }).data?.conversations.find((c) => c.id === conversationId)?.title;
  // Expanded while the panel is empty; collapses to a slim pinned verdict when the first question is asked.
  const [insightOpen, setInsightOpen] = useState(true);
  const prevCount = useRef(messages.length);
  useEffect(() => {
    if (prevCount.current === 0 && messages.length > 0) setInsightOpen(false);
    if (messages.length === 0) setInsightOpen(true);
    prevCount.current = messages.length;
  }, [messages.length]);

  const header = (
    <>
      {isPending && <Skeleton className="h-56" />}
      {error && !data && <ErrorState error={error} onRetry={() => refetch()} />}
      {data && (<>
        <DataStatusBanner status={data.data_status} />
        <AIInsightCard analysis={data} open={insightOpen} onOpenChange={setInsightOpen} onExplain={() => send("", "analyze")} onWhy={(r) => { setHighlight(r); why(r); }} />
      </>)}
    </>
  );

  const startNew = () => { newChat(); setView("chat"); };
  const openSaved = async (id: number) => { await open(id); setView("chat"); };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-ai text-[11px] font-bold text-white">AI</span>
            {view === "history" ? "Chat history" : "Market Copilot"}</h2>
          <p className="mt-0.5 truncate text-[11px] text-faint">
            {view === "history" ? "Your saved conversations" : <>{data?.instrument.name ?? symbol} · {timeframe} · {status.data?.llm ? `${status.data.provider} model` : "offline explainer"}</>}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <ChatActions historyOpen={view === "history"} onNew={startNew} onToggleHistory={() => setView(view === "history" ? "chat" : "history")} />
          {onClose && <button onClick={onClose} className="btn-ghost !h-9 !w-9 !px-0" aria-label="Close copilot">✕</button>}
        </div>
      </div>
      {view === "chat" && title && <p className="-mt-1 truncate rounded-lg bg-raised/60 px-3 py-1.5 text-[11.5px] text-mute" title={title}>{title}</p>}
      {view === "history" ? (
        <ChatHistory activeId={conversationId} onOpen={openSaved} onNew={startNew} onDeleted={(id) => { if (id === conversationId) newChat(); }} />
      ) : (
        <AIChat className="min-h-0 flex-1" header={header} pinHeader={messages.length > 0 && !insightOpen} />
      )}
    </div>
  );
}

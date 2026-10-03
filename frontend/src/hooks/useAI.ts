import { useCallback } from "react";
import { aiChat, aiExplain } from "../api/ai";
import { useWorkspace } from "../store/useWorkspace";
import type { ChartRef } from "../types";

/** Chat actions for the copilot. Messages live in the shared workspace store, so the side panel and the
 *  AI workspace show the same thread. The backend keeps the conversation and the analysis context it saw,
 *  so follow-ups like "what if it breaks 78,000?" refer to the same chart. */
export function useAI() {
  const { symbol, timeframe, conversationId, setConversationId, messages, setMessages, busy, setBusy } = useWorkspace();

  const send = useCallback(async (message: string, action?: string, compareWith?: string) => {
    setMessages((m) => [...m, { role: "user", content: message || actionLabel(action) }, { role: "assistant", content: "", pending: true }]);
    setBusy(true);
    try {
      const res = await aiChat({ symbol, timeframe, message, action, conversation_id: conversationId, compare_with: compareWith });
      setConversationId(res.conversation_id);
      setMessages((m) => [...m.slice(0, -1), { role: "assistant", content: res.reply, payload: res.payload }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Something went wrong.";
      setMessages((m) => [...m.slice(0, -1), { role: "assistant", content: `I couldn't complete that: ${msg}`, payload: { intent: "error", source: "error", refused: true } }]);
    } finally { setBusy(false); }
  }, [symbol, timeframe, conversationId, setConversationId, setMessages, setBusy]);

  const why = useCallback(async (ref: ChartRef) => {
    setMessages((m) => [...m, { role: "user", content: "Why?" }, { role: "assistant", content: "", pending: true }]);
    setBusy(true);
    try {
      const r = await aiExplain(symbol, timeframe, ref);
      setMessages((m) => [...m.slice(0, -1), { role: "assistant", content: r.text, payload: { intent: "explain", source: "offline", refs: [ref] } }]);
    } catch (e) {
      setMessages((m) => [...m.slice(0, -1), { role: "assistant", content: e instanceof Error ? e.message : "Couldn't explain that.", payload: { intent: "explain", source: "error" } }]);
    } finally { setBusy(false); }
  }, [symbol, timeframe, setMessages, setBusy]);

  const reset = useCallback(() => { setMessages(() => []); setConversationId(null); }, [setMessages, setConversationId]);
  return { messages, busy, send, why, reset };
}

export const QUICK_ACTIONS: { id: string; label: string }[] = [
  { id: "analyze", label: "Analyze Chart" }, { id: "liquidity", label: "Find Liquidity" },
  { id: "entry", label: "Find Entry" }, { id: "invalidation", label: "Find Invalidation" },
  { id: "trend", label: "Explain Trend" }, { id: "compare", label: "Compare" },
  { id: "swing", label: "Find Swing Setup" }, { id: "why_wait", label: "Why Should I Wait?" },
  { id: "beginner", label: "Explain Like I'm a Beginner" }, { id: "what_changed", label: "What changed?" },
];
const actionLabel = (a?: string) => QUICK_ACTIONS.find((q) => q.id === a)?.label ?? "Analyze";

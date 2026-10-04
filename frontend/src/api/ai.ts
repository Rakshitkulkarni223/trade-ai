import type { AnalyzeResponse, ChartRef, ChatMessage, ChatResponse, ScanResponse, Timeframe, TrackedSetup, WatchRow } from "../types";
import { del, get, patch, post } from "./client";

export const aiStatus = () => get<{ provider: string; llm: boolean; note: string | null }>("/api/ai/status");
export const aiAnalyze = (symbol: string, timeframe: Timeframe, accountSize?: number, riskPct?: number) =>
  post<AnalyzeResponse>("/api/ai/analyze", { symbol, timeframe, account_size: accountSize, max_risk_per_trade_pct: riskPct });
export const aiChat = (body: { symbol: string; timeframe: Timeframe; message: string; action?: string;
                               conversation_id?: number | null; compare_with?: string }) =>
  post<ChatResponse>("/api/ai/chat", { ...body, conversation_id: body.conversation_id ?? undefined });
export const aiExplain = (symbol: string, timeframe: Timeframe, ref: ChartRef) =>
  post<{ text: string }>("/api/ai/explain", { symbol, timeframe, ref_kind: ref.kind, ref_id: ref.id });

export const aiScan = (body: { market: string; timeframe: Timeframe; filters: string[]; direction: "long" | "short" }) =>
  post<ScanResponse>("/api/ai/scan", body);
export const screenQuery = (query: string, timeframe: Timeframe) => post<ScanResponse>("/api/screener/query", { query, timeframe });
export const screenRules = (market: string, timeframe: Timeframe, rules: Record<string, unknown>) =>
  post<ScanResponse>("/api/screener", { market, timeframe, rules });

export const fetchWatchlist = (timeframe: Timeframe) => get<{ items: WatchRow[] }>(`/api/watchlist?timeframe=${timeframe}`);
export interface AddWatchResult { symbol: string; name: string; added: boolean; resolved_from: string | null }
export const addWatch = (symbol: string) => post<AddWatchResult>("/api/watchlist", { symbol });
export const fetchWatchSymbols = () => get<{ symbols: string[] }>("/api/watchlist/symbols");
export const removeWatch = (symbol: string) => del<{ removed: string }>(`/api/watchlist/${encodeURIComponent(symbol)}`);

export const fetchSetups = () =>
  get<{ setups: TrackedSetup[]; summary: { total: number; open: number; closed: number; net_r: number; note: string } }>("/api/paper/setups");
export const trackSetup = (symbol: string, timeframe: Timeframe, note?: string) =>
  post<TrackedSetup>("/api/paper/setups", { symbol, timeframe, note });
export const deleteSetup = (id: number) => del<{ deleted: number }>(`/api/paper/setups/${id}`);

export interface ConversationSummary { id: number; title: string; symbol: string; timeframe: Timeframe; updated_at: number; message_count: number }
export interface ConversationFull {
  id: number; title: string | null; symbol: string; timeframe: Timeframe; updated_at: number;
  messages: { role: "user" | "assistant"; content: string; payload: ChatMessage["payload"]; created_at: number }[];
}
export const listConversations = () => get<{ conversations: ConversationSummary[] }>("/api/ai/conversations");
export const getConversation = (id: number) => get<ConversationFull>(`/api/ai/conversations/${id}`);
export const renameConversation = (id: number, title: string) => patch<{ id: number; title: string }>(`/api/ai/conversations/${id}`, { title });
export const deleteConversation = (id: number) => del<{ deleted: number }>(`/api/ai/conversations/${id}`);

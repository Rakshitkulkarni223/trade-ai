import { create } from "zustand";
import type { ChartRef, ChatMessage, Timeframe } from "../types";

/** One shared context: the Trading Workspace and the AI Workspace both read symbol + timeframe from here,
 *  so "Analyze this chart" always means the chart the user is looking at. */
export type LiveState = "connecting" | "live" | "polling" | "offline";
export interface Live { key: string; price: number | null; state: LiveState; at: number }

export interface Layers {
  prevDay: boolean; prevWeek: boolean; swing: boolean; equal: boolean;
  fvg: boolean; structure: boolean; plan: boolean; supertrend: boolean; ema: boolean; vwap: boolean; bb: boolean; volume: boolean; rsi: boolean;
}
const DEFAULT_LAYERS: Layers = {
  prevDay: true, prevWeek: true, swing: true, equal: true, fvg: true, structure: true,
  plan: true, supertrend: true, ema: true, vwap: false, bb: false, volume: true, rsi: true,
};

function load<T>(key: string, fallback: T): T {
  try { const raw = localStorage.getItem(key); return raw ? { ...fallback, ...JSON.parse(raw) } : fallback; } catch { return fallback; }
}
function save(key: string, v: unknown) { try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* storage unavailable */ } }

interface State {
  symbol: string; timeframe: Timeframe; layers: Layers; highlight: ChartRef | null;
  aiOpen: boolean; conversationId: number | null; accountSize: number; riskPct: number;
  messages: ChatMessage[]; busy: boolean; live: Live; setLive: (l: Partial<Live>) => void;
  setMessages: (fn: (m: ChatMessage[]) => ChatMessage[]) => void; setBusy: (b: boolean) => void;
  setSymbol: (s: string) => void; setTimeframe: (t: Timeframe) => void;
  toggleLayer: (k: keyof Layers) => void; setHighlight: (r: ChartRef | null) => void;
  setAiOpen: (o: boolean) => void; setConversationId: (id: number | null) => void;
  setRisk: (accountSize: number, riskPct: number) => void;
}
const saved = load<{ symbol: string; timeframe: Timeframe; accountSize: number; riskPct: number }>(
  "tradeai.ws", { symbol: "BTCUSDT", timeframe: "1H", accountSize: 100000, riskPct: 1 });

export const useWorkspace = create<State>((set, get) => ({
  symbol: saved.symbol, timeframe: saved.timeframe, layers: load("tradeai.layers", DEFAULT_LAYERS),
  highlight: null, aiOpen: false, conversationId: null, accountSize: saved.accountSize, riskPct: saved.riskPct,
  messages: [], busy: false,
  live: { key: "", price: null, state: "connecting", at: 0 }, setLive: (l) => set({ live: { ...get().live, ...l } }),
  setMessages: (fn) => set({ messages: fn(get().messages) }), setBusy: (busy) => set({ busy }),
  setSymbol: (symbol) => { set({ symbol, conversationId: null, highlight: null, messages: [] }); persist(get()); },
  setTimeframe: (timeframe) => { set({ timeframe, highlight: null }); persist(get()); },
  toggleLayer: (k) => { const layers = { ...get().layers, [k]: !get().layers[k] }; set({ layers }); save("tradeai.layers", layers); },
  setHighlight: (highlight) => set({ highlight }),
  setAiOpen: (aiOpen) => set({ aiOpen }),
  setConversationId: (conversationId) => set({ conversationId }),
  setRisk: (accountSize, riskPct) => { set({ accountSize, riskPct }); persist(get()); },
}));
function persist(s: State) {
  save("tradeai.ws", { symbol: s.symbol, timeframe: s.timeframe, accountSize: s.accountSize, riskPct: s.riskPct });
}

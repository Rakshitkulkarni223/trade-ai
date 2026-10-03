export type Timeframe = "1m" | "5m" | "15m" | "30m" | "1H" | "4H" | "1D" | "1W";
export const TIMEFRAMES: Timeframe[] = ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W"];

export interface Instrument {
  symbol: string; name: string; category: string; provider: string;
  currency: string; currency_symbol: string; tz_offset: number; lot_size: number;
}
export interface Quote {
  symbol: string; name: string; currency_symbol: string; price: number; change: number;
  change_pct: number; prev_close?: number; high?: number; low?: number; volume?: number; as_of: number;
  error?: string;
}
export interface Candle { t: number; o: number; h: number; l: number; c: number; v: number }
export interface DataStatus { as_of: number; age_seconds: number; stale: boolean; note: string | null }

export type ChartRef = { kind: "liquidity" | "structure" | "fvg" | "plan" | "indicator"; id: string };

export interface LiquidityLevel {
  id: string; kind: "PDH" | "PDL" | "PWH" | "PWL" | "BSL" | "SSL" | "EQH" | "EQL";
  side: "buy_side" | "sell_side"; price: number; t: number; status: "active" | "swept" | "broken";
  swept_t: number | null; reclaimed: boolean;
}
export interface StructureEvent {
  id: string; type: "BOS" | "CHoCH"; direction: "bullish" | "bearish"; t: number; level: number; level_t: number;
}
export interface Swing { t: number; price: number; kind: "high" | "low"; label: string }
export interface Fvg { id: string; type: "bullish" | "bearish"; low: number; high: number; t: number; status: string; size: number }

export interface EvidenceItem {
  key: string; label: string; state: "pass" | "fail" | "warn" | "pending" | "info"; detail: string;
  ref: ChartRef | null; required: boolean;
}
export interface Signal {
  action: "LONG" | "SHORT" | "WAIT"; bias: string; considered_direction: "long" | "short";
  setup_type: string; summary: string; items: EvidenceItem[];
  evidence: { for: EvidenceItem[]; against: EvidenceItem[]; caution: EvidenceItem[]; missing: EvidenceItem[] };
  waiting_for: { label: string; done: boolean }[]; invalidation: string;
}
export interface Target { name: string; price: number; r: number; note: string | null }
export interface Plan {
  direction: "long" | "short"; status: "active" | "conditional"; entry: number; stop: number;
  targets: Target[]; risk_per_unit: number; rr: number[];
  sizing: { quantity: number; risk_amount: number; position_value: number; position_pct: number; capped: boolean; note: string | null };
  assumptions: Record<string, number | string>; warnings: string[]; disclaimer: string;
}
export interface Indicators {
  rsi: number | null; ema20: number | null; ema50: number | null; sma200: number | null; atr: number | null;
  atr_pct: number | null; vwap: number | null; volume_ratio: number | null; macd_hist: number | null;
  ema_alignment: string; price_vs_vwap_pct: number | null;
}
export interface Analysis {
  instrument: Instrument; quote: Quote | null; data_status: DataStatus;
  symbol: string; timeframe: Timeframe; bars: number; price: number; as_of: number; precision: number;
  indicators: Indicators;
  series: { t: number[]; ema20: (number | null)[]; ema50: (number | null)[]; vwap: (number | null)[];
            bb_upper: (number | null)[]; bb_lower: (number | null)[]; rsi: (number | null)[] };
  structure: { trend: string; swings: Swing[]; events: StructureEvent[]; last_bos: StructureEvent | null; last_choch: StructureEvent | null };
  liquidity: { levels: LiquidityLevel[]; nearest_buy_side: LiquidityLevel | null; nearest_sell_side: LiquidityLevel | null; recent_sweep: LiquidityLevel | null };
  fvg: Fvg[]; signal: Signal; plan: Plan;
}

export interface Section { id: string; title: string; body: string; bullets: string[]; refs: ChartRef[] }
export interface AnalyzeResponse {
  symbol: string; name: string; timeframe: Timeframe; instrument: Instrument; quote: Quote | null;
  data_status: DataStatus; narrative: string; narrative_source: string; sections: Section[];
  card: AnalysisCard; disclaimer: string;
}
export interface AnalysisCard {
  action: Signal["action"]; bias: string; setup_type: string; summary: string; evidence: Signal["evidence"];
  waiting_for: Signal["waiting_for"]; invalidation: string; plan: Plan; indicators: Indicators; symbol: string; timeframe: Timeframe;
}

export interface CompareRow {
  symbol: string; name: string; price: number; trend: string; rsi: number | null; atr_pct: number | null;
  ema_alignment: string; action: string; swept: string; waiting: string[];
}
export interface ChatPayload {
  intent: string; symbol?: string; timeframe?: Timeframe; refused?: boolean; source: string;
  card?: AnalysisCard; compare?: CompareRow[]; refs?: ChartRef[]; data_status?: DataStatus; disclaimer?: string;
}
export interface ChatMessage { role: "user" | "assistant"; content: string; payload?: ChatPayload | null; pending?: boolean }
export interface ChatResponse { conversation_id: number; reply: string; payload: ChatPayload }

export interface WatchRow {
  symbol: string; name: string; category: string; currency_symbol: string; price?: number; change_pct?: number;
  trend?: string | null; liquidity?: string | null; status?: Signal["action"] | null; summary?: string; error?: string;
}

export interface ScanCheck { rule: string; label: string; ok: boolean; detail: string }
export interface ScanResult {
  symbol: string; name: string; category: string; price: number; currency_symbol: string;
  action: Signal["action"]; bias: string; setup_type: string; summary: string; checks: ScanCheck[]; matched: boolean;
  supporting: string[]; waiting_for: string[];
  plan: { direction: string; status: string; entry: number; stop: number; tp1: number } | null;
  features: Record<string, unknown>;
}
export interface ScanResponse {
  market: string; timeframe: Timeframe; rules: Record<string, unknown>;
  funnel: { scanned: number; liquidity_events: number; structure_confirmations: number; potential_setups: number; matched: number };
  results: ScanResult[]; unavailable: { symbol: string; reason: string }[];
  parsed?: { market: string; rules: Record<string, unknown>; source: string };
}

export interface TrackedSetup {
  id: number; symbol: string; timeframe: Timeframe; direction: "long" | "short"; entry: number; stop: number;
  targets: Target[]; created_at: number; note: string | null; evidence: { summary: string; for: string[]; caution: string[] } | null;
  result: { state: string; best_target?: number; open_r?: number; realised_r?: number | null; closed: boolean; last_price?: number; note: string };
}

import type { Candle, DataStatus, Instrument, Quote, Timeframe } from "../types";
import { get, post } from "./client";

export interface UniverseResponse { categories: { id: string; label: string; instruments: Instrument[] }[]; timeframes: Timeframe[] }

export const fetchUniverse = () => get<UniverseResponse>("/api/market/universe");
export const searchSymbols = (q: string) => get<{ results: Instrument[] }>(`/api/market/search?q=${encodeURIComponent(q)}`);
export const fetchPulse = () => get<{ quotes: Quote[] }>("/api/market/pulse");
export const fetchQuotes = (symbols: string[]) => post<{ quotes: Quote[] }>("/api/market/quotes", { symbols });
export const fetchHistory = (symbol: string, timeframe: Timeframe, limit = 500) =>
  get<{ instrument: Instrument; timeframe: Timeframe; candles: Candle[]; data_status: DataStatus }>(
    `/api/market/${encodeURIComponent(symbol)}/history?timeframe=${timeframe}&limit=${limit}`);
export const fetchDepth = (symbol: string) =>
  get<{ bids: [number, number][]; asks: [number, number][] }>(`/api/market/${encodeURIComponent(symbol)}/depth`);

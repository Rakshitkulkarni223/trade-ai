import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchAnalysis } from "../api/analysis";
import { fetchHistory, fetchPulse, fetchUniverse, searchSymbols } from "../api/market";
import type { Timeframe } from "../types";

// Slower than the live feed on purpose: this refresh recomputes indicators, liquidity and the AI insight.
const POLL: Record<Timeframe, number> = { "1m": 8_000, "5m": 10_000, "15m": 15_000, "30m": 15_000, "1H": 15_000, "4H": 30_000, "1D": 60_000, "1W": 120_000 };

export const useHistory = (symbol: string, tf: Timeframe) =>
  useQuery({ queryKey: ["history", symbol, tf], queryFn: () => fetchHistory(symbol, tf), refetchInterval: POLL[tf], placeholderData: keepPreviousData });

export const useAnalysisData = (symbol: string, tf: Timeframe, accountSize?: number, riskPct?: number) =>
  useQuery({ queryKey: ["analysis", symbol, tf, accountSize, riskPct], queryFn: () => fetchAnalysis(symbol, tf, accountSize, riskPct),
             refetchInterval: POLL[tf], placeholderData: keepPreviousData });

export const usePulse = () => useQuery({ queryKey: ["pulse"], queryFn: fetchPulse, refetchInterval: 30_000 });
export const useUniverse = () => useQuery({ queryKey: ["universe"], queryFn: fetchUniverse, staleTime: Infinity });
export const useSearch = (q: string) => useQuery({ queryKey: ["search", q], queryFn: () => searchSymbols(q), staleTime: 60_000 });

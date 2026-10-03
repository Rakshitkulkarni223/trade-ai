import type { Analysis, Timeframe } from "../types";
import { get } from "./client";

export const fetchAnalysis = (symbol: string, timeframe: Timeframe, accountSize?: number, riskPct?: number) => {
  const q = new URLSearchParams({ timeframe });
  if (accountSize) q.set("account_size", String(accountSize));
  if (riskPct) q.set("risk_pct", String(riskPct));
  return get<Analysis>(`/api/analysis/${encodeURIComponent(symbol)}?${q}`);
};

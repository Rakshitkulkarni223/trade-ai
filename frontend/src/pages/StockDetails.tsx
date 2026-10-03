import { useEffect } from "react";
import { useParams } from "react-router-dom";
import AICopilot from "../components/ai/AICopilot";
import ChartToolbar from "../components/chart/ChartToolbar";
import ChartWorkspace from "../components/chart/ChartWorkspace";
import IndicatorPanel from "../components/chart/IndicatorPanel";
import LiquidityMap from "../components/chart/LiquidityMap";
import StructurePanel from "../components/chart/StructurePanel";
import { DataStatusBanner, ErrorState } from "../components/common/ui";
import MarketHeader from "../components/market/MarketHeader";
import { useAnalysisData, useHistory } from "../hooks/useMarketData";
import { liveKey } from "../hooks/useLiveFeed";
import { precisionFor } from "../lib/format";
import { useWorkspace } from "../store/useWorkspace";

/** The Trading Workspace: chart first, with liquidity / structure / indicators beside it and the copilot docked. */
export default function StockDetails() {
  const { symbol: param } = useParams();
  const { symbol, timeframe, setSymbol, accountSize, riskPct } = useWorkspace();
  useEffect(() => { if (param && param.toUpperCase() !== symbol.toUpperCase()) setSymbol(param); }, [param, symbol, setSymbol]);

  const history = useHistory(symbol, timeframe);
  const analysis = useAnalysisData(symbol, timeframe, accountSize, riskPct);
  const candles = history.data?.candles ?? [];
  const a = analysis.data;
  const precision = a?.precision ?? precisionFor(candles[candles.length - 1]?.c);

  return (
    <div className="grid gap-5 p-4 md:p-6 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="min-w-0 space-y-4">
        <MarketHeader analysis={a} symbol={symbol} />
        <DataStatusBanner status={history.data?.data_status} />
        <ChartToolbar />
        {history.error && !history.data ? (
          <ErrorState error={history.error} onRetry={() => history.refetch()} />
        ) : (
          <ChartWorkspace candles={candles} analysis={a} precision={precision} loading={history.isPending}
            dataKey={history.data ? liveKey(history.data.instrument.symbol, history.data.timeframe) : undefined} />
        )}
        {analysis.error && !a && history.data && (
          <div className="rounded-xl border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
            Analysis unavailable: {analysis.error instanceof Error ? analysis.error.message : "unknown error"}. The chart is shown without overlays.
          </div>
        )}
        {a && (
          <div className="grid gap-4 lg:grid-cols-3">
            <LiquidityMap analysis={a} />
            <StructurePanel analysis={a} />
            <IndicatorPanel analysis={a} />
          </div>
        )}
      </div>
      <aside className="hidden xl:block">
        <div className="card sticky top-4 h-[calc(100vh-6rem)] p-4"><AICopilot /></div>
      </aside>
    </div>
  );
}

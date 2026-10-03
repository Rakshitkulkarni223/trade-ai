import {
  ColorType, CrosshairMode, LineStyle, createChart,
  type AutoscaleInfo, type IChartApi, type IPriceLine, type ISeriesApi, type LogicalRange, type SeriesMarker, type Time, type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLiveFeed, liveKey } from "../../hooks/useLiveFeed";
import { useWorkspace } from "../../store/useWorkspace";
import type { Analysis, Candle, ChartRef, LiquidityLevel } from "../../types";
import { cx, fmtPrice, hexA } from "../../lib/format";
import { LEVEL_STYLE } from "../../lib/liquidityStyle";

// Colours mirror the CSS tokens (canvas and chart options cannot read CSS variables directly).
const C = {
  bg: "#0a0c11", text: "#8b93a7", grid: "#141822", up: "#26be82", down: "#f45064", primary: "#5b7cff",
  liq: "#38bdf8", fvg: "#fb923c", struct: "#a78bfa", warn: "#f5a524", ai: "#8b5cf6",
};

/** The chart gets the few levels that matter now; the Liquidity Map panel lists everything. Levels at the same
 *  price (e.g. PWH and a swing high) are merged into one line with a combined label. */
function pickLevels(levels: LiquidityLevel[], price: number, precision: number, highlightId?: string | null) {
  const active = levels.filter((l) => l.status === "active");
  const nearest = (side: LiquidityLevel["side"]) => active.filter((l) => l.side === side).sort((a, b) => Math.abs(a.price - price) - Math.abs(b.price - price)).slice(0, 3);
  const swept = levels.filter((l) => l.status === "swept").sort((a, b) => (b.swept_t ?? 0) - (a.swept_t ?? 0)).slice(0, 2);
  const chosen = new Map<string, LiquidityLevel>();
  [...nearest("buy_side"), ...nearest("sell_side"), ...swept, ...levels.filter((l) => l.id === highlightId)].forEach((l) => chosen.set(l.id, l));
  const byPrice = new Map<string, { level: LiquidityLevel; kinds: string[]; ids: string[] }>();
  chosen.forEach((l) => {
    const k = l.price.toFixed(precision);
    const g = byPrice.get(k);
    if (g) { if (!g.kinds.includes(l.kind)) g.kinds.push(l.kind); g.ids.push(l.id); if (l.status === "swept") g.level = l; }
    else byPrice.set(k, { level: l, kinds: [l.kind], ids: [l.id] });
  });
  return [...byPrice.values()];
}

/** `dataKey` says which symbol|timeframe `candles` belong to, so a live update can never be drawn on another market's history. */
interface Props { candles: Candle[]; analysis?: Analysis; precision: number; loading?: boolean; dataKey?: string }

/** Default view: show ~70 candles, but fit the price axis to the last ~50 plus the plan, so the latest action is readable. */
const VIEW_BARS = 70, FOCUS_BARS = 50, RIGHT_PAD_BARS = 10;

const TF_SECONDS: Record<string, number> = { "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800 };

const t = (n: number) => n as UTCTimestamp;

export default function ChartWorkspace({ candles, analysis, precision, loading, dataKey }: Props) {
  const { layers, highlight, symbol, timeframe } = useWorkspace();
  const mainRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const resetRef = useRef<HTMLButtonElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<{
    candle?: ISeriesApi<"Candlestick">; vol?: ISeriesApi<"Histogram">; ema20?: ISeriesApi<"Line">; ema50?: ISeriesApi<"Line">;
    vwap?: ISeriesApi<"Line">; bbU?: ISeriesApi<"Line">; bbL?: ISeriesApi<"Line">; rsi?: ISeriesApi<"Line">;
  }>({});
  const linesRef = useRef<IPriceLine[]>([]);
  const analysisRef = useRef<Analysis | undefined>(analysis);
  const layersRef = useRef(layers);
  const highlightRef = useRef<ChartRef | null>(highlight);
  const drawRef = useRef<() => void>(() => {});
  const lastKey = useRef("");
  const liveRef = useRef<Candle | null>(null);
  const pickedRef = useRef<{ level: LiquidityLevel; kinds: string[]; ids: string[] }[]>([]);
  const focusRef = useRef(true);       // default view: price scale fits the recent candles, not an old spike
  const candlesRef = useRef<Candle[]>(candles);
  candlesRef.current = candles;
  const [hover, setHover] = useState<Candle | null>(null);

  analysisRef.current = analysis;
  layersRef.current = layers;
  highlightRef.current = highlight;

  // ---- create charts once
  useEffect(() => {
    const el = mainRef.current, rsiEl = rsiRef.current;
    if (!el || !rsiEl) return;
    const base = {
      layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: C.text, fontFamily: "Inter, system-ui, sans-serif", fontSize: 11 },
      grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
      rightPriceScale: { borderColor: C.grid },
      timeScale: { borderColor: C.grid, rightOffset: 6, timeVisible: true, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: "#3a4256", labelBackgroundColor: "#232834" }, horzLine: { color: "#3a4256", labelBackgroundColor: "#232834" } },
    } as const;
    const chart = createChart(el, { ...base, autoSize: true });
    const rsiChart = createChart(rsiEl, { ...base, autoSize: true, timeScale: { ...base.timeScale, visible: false }, rightPriceScale: { borderColor: C.grid, scaleMargins: { top: 0.12, bottom: 0.12 } } });
    chartRef.current = chart; rsiChartRef.current = rsiChart;

    // Once you zoom or drag, stop forcing the focused fit and let the chart autoscale to what you are looking at.
    let down: { x: number; y: number } | null = null;
    const release = () => { focusRef.current = false; };
    const onDown = (e: PointerEvent) => { down = { x: e.clientX, y: e.clientY }; };
    const onMove = (e: PointerEvent) => { if (down && e.buttons === 1 && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) release(); };
    const onUp = () => { down = null; };
    el.addEventListener("wheel", release, { passive: true });
    el.addEventListener("pointerdown", onDown); el.addEventListener("pointermove", onMove); window.addEventListener("pointerup", onUp);

    const s = seriesRef.current;
    s.candle = chart.addCandlestickSeries({ upColor: C.up, downColor: C.down, borderUpColor: C.up, borderDownColor: C.down, wickUpColor: C.up, wickDownColor: C.down, priceLineVisible: true,
      autoscaleInfoProvider: (original: () => AutoscaleInfo | null) => {
        if (!focusRef.current) return original();
        const recent = candlesRef.current.slice(-FOCUS_BARS);
        if (recent.length === 0) return original();
        const live = liveRef.current;
        let lo = Math.min(...recent.map((c) => c.l), live ? live.l : Infinity);
        let hi = Math.max(...recent.map((c) => c.h), live ? live.h : -Infinity);
        const span = hi - lo || hi * 0.001;
        // plan levels join the fit only when they're close enough not to flatten the candles
        const a = analysisRef.current;
        if (a && layersRef.current.plan && a.signal.action !== "WAIT") {
          for (const v of [a.plan.entry, a.plan.stop, ...a.plan.targets.map((t) => t.price)]) {
            if (v > lo - span * 1.5 && v < hi + span * 1.5) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
          }
        }
        const pad = (hi - lo) * 0.08;
        return { priceRange: { minValue: lo - pad, maxValue: hi + pad } };
      } });
    s.vol = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    const line = (color: string, width: 1 | 2 = 1, style = LineStyle.Solid) =>
      chart.addLineSeries({ color, lineWidth: width, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false, lineStyle: style,
        autoscaleInfoProvider: () => null });   // overlays (EMA, VWAP, bands) must not stretch the price axis
    s.ema20 = line("#f5c451"); s.ema50 = line("#5b7cff", 2); s.vwap = line("#e879f9", 1, LineStyle.Dashed);
    s.bbU = line("#475569", 1, LineStyle.Dotted); s.bbL = line("#475569", 1, LineStyle.Dotted);
    s.rsi = rsiChart.addLineSeries({ color: C.ai, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    for (const [price, color] of [[70, C.down], [50, "#3a4256"], [30, C.up]] as const)
      s.rsi.createPriceLine({ price, color, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "" });

    // keep the two panes on the same time window
    let syncing = false;
    const link = (from: IChartApi, to: IChartApi) => from.timeScale().subscribeVisibleLogicalRangeChange((r: LogicalRange | null) => {
      if (syncing || !r) return;
      syncing = true; to.timeScale().setVisibleLogicalRange(r); syncing = false;
    });
    link(chart, rsiChart); link(rsiChart, chart);

    chart.subscribeCrosshairMove((p) => {
      const d = p.seriesData.get(s.candle!) as { open: number; high: number; low: number; close: number } | undefined;
      const vol = p.seriesData.get(s.vol!) as { value: number } | undefined;
      setHover(d && p.time ? { t: p.time as number, o: d.open, h: d.high, l: d.low, c: d.close, v: vol?.value ?? 0 } : null);
    });

    // overlay canvas: FVG boxes and structure breaks need pixel coordinates, so redraw whenever the view changes
    const canvas = overlayRef.current!;
    // Keep the Reset icon level with the TradingView logo (bottom-left), and as far in from the plot's right edge
    // as the logo is from its left edge. Measured from the real logo element so it holds at any size or zoom.
    const placeReset = () => {
      const btn = resetRef.current;
      if (!btn) return;
      const logo = el.querySelector<HTMLElement>("#tv-attr-logo");
      const cr = el.getBoundingClientRect(), lr = logo?.getBoundingClientRect();
      const size = btn.offsetHeight || 28;
      const bottom = lr && lr.height ? cr.bottom - lr.bottom + (lr.height - size) / 2 : 36;
      const inset = lr && lr.width ? lr.left - cr.left : 10;
      btn.style.bottom = `${Math.round(bottom)}px`;
      btn.style.right = `${Math.round(chart.priceScale("right").width() + inset)}px`;
    };
    const draw = () => {
      const a = analysisRef.current, ctx = canvas.getContext("2d");
      if (!ctx) return;
      const dpr = window.devicePixelRatio || 1;
      const w = el.clientWidth, h = el.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) { canvas.width = w * dpr; canvas.height = h * dpr; canvas.style.width = `${w}px`; canvas.style.height = `${h}px`; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      placeReset();
      if (!a || !s.candle) return;
      const L = layersRef.current, hl = highlightRef.current;
      const ts = chart.timeScale();
      const plotRight = w - chart.priceScale("right").width();
      const x = (time: number): number | null => { const c = ts.timeToCoordinate(t(time)); return c === null ? null : (c as number); };
      const y = (price: number) => s.candle!.priceToCoordinate(price);

      if (L.supertrend) {
        const tt = a.series.t;
        const run = (arr: (number | null)[], color: string) => {
          ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.setLineDash([]); ctx.beginPath();
          let open = false;
          for (let i = 0; i < tt.length; i++) {
            const v = arr[i];
            const xx = v == null ? null : x(tt[i]), yy = v == null ? null : y(v);
            if (xx === null || yy === null || xx > plotRight + 40) { open = false; continue; }
            if (!open) { ctx.moveTo(xx, yy); open = true; } else ctx.lineTo(xx, yy);
          }
          ctx.stroke();
        };
        run(a.series.st_up, "#26be82"); run(a.series.st_dn, "#f45064");

        // Buy / Sell signals: a dot where the Supertrend flips, and a solid pill (white border, pointer) like the TradingView script
        ctx.font = "800 11px Inter, sans-serif";
        for (const sg of a.supertrend.signals) {
          const xx = x(sg.t), yy = y(sg.price);
          if (xx === null || yy === null || xx < -30 || xx > plotRight + 10) continue;
          const buy = sg.type === "buy", fill = buy ? "#15a05c" : "#e0364a", text = buy ? "BUY" : "SELL";
          const w = ctx.measureText(text).width + 18, ph = 20, gap = 14;
          const plotBottom = h - ts.height() - 4;                    // above the time axis
          // Buy normally hangs below the support line and Sell sits above the resistance line; flip when that would leave the chart
          let below = buy;
          if (below && yy + gap + ph > plotBottom) below = false;
          if (!below && yy - gap - ph < 4) below = true;
          const top = below ? yy + gap : yy - gap - ph;
          const left = Math.min(Math.max(xx - w / 2, 2), plotRight - w - 2);
          ctx.save();
          ctx.setLineDash([]);
          ctx.fillStyle = fill; ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.lineWidth = 1.6; ctx.lineJoin = "round";
          ctx.beginPath(); ctx.arc(xx, yy, 4.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();          // the dot on the line
          ctx.beginPath();
          ctx.roundRect(left, top, w, ph, 5);
          ctx.fill(); ctx.stroke();
          const edge = below ? top : top + ph, tipY = below ? top - 7 : top + ph + 7;               // pointer toward the dot
          ctx.beginPath(); ctx.moveTo(xx - 5, edge); ctx.lineTo(xx, tipY); ctx.lineTo(xx + 5, edge); ctx.closePath(); ctx.fill(); ctx.stroke();
          ctx.fillRect(xx - 4, below ? top - 0.5 : top + ph - 2, 8, 2.5);                            // hide the seam between pill and pointer
          ctx.fillStyle = "#ffffff"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
          ctx.fillText(text, left + w / 2, top + ph / 2 + 0.5);
          ctx.restore();
        }
      }
      if (L.fvg) for (const g of a.fvg) {
        const y1 = y(g.high), y2 = y(g.low);
        if (y1 === null || y2 === null) continue;
        const x1: number = x(g.t) ?? 0;
        if (x1 > plotRight) continue;
        const on = hl?.kind === "fvg" && hl.id === g.id;
        ctx.fillStyle = `rgba(251,146,60,${on ? 0.32 : g.status === "unmitigated" ? 0.16 : 0.08})`;
        ctx.fillRect(x1, y1, plotRight - x1, y2 - y1);
        ctx.strokeStyle = `rgba(251,146,60,${on ? 1 : 0.55})`; ctx.lineWidth = on ? 2 : 1; ctx.setLineDash([]);
        ctx.strokeRect(x1, y1, plotRight - x1, y2 - y1);
        ctx.fillStyle = "rgba(251,146,60,.95)"; ctx.font = "600 10px Inter, sans-serif";
        ctx.fillText(`${g.type === "bullish" ? "Bull" : "Bear"} FVG`, Math.max(x1 + 4, 4), y1 + 11);
      }
      // Liquidity levels: start at the candle that formed them, run right until swept (then a cross), tagged at the start.
      for (const g of pickedRef.current) {
        const l = g.level, st = LEVEL_STYLE[l.kind], yy = y(l.price);
        if (yy === null) continue;
        const on = hl?.kind === "liquidity" && g.ids.includes(hl.id), swept = l.status === "swept";
        const x1 = Math.max(0, x(l.t) ?? 0);
        let x2 = plotRight, cross = false;
        if (swept && l.swept_t) { const sx = x(l.swept_t); if (sx !== null) { x2 = Math.min(sx, plotRight); cross = true; } }
        if (x1 >= plotRight || x2 <= 0) continue;
        const color = on ? "#ffffff" : st.color;
        ctx.save();
        ctx.globalAlpha = swept && !on ? 0.6 : 1;
        ctx.strokeStyle = color; ctx.lineCap = "round"; ctx.setLineDash(st.dash);
        ctx.lineWidth = on ? st.width + 1.4 : st.width;
        const offsets = st.double ? [-2.2, 2.2] : [0];
        for (const o of offsets) { ctx.beginPath(); ctx.moveTo(x1, yy + o); ctx.lineTo(x2, yy + o); ctx.stroke(); }
        ctx.setLineDash([]);
        if (cross) {        // swept: a small cross where price took the liquidity
          ctx.lineWidth = 1.8; ctx.beginPath();
          ctx.moveTo(x2 - 4, yy - 4); ctx.lineTo(x2 + 4, yy + 4); ctx.moveTo(x2 + 4, yy - 4); ctx.lineTo(x2 - 4, yy + 4); ctx.stroke();
        }
        // tag at the start of the line
        const label = g.kinds.join("/");
        ctx.font = "700 10px Inter, sans-serif";
        const tw = ctx.measureText(label).width + 10, tx = Math.min(x1 + 4, plotRight - tw - 4), ty = yy - 15;
        ctx.fillStyle = hexA(st.color, 0.2); ctx.strokeStyle = hexA(st.color, 0.75); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.roundRect(tx, ty, tw, 14, 4); ctx.fill(); ctx.stroke();
        ctx.fillStyle = on ? "#ffffff" : st.color; ctx.fillText(label, tx + 5, ty + 10.5);
        ctx.restore();
      }
      if (L.structure) for (const e of a.structure.events.filter((ev, i, all) => i >= all.length - 6 || (hl?.kind === "structure" && hl.id === ev.id))) {
        const yy = y(e.level); if (yy === null) continue;
        const x1: number = x(e.level_t) ?? 0, x2 = x(e.t);
        if (x2 === null) continue;
        const on = hl?.kind === "structure" && hl.id === e.id;
        ctx.strokeStyle = on ? "#ffffff" : "rgba(167,139,250,.85)"; ctx.lineWidth = on ? 2.5 : 1.25; ctx.setLineDash([5, 4]);
        ctx.beginPath(); ctx.moveTo(x1, yy); ctx.lineTo(x2, yy); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = on ? "#fff" : C.struct; ctx.font = "600 10px Inter, sans-serif";
        const label = `${e.type}`; ctx.fillText(label, (x1 + x2) / 2 - ctx.measureText(label).width / 2, yy + (e.direction === "bullish" ? 12 : -5));
      }
    };
    drawRef.current = draw;
    let sig = "", raf = 0;
    const loop = () => {
      // cheap change detector: view window + a reference price coordinate
      const r = chart.timeScale().getVisibleLogicalRange();
      const probe = s.candle!.priceToCoordinate(analysisRef.current?.price ?? 0);
      const next = `${r?.from}|${r?.to}|${probe}|${el.clientWidth}|${el.clientHeight}`;
      if (next !== sig) { sig = next; draw(); }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); el.removeEventListener("wheel", release); el.removeEventListener("pointerdown", onDown); el.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onUp); chart.remove(); rsiChart.remove(); chartRef.current = null; rsiChartRef.current = null; seriesRef.current = {}; };
  }, []);

  // Normal view: the latest candles with room on the right, price scale fitted to recent action + plan.
  const resetView = () => {
    const chart = chartRef.current, n = candlesRef.current.length;
    if (!chart || n === 0) return;
    focusRef.current = true;
    chart.priceScale("right").applyOptions({ autoScale: true });
    rsiChartRef.current?.priceScale("right").applyOptions({ autoScale: true });
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - VIEW_BARS), to: n + RIGHT_PAD_BARS });
  };

  // ---- live updates: touch only the forming candle; the periodic refresh rebuilds everything else
  const drawLive = (c: Candle) => {
    const s = seriesRef.current;
    if (!s.candle) return;
    try {
      s.candle.update({ time: t(c.t), open: c.o, high: c.h, low: c.l, close: c.c });
      s.vol?.update({ time: t(c.t), value: c.v, color: c.c >= c.o ? "rgba(38,190,130,.35)" : "rgba(244,80,100,.35)" });
    } catch {
      liveRef.current = null;       // a stray update older than the series: drop it, the next refresh rebuilds the bar
    }
  };
  const matches = dataKey === liveKey(symbol, timeframe);
  useLiveFeed(symbol, timeframe, {
    onCandle: (c) => {
      const last = candlesRef.current[candlesRef.current.length - 1];
      if (!matches || !last || c.t < last.t) return;       // never rewrite history, never mix markets
      liveRef.current = c; drawLive(c);
    },
    onTick: (price) => {
      const base = liveRef.current ?? candlesRef.current[candlesRef.current.length - 1];
      if (!matches || !base || Date.now() / 1000 >= base.t + (TF_SECONDS[timeframe] ?? 3600)) return;   // new bar: wait for the refresh
      const next = { ...base, h: Math.max(base.h, price), l: Math.min(base.l, price), c: price };
      liveRef.current = next; drawLive(next);
    },
  });

  // ---- candles, volume and indicator lines
  useEffect(() => {
    const s = seriesRef.current, chart = chartRef.current;
    if (!s.candle || !chart || candles.length === 0) return;
    const p = Math.pow(10, -precision);
    s.candle.applyOptions({ priceFormat: { type: "price", precision, minMove: p } });
    chart.applyOptions({ timeScale: { timeVisible: !["1D", "1W"].includes(timeframe) } });
    s.candle.setData(candles.map((c) => ({ time: t(c.t), open: c.o, high: c.h, low: c.l, close: c.c })));
    s.vol!.setData(candles.map((c) => ({ time: t(c.t), value: c.v, color: c.c >= c.o ? "rgba(38,190,130,.35)" : "rgba(244,80,100,.35)" })));

    // map indicator values by timestamp so a refresh between the two requests can never misalign them
    const A = analysis;
    const byTime = (arr?: (number | null)[]) => {
      const m = new Map<number, number>();
      if (A && arr) A.series.t.forEach((time, i) => { const v = arr[i]; if (v !== null && v !== undefined) m.set(time, v); });
      return m;
    };
    const lineData = (arr?: (number | null)[]) => { const m = byTime(arr); return candles.filter((c) => m.has(c.t)).map((c) => ({ time: t(c.t), value: m.get(c.t)! })); };
    s.ema20!.setData(lineData(A?.series.ema20)); s.ema50!.setData(lineData(A?.series.ema50)); s.vwap!.setData(lineData(A?.series.vwap));
    s.bbU!.setData(lineData(A?.series.bb_upper)); s.bbL!.setData(lineData(A?.series.bb_lower));
    const rsi = byTime(A?.series.rsi);
    s.rsi!.setData(candles.map((c) => (rsi.has(c.t) ? { time: t(c.t), value: rsi.get(c.t)! } : { time: t(c.t) })));

    const lastC = candles[candles.length - 1];
    if (liveRef.current && liveRef.current.t >= lastC.t && dataKey === liveKey(symbol, timeframe)) drawLive(liveRef.current);
    else liveRef.current = null;
    // Reset when the candles on screen switch to another symbol/timeframe. Keyed on the data, not the selection:
    // while the new history loads the old candles stay up, and resetting then would be undone when the new ones arrive.
    const shown = dataKey ?? `${symbol}|${timeframe}`;
    if (lastKey.current !== shown) { lastKey.current = shown; resetView(); }
    drawRef.current();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, analysis, precision, symbol, timeframe, dataKey]);

  // ---- indicator visibility
  useEffect(() => {
    const s = seriesRef.current;
    s.ema20?.applyOptions({ visible: layers.ema }); s.ema50?.applyOptions({ visible: layers.ema });
    s.vwap?.applyOptions({ visible: layers.vwap });
    s.bbU?.applyOptions({ visible: layers.bb }); s.bbL?.applyOptions({ visible: layers.bb });
    s.vol?.applyOptions({ visible: layers.volume });
  }, [layers]);

  // ---- price lines (liquidity + plan) and markers (structure + sweep)
  useEffect(() => {
    const s = seriesRef.current;
    if (!s.candle) return;
    linesRef.current.forEach((l) => s.candle!.removePriceLine(l));
    linesRef.current = [];
    drawRef.current();
    if (!analysis) { s.candle.setMarkers([]); return; }
    const add = (price: number, color: string, title: string, style: LineStyle, width: 1 | 2 | 3 = 1) =>
      linesRef.current.push(s.candle!.createPriceLine({ price, color, title, lineStyle: style, lineWidth: width, axisLabelVisible: true }));

    // Liquidity: the coloured tag on the price axis comes from a price line with its line hidden; the line itself is drawn
    // on the overlay canvas (see draw) so every kind of level can have its own look and start where it formed.
    const visible = analysis.liquidity.levels.filter((l) => layers[LEVEL_STYLE[l.kind].layer]);
    const groups = pickLevels(visible, analysis.price, precision, highlight?.kind === "liquidity" ? highlight.id : null);
    pickedRef.current = groups;
    for (const g of groups) {
      const l = g.level, name = g.kinds.join("/"), swept = l.status === "swept";
      linesRef.current.push(s.candle!.createPriceLine({ price: l.price, color: swept ? hexA(LEVEL_STYLE[l.kind].color, 0.55) : LEVEL_STYLE[l.kind].color,
        title: swept ? `${name} ✓` : name, lineVisible: false, axisLabelVisible: true }));
    }
    drawRef.current();
    // Entry / SL / TP exist only for a confirmed setup. While the status is WAIT there is nothing to draw:
    // scenario levels on every chart invite trades that are not there.
    if (layers.plan && analysis.signal.action !== "WAIT") {
      const p = analysis.plan;
      const style = LineStyle.Solid;
      const sfx = "";
      const hl = (id: string) => (highlight?.kind === "plan" && highlight.id === id ? 3 : 1) as 1 | 3;
      add(p.entry, C.primary, `ENTRY${sfx}`, style, hl("entry"));
      add(p.stop, C.down, `SL${sfx}`, style, hl("stop"));
      p.targets.forEach((tg) => add(tg.price, C.up, `${tg.name}${sfx}`, style, hl("targets")));
    }

    const markers: SeriesMarker<Time>[] = [];
    if (layers.structure) for (const e of analysis.structure.events.slice(-6)) {
      const bull = e.direction === "bullish";
      markers.push({ time: t(e.t), position: bull ? "belowBar" : "aboveBar", shape: bull ? "arrowUp" : "arrowDown", color: C.struct, text: e.type });
    }
    for (const l of analysis.liquidity.levels.filter((x) => x.status === "swept").sort((a, b) => (b.swept_t ?? 0) - (a.swept_t ?? 0)).slice(0, 3)) {
      if (l.swept_t && layers[LEVEL_STYLE[l.kind].layer]) {
        const sell = l.side === "sell_side";
        markers.push({ time: t(l.swept_t), position: sell ? "belowBar" : "aboveBar", shape: "circle", color: C.liq, text: `${sell ? "SSL" : "BSL"} swept` });
      }
    }
    const st = analysis.signal.state;
    if (st && analysis.signal.action !== "WAIT") {
      const long = analysis.signal.action === "LONG";
      markers.push({ time: t(st.since_t), position: long ? "belowBar" : "aboveBar", shape: long ? "arrowUp" : "arrowDown", color: long ? C.up : C.down, text: `${analysis.signal.action} setup` });
    }
    markers.sort((a, b) => (a.time as number) - (b.time as number));
    // one marker per candle/position keeps the chart readable
    const seen = new Set<string>();
    s.candle.setMarkers(markers.filter((m) => { const k = `${m.time}|${m.position}`; if (seen.has(k)) return false; seen.add(k); return true; }));
  }, [analysis, layers, highlight]);

  const last = candles[candles.length - 1];
  const shown = hover ?? last;
  const change = useMemo(() => (shown ? ((shown.c - shown.o) / shown.o) * 100 : 0), [shown]);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-line bg-bg">
      <div className="pointer-events-none absolute left-3 top-2 z-10 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] tnum text-mute">
        {shown && (<>
          <span>O <b className="font-medium text-ink">{fmtPrice(shown.o, precision)}</b></span>
          <span>H <b className="font-medium text-ink">{fmtPrice(shown.h, precision)}</b></span>
          <span>L <b className="font-medium text-ink">{fmtPrice(shown.l, precision)}</b></span>
          <span>C <b className="font-medium text-ink">{fmtPrice(shown.c, precision)}</b></span>
          <span className={cx(change >= 0 ? "text-up" : "text-down")}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</span>
        </>)}
        {layers.ema && (<><span className="text-[#f5c451]">EMA 20</span><span className="text-primary">EMA 50</span></>)}
        {layers.vwap && <span className="text-[#e879f9]">VWAP</span>}
      </div>
      {/* belongs to the Entry / SL / TP layer: switch the layer off and the status note goes with it */}
      {analysis && layers.plan && (
        <div className="pointer-events-none absolute left-3 top-8 z-10 max-w-[70%]">
          {analysis.signal.action === "WAIT" ? (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-warn/30 bg-bg/80 px-2 py-0.5 text-[11px] text-warn backdrop-blur">
              <span className="h-1.5 w-1.5 rounded-full bg-warn" />No entry yet · wait for a confirmed setup
            </span>
          ) : (
            <span className={cx("inline-flex items-center gap-1.5 rounded-md border bg-bg/80 px-2 py-0.5 text-[11px] backdrop-blur",
              analysis.signal.action === "LONG" ? "border-up/40 text-up" : "border-down/40 text-down")}>
              <span className={cx("h-1.5 w-1.5 rounded-full", analysis.signal.action === "LONG" ? "bg-up" : "bg-down")} />
              {analysis.signal.action} setup active{analysis.signal.state ? ` · ${analysis.signal.state.age_bars} candle${analysis.signal.state.age_bars === 1 ? "" : "s"} ago · levels fixed` : ""}
            </span>
          )}
        </div>
      )}
      <div ref={mainRef} className="relative h-[46vh] min-h-[320px] w-full md:h-[52vh]">
        <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 z-[5]" />
        <button ref={resetRef} onClick={resetView} title="Reset view" aria-label="Reset view" style={{ bottom: 36, right: 84 }}
          className="absolute z-10 grid h-7 w-7 place-items-center rounded-md border border-line bg-panel/90 text-mute shadow-lg backdrop-blur transition hover:border-primary/60 hover:text-ink active:scale-90">
          <svg aria-hidden viewBox="0 0 24 24" className="h-[15px] w-[15px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" />
          </svg>
        </button>
      </div>
      <div className={cx("border-t border-line", !layers.rsi && "hidden")}>
        <div className="px-3 pt-1 text-[10px] font-medium uppercase tracking-wider text-faint">RSI 14</div>
        <div ref={rsiRef} className="h-[88px] w-full" />
      </div>
      {loading && <div className="absolute inset-0 z-20 grid place-items-center bg-bg/60 text-sm text-mute">Loading market data…</div>}
    </div>
  );
}

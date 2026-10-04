import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useWorkspace } from "../store/useWorkspace";
import type { Candle, Timeframe } from "../types";

export const liveKey = (symbol: string, tf: Timeframe) => `${symbol.toUpperCase()}|${tf}`;

interface Handlers { onCandle: (c: Candle, closed: boolean) => void; onTick: (price: number) => void }

/** Connects to the backend's live feed for the symbol/timeframe on screen: a streaming candle for crypto,
 *  a polled price tick for everything else. Reconnects with backoff; reports its state to the store. */
export function useLiveFeed(symbol: string, tf: Timeframe, handlers: Handlers) {
  const h = useRef(handlers);
  h.current = handlers;
  const setLive = useWorkspace((s) => s.setLive);
  const qc = useQueryClient();

  useEffect(() => {
    const key = liveKey(symbol, tf);
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let closed = false;
    let pending: number | null = null;
    let wasClosed = false;
    let flush: ReturnType<typeof setInterval> | undefined;

    setLive({ key, price: null, state: "connecting", at: 0 });

    // The header price re-renders at most ~4 times a second, however fast ticks arrive.
    flush = setInterval(() => {
      if (pending !== null) { setLive({ key, price: pending, at: Date.now() }); pending = null; }
    }, 250);

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(`${proto}//${location.host}/ws/market/${encodeURIComponent(symbol)}?timeframe=${tf}`);
      ws.onmessage = (ev) => {
        if (closed) return;          // a replaced connection (old timeframe/symbol) must never touch the new chart
        let m: { type: string; mode?: string; candle?: Candle; closed?: boolean; price?: number; state?: string };
        try { m = JSON.parse(ev.data); } catch { return; }
        if (m.type === "hello") {
          attempt = 0; setLive({ key, state: m.mode === "stream" ? "live" : "polling" });
          if (wasClosed) { wasClosed = false; qc.invalidateQueries({ queryKey: ["history"] }); qc.invalidateQueries({ queryKey: ["analysis"] }); }   // the market just opened: catch up
        }
        else if (m.type === "status" && m.state === "closed") { wasClosed = true; setLive({ key, state: "closed" }); }
        else if (m.type === "kline" && m.candle) { pending = m.candle.c; h.current.onCandle(m.candle, !!m.closed); }
        else if (m.type === "tick" && typeof m.price === "number") { pending = m.price; h.current.onTick(m.price); }
        else if (m.type === "status" && m.state === "error") {
          setLive({ key, state: "offline" });
          if ((m as { fatal?: boolean }).fatal) closed = true;     // an unknown symbol will not start working: stop retrying
        }
      };
      ws.onclose = () => {
        if (closed) return;
        setLive({ key, state: "offline" });
        timer = setTimeout(connect, Math.min(1000 * 2 ** attempt++, 15000));
      };
      ws.onerror = () => ws?.close();
    };
    connect();

    return () => { closed = true; clearTimeout(timer); clearInterval(flush); ws?.close(); };
  }, [symbol, tf, setLive, qc]);
}

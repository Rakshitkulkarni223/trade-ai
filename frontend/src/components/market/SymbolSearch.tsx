import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSearch } from "../../hooks/useMarketData";
import { useWorkspace } from "../../store/useWorkspace";
import { cx } from "../../lib/format";

export default function SymbolSearch({ large, autoFocus, onPick, placeholder }: {
  large?: boolean; autoFocus?: boolean; placeholder?: string; onPick?: (symbol: string) => void;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [debounced, setDebounced] = useState("");
  const [idx, setIdx] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const nav = useNavigate();
  const setSymbol = useWorkspace((s) => s.setSymbol);
  const { data } = useSearch(debounced);

  useEffect(() => { const id = setTimeout(() => setDebounced(q), 120); return () => clearTimeout(id); }, [q]);
  useEffect(() => { setIdx(0); }, [debounced]);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const pick = (symbol: string) => {
    setQ(""); setOpen(false);
    if (onPick) onPick(symbol); else { setSymbol(symbol); nav("/chart"); }
  };
  const results = data?.results ?? [];
  const raw = q.trim().toUpperCase();
  const canRaw = raw.length > 0 && !results.some((r) => r.symbol === raw);

  return (
    <div ref={box} className="relative w-full">
      <div className="relative">
        <svg className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="9" cy="9" r="6" /><path d="m14 14 4 4" strokeLinecap="round" /></svg>
        <input autoFocus={autoFocus} className={cx("input !pl-10", large && "!rounded-2xl !py-4 !text-base")} placeholder={placeholder ?? "Search stocks, crypto, indices…"} value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(e.target.value.trim().length > 0); }} onFocus={() => q.trim() && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, results.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
            else if (e.key === "Enter") { const t = results[idx]?.symbol ?? (canRaw ? raw : undefined); if (t) pick(t); }
            else if (e.key === "Escape") setOpen(false);
          }} />
      </div>
      {open && (results.length > 0 || canRaw) && (
        <ul className="absolute left-0 right-0 top-full z-40 mt-2 max-h-80 overflow-y-auto rounded-2xl border border-line bg-panel p-1.5 shadow-2xl">
          {results.map((r, i) => (
            <li key={r.symbol}>
              <button onMouseEnter={() => setIdx(i)} onClick={() => pick(r.symbol)}
                className={cx("flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left", i === idx ? "bg-raised" : "")}>
                <span><span className="text-sm font-medium text-ink">{r.name}</span><span className="ml-2 text-xs text-faint">{r.symbol}</span></span>
                <span className="rounded-md bg-raised px-1.5 py-0.5 text-[10px] text-mute">{r.category}</span>
              </button>
            </li>
          ))}
          {canRaw && (
            <li><button onClick={() => pick(raw)} className="w-full rounded-xl px-3 py-2 text-left text-sm text-mute hover:bg-raised">
              Try ticker <b className="text-ink">{raw}</b> <span className="text-xs text-faint">(Yahoo Finance / Binance)</span></button></li>
          )}
        </ul>
      )}
    </div>
  );
}

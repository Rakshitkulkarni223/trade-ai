import { useEffect, useRef, useState } from "react";
import { QUICK_ACTIONS, useAI } from "../../hooks/useAI";
import { useWorkspace } from "../../store/useWorkspace";
import type { AnalysisCard, ChatMessage, CompareRow } from "../../types";
import { cx, fmtPrice } from "../../lib/format";
import { ActionBadge } from "../common/ui";

export function AIQuickActions({ onPick, disabled }: { onPick: (id: string) => void; disabled?: boolean }) {
  return (
    <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
      {QUICK_ACTIONS.map((q) => (
        <button key={q.id} className="chip shrink-0" disabled={disabled} onClick={() => onPick(q.id)}>{q.label}</button>
      ))}
    </div>
  );
}

function MiniCard({ card }: { card: AnalysisCard }) {
  const p = card.plan, scenario = p.status === "conditional";
  const dec = Math.abs(p.entry) >= 1000 ? 2 : Math.abs(p.entry) >= 1 ? 4 : 8;
  return (
    <div className="mt-2 rounded-xl border border-line bg-bg/60 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-mute">{card.symbol} · {card.timeframe}</span><ActionBadge action={card.action} />
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        {[["Entry", p.entry, "text-primary"], ["SL", p.stop, "text-down"], ...p.targets.map((t) => [t.name, t.price, "text-up"] as const)].map(([k, v, c]) => (
          <div key={String(k)} className="flex justify-between"><span className="text-mute">{k}{scenario && k === "Entry" ? " (scenario)" : ""}</span><span className={cx("tnum font-medium", String(c))}>{fmtPrice(Number(v), dec)}</span></div>
        ))}
      </div>
      {card.waiting_for.length > 0 && card.action === "WAIT" && (
        <ul className="mt-2 space-y-0.5 border-t border-line pt-2 text-xs">
          {card.waiting_for.map((w) => <li key={w.label} className={w.done ? "text-up" : "text-mute"}>{w.done ? "✓" : "○"} {w.label}</li>)}
        </ul>
      )}
    </div>
  );
}

function CompareTable({ rows }: { rows: CompareRow[] }) {
  return (
    <div className="mt-2 overflow-x-auto rounded-xl border border-line">
      <table className="w-full min-w-[320px] text-xs">
        <thead><tr className="text-left text-faint"><th className="p-2 font-medium" />{rows.map((r) => <th key={r.symbol} className="p-2 font-semibold text-ink">{r.name}</th>)}</tr></thead>
        <tbody className="[&_td]:border-t [&_td]:border-line [&_td]:p-2">
          <tr><td className="text-mute">Status</td>{rows.map((r) => <td key={r.symbol}><ActionBadge action={r.action} /></td>)}</tr>
          <tr><td className="text-mute">Structure</td>{rows.map((r) => <td key={r.symbol} className="capitalize">{r.trend}</td>)}</tr>
          <tr><td className="text-mute">RSI</td>{rows.map((r) => <td key={r.symbol} className="tnum">{r.rsi ?? "—"}</td>)}</tr>
          <tr><td className="text-mute">ATR</td>{rows.map((r) => <td key={r.symbol} className="tnum">{r.atr_pct ?? "—"}%</td>)}</tr>
          <tr><td className="text-mute">Liquidity</td>{rows.map((r) => <td key={r.symbol}>{r.swept === "none" ? "—" : `swept ${r.swept.replace("_", "-")}`}</td>)}</tr>
        </tbody>
      </table>
    </div>
  );
}

function Bubble({ m, onShow }: { m: ChatMessage; onShow: (ref: NonNullable<ChatMessage["payload"]>["refs"]) => void }) {
  if (m.role === "user") return <div className="rise ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-primary/90 px-3.5 py-2 text-sm text-white">{m.content}</div>;
  const p = m.payload;
  return (
    <div className="rise max-w-[95%]">
      <div className={cx("rounded-2xl rounded-bl-md border px-3.5 py-2.5", p?.refused ? "border-down/30 bg-down/5" : "border-line bg-raised")}>
        {m.pending ? (
          <span className="flex items-center gap-1.5 py-1 text-faint">{[0, 1, 2].map((i) => <span key={i} className="dot-live h-1.5 w-1.5 rounded-full bg-ai" style={{ animationDelay: `${i * 0.2}s` }} />)}</span>
        ) : (<>
          <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink">{m.content}</p>
          {p?.card && p.intent !== "compare" && p.intent !== "whatif" && p.intent !== "what_changed" && <MiniCard card={p.card} />}
          {p?.compare && <CompareTable rows={p.compare} />}
          {p?.refs && p.refs.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              <button className="chip !py-1" onClick={() => onShow(p.refs)}>Show on chart</button>
            </div>
          )}
        </>)}
      </div>
      {!m.pending && p?.source && p.source !== "error" && p.source !== "backend" && (
        <div className="mt-1 px-1 text-[10px] text-faint">{p.source === "offline" ? "Rules-based explainer · numbers from the analysis engine" : `${p.source} · checked against backend numbers`}</div>
      )}
    </div>
  );
}

export default function AIChat({ className, showActions = true }: { className?: string; showActions?: boolean }) {
  const { symbol, timeframe, setHighlight } = useWorkspace();
  const { messages, busy, send, reset } = useAI();
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);

  const submit = () => { const t = text.trim(); if (!t || busy) return; setText(""); send(t); };

  return (
    <div className={cx("flex min-h-0 flex-col", className)}>
      {showActions && <AIQuickActions disabled={busy} onPick={(id) => send("", id)} />}
      <div className="mt-2 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="rounded-xl border border-dashed border-line p-4 text-center text-xs text-mute">
            Ask about <b className="text-ink">{symbol}</b> on the <b className="text-ink">{timeframe}</b> chart: liquidity, structure, entry, invalidation, or “what if it breaks 78,000?”.
          </div>
        )}
        {messages.map((m, i) => <Bubble key={i} m={m} onShow={(refs) => refs && refs[0] && setHighlight(refs[0])} />)}
        <div ref={end} />
      </div>
      <div className="mt-2 flex items-end gap-2">
        <textarea rows={1} className="input max-h-28 min-h-[42px] resize-none" placeholder={`Ask anything about ${symbol}…`} value={text}
          onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} />
        <button className="btn-ai h-[42px] shrink-0" onClick={submit} disabled={busy || !text.trim()} aria-label="Send">Send</button>
      </div>
      <div className="mt-1.5 flex items-center justify-between px-1 text-[10px] text-faint">
        <span>Information only, not financial advice.</span>
        {messages.length > 0 && <button className="hover:text-mute" onClick={reset}>Clear</button>}
      </div>
    </div>
  );
}

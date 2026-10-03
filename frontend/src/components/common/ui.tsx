import type { ReactNode } from "react";
import type { DataStatus, Signal } from "../../types";
import { actionTone, cx, hexA, timeAgo } from "../../lib/format";

export function ActionBadge({ action, className }: { action?: Signal["action"] | string | null; className?: string }) {
  if (!action) return <span className="text-faint">—</span>;
  return (
    <span className={cx("inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold tracking-wide", actionTone(action), className)}>
      {action}
    </span>
  );
}

export function TrendText({ trend }: { trend?: string | null }) {
  if (!trend) return <span className="text-faint">—</span>;
  const c = trend === "bullish" ? "text-up" : trend === "bearish" ? "text-down" : "text-mute";
  return <span className={cx("capitalize", c)}>{trend}</span>;
}

/** Surfaces stale / closed-market data prominently: the AI must never imply the data is fresher than it is. */
export function DataStatusBanner({ status }: { status?: DataStatus }) {
  if (!status?.note) return null;
  return (
    <div className={cx("flex items-start gap-2 rounded-xl border px-3 py-1.5 text-[11px] leading-snug",
      status.stale ? "border-warn/40 bg-warn/10 text-warn" : "border-line bg-raised text-mute")}>
      <span aria-hidden>{status.stale ? "⚠" : "◐"}</span>
      <span>{status.note} <span className="text-faint">Last candle {timeAgo(status.as_of)}.</span></span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="card flex flex-col items-start gap-3 p-5">
      <div className="text-sm font-medium text-down">Data unavailable</div>
      <p className="text-sm text-mute">{msg}</p>
      <p className="text-xs text-faint">No analysis is shown without real market data. Nothing is estimated or filled in.</p>
      {onRetry && <button className="btn-ghost" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-xl bg-raised", className)} />;
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-sm font-semibold text-ink">{children}</h2>
      {aside}
    </div>
  );
}

/** ON: filled tint, coloured border, a tick and full-strength text. OFF: hollow ring, dim text, no fill. */
export function Toggle({ on, onChange, label, color = "#5b7cff" }: { on: boolean; onChange: () => void; label: string; color?: string }) {
  return (
    <button onClick={onChange} aria-pressed={on}
      className={cx("flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition active:scale-[.97]",
        on ? "font-semibold text-ink" : "border-line/70 font-medium text-faint hover:text-mute")}
      style={on ? { background: hexA(color, 0.16), borderColor: hexA(color, 0.7), boxShadow: `inset 0 0 0 1px ${hexA(color, 0.12)}` } : undefined}>
      <span aria-hidden className="grid h-3.5 w-3.5 place-items-center rounded-full border text-[9px] leading-none"
        style={on ? { background: color, borderColor: color, color: "#0a0c11" } : { borderColor: "rgb(var(--faint))" }}>{on ? "✓" : ""}</span>
      {label}
    </button>
  );
}

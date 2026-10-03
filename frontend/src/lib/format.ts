export function fmtPrice(v: number | null | undefined, precision = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: precision, maximumFractionDigits: precision });
}
export function precisionFor(price: number | undefined): number {
  if (!price) return 2;
  return price >= 10 ? 2 : price >= 1 ? 4 : 6;
}
export const fmtPct = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(d)}%`;
export const tone = (v: number | null | undefined) => (v === null || v === undefined || v === 0 ? "text-mute" : v > 0 ? "text-up" : "text-down");
export function timeAgo(ts: number): string {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  if (s < 129600) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}
export const actionTone = (a?: string | null) =>
  a === "LONG" ? "text-up border-up/40 bg-up/10" : a === "SHORT" ? "text-down border-down/40 bg-down/10"
    : "text-warn border-warn/40 bg-warn/10";
export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/** "#rrggbb" + alpha -> rgba(), for tints built from a swatch colour. */
export function hexA(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

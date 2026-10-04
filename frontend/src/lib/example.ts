/** A realistic "what if it breaks …" level for the instrument on screen: ~2% below the current price, rounded to a tidy
 *  number at that price's scale (22,400 -> 22,000; 84,600 -> 82,500; 2,680 -> 2,650; 0.21 -> 0.195). */
export function exampleLevel(price: number | undefined | null): number | null {
  if (!price || !Number.isFinite(price) || price <= 0) return null;
  const target = price * 0.98;
  const magnitude = Math.pow(10, Math.floor(Math.log10(target)));
  const step = magnitude / 20;
  const level = Math.round(target / step) * step;
  return level > 0 ? level : null;
}

export function formatLevel(level: number): string {
  const d = level >= 100 ? 0 : level >= 1 ? 2 : 3;
  return level.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: d });
}

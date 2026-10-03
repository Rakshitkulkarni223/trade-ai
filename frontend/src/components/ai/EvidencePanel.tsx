import type { ChartRef, EvidenceItem, Signal } from "../../types";
import { cx } from "../../lib/format";

const MARK: Record<string, { icon: string; tone: string }> = {
  pass: { icon: "✓", tone: "text-up" }, warn: { icon: "⚠", tone: "text-warn" },
  fail: { icon: "✗", tone: "text-down" }, pending: { icon: "○", tone: "text-faint" }, info: { icon: "◆", tone: "text-fvg" },
};

/** "Why this setup?" Observable reasons instead of a confidence percentage. */
export default function EvidencePanel({ evidence, onWhy, compact }: {
  evidence: Signal["evidence"]; onWhy?: (ref: ChartRef) => void; compact?: boolean;
}) {
  const groups: [string, EvidenceItem[]][] = [
    ["Supporting", evidence.for], ["Caution", evidence.caution], ["Against", evidence.against], ["Missing confirmation", evidence.missing],
  ];
  return (
    <div className="space-y-2.5">
      {groups.filter(([, items]) => items.length).map(([name, items]) => (
        <div key={name}>
          <div className="label mb-1">{name}</div>
          <ul className="space-y-1">
            {items.map((i) => (
              <li key={i.key} className="flex items-start gap-2 text-[13px] leading-snug">
                <span className={cx("mt-px w-4 shrink-0 text-center font-semibold", MARK[i.state].tone)}>{MARK[i.state].icon}</span>
                <span className="min-w-0 flex-1">
                  <span className="text-ink">{i.label}</span>
                  {!compact && <span className="block text-xs text-mute">{i.detail}</span>}
                </span>
                {i.ref && onWhy && (
                  <button onClick={() => onWhy(i.ref!)} className="shrink-0 rounded-md border border-line px-1.5 py-0.5 text-[10px] font-medium text-mute hover:border-ai/60 hover:text-ai">Why?</button>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

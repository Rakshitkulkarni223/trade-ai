import type { ReactNode } from "react";

/** Small, safe markdown renderer for model replies: **bold**, *italic*, `code`, bullets, numbered lists, headings.
 *  Builds React nodes (never raw HTML), so model output cannot inject markup. */
function inline(text: string, k: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g).filter(Boolean).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <strong key={`${k}${i}`} className="font-semibold text-ink">{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) return <code key={`${k}${i}`} className="rounded bg-bg px-1 py-0.5 font-mono text-[12px] text-ai">{part.slice(1, -1)}</code>;
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) return <em key={`${k}${i}`}>{part.slice(1, -1)}</em>;
    return <span key={`${k}${i}`}>{part}</span>;
  });
}

const BULLET = /^(\s*)[-*•]\s+(.*)$/;
const NUMBERED = /^(\s*)\d+[.)]\s+(.*)$/;
const HEADING = /^#{1,4}\s+(.*)$/;
const LABEL = /^\*\*([^*]+?):?\*\*:?\s*$/;          // a line that is just **Title:**
const FOOTNOTE = /^\*\(?[^*]+\)?\*$/;               // a whole line in italics, e.g. the disclaimer

/** "**Title:**" or "## Title" on its own line becomes a section label. */
function sectionLabel(line: string): string | null {
  const l = LABEL.exec(line);
  if (l) return l[1];
  const h = HEADING.exec(line);
  return h ? h[1].replace(/\*\*/g, "").replace(/:$/, "") : null;
}

export default function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r/g, "").split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const label = sectionLabel(line.trim());
    if (label) {
      out.push(<div key={i} className="mt-3 text-[11px] font-semibold uppercase tracking-wider text-ai first:mt-0">{label}</div>);
      i++; continue;
    }
    if (FOOTNOTE.test(line.trim()) && !BULLET.test(line)) {
      out.push(<p key={i} className="mt-2 text-[11px] italic text-faint">{line.trim().replace(/^\*+|\*+$/g, "").replace(/^\(|\)$/g, "")}</p>);
      i++; continue;
    }
    if (BULLET.test(line) || NUMBERED.test(line)) {
      const ordered = NUMBERED.test(line) && !BULLET.test(line);
      const items: { depth: number; body: string }[] = [];
      while (i < lines.length && (BULLET.test(lines[i]) || NUMBERED.test(lines[i]))) {
        const m = (BULLET.exec(lines[i]) ?? NUMBERED.exec(lines[i]))!;
        items.push({ depth: m[1].length >= 2 ? 1 : 0, body: m[2] });
        i++;
      }
      const List = ordered ? "ol" : "ul";
      out.push(
        <List key={`l${i}`} className={ordered ? "my-1.5 list-decimal space-y-1 pl-5" : "my-1.5 space-y-1"}>
          {items.map((it, j) => ordered ? <li key={j} className="pl-0.5">{inline(it.body, `${i}-${j}`)}</li> : (
            <li key={j} className={`flex gap-2 ${it.depth ? "ml-4" : ""}`}>
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-faint" />
              <span className="min-w-0">{inline(it.body, `${i}-${j}`)}</span>
            </li>
          ))}
        </List>,
      );
      continue;
    }
    // paragraph: merge consecutive plain lines
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !BULLET.test(lines[i]) && !NUMBERED.test(lines[i]) && !LABEL.test(lines[i].trim()) && !HEADING.test(lines[i].trim())) { para.push(lines[i].trim()); i++; }
    out.push(<p key={`p${i}`} className="mt-2 first:mt-0">{inline(para.join(" "), `p${i}`)}</p>);
  }
  return <div className="space-y-0 text-[13.5px] leading-relaxed text-ink">{out}</div>;
}

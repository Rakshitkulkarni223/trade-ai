import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { deleteConversation, listConversations, renameConversation, type ConversationSummary } from "../../api/ai";
import { cx, timeAgo } from "../../lib/format";

const DAY = 86400;
/** Today / Yesterday / Previous 7 days / Older, by the viewer's local calendar day. */
function bucket(ts: number): string {
  const midnight = new Date(); midnight.setHours(0, 0, 0, 0);
  const startToday = midnight.getTime() / 1000;
  if (ts >= startToday) return "Today";
  if (ts >= startToday - DAY) return "Yesterday";
  if (ts >= startToday - 7 * DAY) return "Previous 7 days";
  return "Older";
}
const ORDER = ["Today", "Yesterday", "Previous 7 days", "Older"];

/** Saved conversations, newest first, grouped by day: open, rename, delete, or start a new chat. */
export default function ChatHistory({ activeId, onOpen, onNew, onDeleted }: {
  activeId: number | null; onOpen: (id: number) => void; onNew: () => void; onDeleted: (id: number) => void;
}) {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["conversations"], queryFn: listConversations, staleTime: 0 });
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [confirm, setConfirm] = useState<number | null>(null);
  const [opening, setOpening] = useState<number | null>(null);
  const edit = useRef<HTMLInputElement>(null);

  const groups = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const rows = (list.data?.conversations ?? []).filter((c) => !needle || `${c.title} ${c.symbol}`.toLowerCase().includes(needle));
    const by = new Map<string, ConversationSummary[]>();
    rows.forEach((c) => { const k = bucket(c.updated_at); by.set(k, [...(by.get(k) ?? []), c]); });
    return ORDER.filter((k) => by.has(k)).map((k) => [k, by.get(k)!] as const);
  }, [list.data, q]);

  const refresh = () => qc.invalidateQueries({ queryKey: ["conversations"] });
  const save = async (id: number) => {
    const t = draft.trim();
    setEditing(null);
    if (t) { await renameConversation(id, t); refresh(); }
  };
  const remove = async (id: number) => { setConfirm(null); await deleteConversation(id); onDeleted(id); refresh(); };
  const open = async (id: number) => { setOpening(id); try { await onOpen(id); } finally { setOpening(null); } };
  const total = list.data?.conversations.length ?? 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <button onClick={onNew} className="btn-ai mb-3 w-full gap-2 !py-2.5">
        <span aria-hidden className="text-lg leading-none">＋</span>New chat
      </button>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search conversations…" className="input mb-3 !py-2" aria-label="Search conversations" />

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {list.isPending && <p className="px-2 py-6 text-center text-xs text-faint">Loading…</p>}
        {list.error && <p className="px-2 py-6 text-center text-xs text-down">Couldn't load your history.</p>}
        {!list.isPending && total === 0 && (
          <p className="px-3 py-8 text-center text-xs leading-relaxed text-faint">No conversations yet. Ask the copilot something and it will be saved here.</p>
        )}
        {!list.isPending && total > 0 && groups.length === 0 && <p className="px-2 py-6 text-center text-xs text-faint">Nothing matches “{q}”.</p>}

        {groups.map(([label, rows]) => (
          <section key={label} className="mb-3">
            <h4 className="px-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-faint">{label}</h4>
            <ul className="space-y-0.5">
              {rows.map((c) => {
                const active = c.id === activeId;
                return (
                  <li key={c.id} className={cx("group relative rounded-xl transition", active ? "bg-ai/15 ring-1 ring-ai/40" : "hover:bg-raised")}>
                    {editing === c.id ? (
                      <input ref={edit} autoFocus value={draft} maxLength={120} onChange={(e) => setDraft(e.target.value)} onBlur={() => save(c.id)}
                        onKeyDown={(e) => { if (e.key === "Enter") save(c.id); if (e.key === "Escape") setEditing(null); }}
                        className="input m-1 !w-[calc(100%-0.5rem)] !py-1.5" aria-label="Conversation title" />
                    ) : confirm === c.id ? (
                      <div className="flex items-center justify-between gap-2 px-3 py-2.5 text-xs">
                        <span className="text-mute">Delete this conversation?</span>
                        <span className="flex gap-1.5">
                          <button onClick={() => remove(c.id)} className="rounded-md bg-down/20 px-2 py-1 font-semibold text-down hover:bg-down/30">Delete</button>
                          <button onClick={() => setConfirm(null)} className="rounded-md bg-raised px-2 py-1 text-mute hover:text-ink">Cancel</button>
                        </span>
                      </div>
                    ) : (
                      <>
                        <button onClick={() => open(c.id)} disabled={opening !== null} className="block w-full px-3 py-2.5 pr-16 text-left">
                          <span className={cx("block truncate text-[13px]", active ? "font-semibold text-ink" : "text-ink")}>{c.title}</span>
                          <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-faint">
                            <span className="rounded bg-bg px-1 py-px font-medium text-mute">{c.symbol}</span>
                            <span>{c.timeframe}</span><span>·</span><span>{timeAgo(c.updated_at)}</span>
                            {opening === c.id && <span className="text-ai">opening…</span>}
                          </span>
                        </button>
                        <span className="absolute right-1.5 top-1.5 flex gap-0.5 opacity-0 transition focus-within:opacity-100 group-hover:opacity-100 max-md:opacity-100">
                          <button onClick={() => { setDraft(c.title); setEditing(c.id); }} aria-label={`Rename ${c.title}`} title="Rename"
                            className="grid h-7 w-7 place-items-center rounded-lg text-faint hover:bg-bg hover:text-ink">
                            <svg aria-hidden viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></svg>
                          </button>
                          <button onClick={() => setConfirm(c.id)} aria-label={`Delete ${c.title}`} title="Delete"
                            className="grid h-7 w-7 place-items-center rounded-lg text-faint hover:bg-bg hover:text-down">
                            <svg aria-hidden viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" /></svg>
                          </button>
                        </span>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

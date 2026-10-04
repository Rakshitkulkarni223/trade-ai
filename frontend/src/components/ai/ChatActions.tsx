import { cx } from "../../lib/format";

const Icon = ({ d }: { d: string }) => (
  <svg aria-hidden viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

/** The two controls every chat panel has: start a new chat, and browse the history. */
export default function ChatActions({ historyOpen, onNew, onToggleHistory }: { historyOpen: boolean; onNew: () => void; onToggleHistory: () => void }) {
  const base = "grid h-9 w-9 place-items-center rounded-xl border transition active:scale-95";
  return (
    <div className="flex items-center gap-1.5">
      <button onClick={onNew} title="New chat" aria-label="New chat" className={cx(base, "border-line bg-raised text-mute hover:border-ai/60 hover:text-ink")}>
        <Icon d="M12 5v14M5 12h14" />
      </button>
      <button onClick={onToggleHistory} title="Chat history" aria-label="Chat history" aria-pressed={historyOpen}
        className={cx(base, historyOpen ? "border-ai/60 bg-ai/15 text-ink" : "border-line bg-raised text-mute hover:border-ai/60 hover:text-ink")}>
        <Icon d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5M12 8v4l3 2" />
      </button>
    </div>
  );
}

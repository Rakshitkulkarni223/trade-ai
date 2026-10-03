import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useWorkspace } from "../../store/useWorkspace";
import AICopilot from "../ai/AICopilot";
import SymbolSearch from "../market/SymbolSearch";
import { cx } from "../../lib/format";

const NAV = [
  { to: "/", label: "Discover", icon: "M3 11 12 3l9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" },
  { to: "/markets", label: "Markets", icon: "M4 20V10m6 10V4m6 16v-7m4 7H2" },
  { to: "/chart", label: "Chart", icon: "M3 17l5-6 4 4 8-10" },
  { to: "/watchlist", label: "Watchlist", icon: "m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z" },
  { to: "/screener", label: "Screener", icon: "M3 5h18l-7 8v6l-4 2v-8z" },
  { to: "/lab", label: "AI Lab", icon: "M9 3h6m-5 0v6L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-10V3" },
  { to: "/ai", label: "AI Workspace", icon: "M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" },
  { to: "/paper", label: "Paper Analysis", icon: "M7 3h8l4 4v14H7zM15 3v4h4M10 12h6M10 16h6" },
];
const MOBILE = ["/", "/markets", "/chart", "/watchlist", "/lab"];

const Icon = ({ d }: { d: string }) => (
  <svg className="h-[18px] w-[18px] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

export default function AppShell() {
  const { aiOpen, setAiOpen, symbol, timeframe } = useWorkspace();
  const loc = useLocation();
  const [more, setMore] = useState(false);
  const onChart = loc.pathname.startsWith("/chart");
  const onAiPage = loc.pathname === "/ai";

  return (
    <div className="flex h-full">
      {/* sidebar: desktop */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-line bg-panel/60 p-3 lg:flex">
        <div className="mb-5 flex items-center gap-2 px-2 pt-1">
          <span className="grid h-8 w-8 place-items-center rounded-xl bg-ai text-white"><Icon d="M4 17l5-6 4 4 7-9" /></span>
          <span className="text-[15px] font-semibold tracking-tight">TradeAI</span>
        </div>
        <nav className="space-y-0.5">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"} className={({ isActive }) =>
              cx("flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition", isActive ? "bg-raised text-ink" : "text-mute hover:bg-raised/60 hover:text-ink")}>
              <Icon d={n.icon} />{n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto rounded-xl border border-line bg-raised/50 p-3 text-[11px] leading-snug text-faint">
          Analysis only. No broker, no orders. Information, not financial advice.
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-line bg-bg/80 px-4 py-2.5 backdrop-blur md:px-6">
          <span className="grid h-8 w-8 place-items-center rounded-xl bg-ai text-white lg:hidden"><Icon d="M4 17l5-6 4 4 7-9" /></span>
          <div className="max-w-xl flex-1"><SymbolSearch /></div>
          <button className={cx("btn-ai ml-auto !py-2", onChart && "xl:hidden", onAiPage && "hidden")} onClick={() => setAiOpen(true)} aria-label="Ask AI">
            <span className="text-base leading-none">✦</span><span className="hidden sm:inline">Ask AI</span>
          </button>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto pb-20 lg:pb-0">
          <Outlet />
        </main>
      </div>

      {/* AI as drawer (md+) or bottom sheet (mobile); docked on the chart page at xl */}
      {aiOpen && (
        <div className={cx("fixed inset-0 z-50", onChart && "xl:hidden")}>
          <button className="absolute inset-0 bg-black/60" onClick={() => setAiOpen(false)} aria-label="Close AI panel" />
          <div className={cx("absolute bg-panel p-4 shadow-2xl", "inset-x-0 bottom-0 h-[88vh] rounded-t-3xl border-t border-line safe-bottom",
            "md:inset-y-0 md:left-auto md:right-0 md:h-auto md:w-[440px] md:rounded-none md:rounded-l-3xl md:border-l md:border-t-0")}>
            <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-line md:hidden" />
            <AICopilot onClose={() => setAiOpen(false)} />
          </div>
        </div>
      )}

      {/* bottom navigation: mobile */}
      <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-panel/95 backdrop-blur safe-bottom lg:hidden">
        {NAV.filter((n) => MOBILE.includes(n.to)).map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === "/"} onClick={() => setMore(false)} className={({ isActive }) =>
            cx("flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px]", isActive ? "text-ai" : "text-faint")}>
            <Icon d={n.icon} />{n.label}
          </NavLink>
        ))}
        <button onClick={() => setMore(!more)} className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] text-faint"><Icon d="M5 12h.01M12 12h.01M19 12h.01" />More</button>
        {more && (
          <div className="absolute bottom-full right-2 mb-2 w-48 rounded-2xl border border-line bg-panel p-1.5 shadow-2xl">
            {NAV.filter((n) => !MOBILE.includes(n.to)).map((n) => (
              <NavLink key={n.to} to={n.to} onClick={() => setMore(false)} className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-mute hover:bg-raised hover:text-ink"><Icon d={n.icon} />{n.label}</NavLink>
            ))}
          </div>
        )}
      </nav>
      <span className="sr-only">{symbol} {timeframe}</span>
    </div>
  );
}

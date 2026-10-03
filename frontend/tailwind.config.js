/** Colours carry meaning (spec §46): green/red = direction, violet = AI, blue = liquidity,
 *  amber = FVG, purple = structure. Everything else is neutral. */
const c = (v) => `rgb(var(--${v}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: c("bg"), panel: c("panel"), raised: c("raised"), line: c("line"),
        ink: c("ink"), mute: c("mute"), faint: c("faint"),
        primary: c("primary"), up: c("up"), down: c("down"), warn: c("warn"),
        ai: c("ai"), liq: c("liq"), fvg: c("fvg"), struct: c("struct"),
      },
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: { glow: "0 0 0 1px rgb(var(--ai) / 0.35), 0 8px 32px -8px rgb(var(--ai) / 0.35)" },
    },
  },
  plugins: [],
};

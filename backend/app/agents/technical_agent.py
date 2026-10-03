from __future__ import annotations

from .common import Finding, Fmt


def run(a: dict, f: Fmt) -> Finding:
    i, price = a["indicators"], a["price"]
    facts = []
    if i["rsi"] is not None:
        zone = "overbought" if i["rsi"] >= 70 else "oversold" if i["rsi"] <= 30 else \
            "above 50, momentum leaning up" if i["rsi"] > 50 else "below 50, momentum leaning down"
        facts.append(f"RSI {i['rsi']:.1f} ({zone}).")
    if i["ema50"] is not None:
        side = "above" if price > i["ema50"] else "below"
        facts.append(f"Price is {side} EMA 50 ({f.price(i['ema50'])}); EMA 20 {f.price(i['ema20'])}; "
                     f"alignment is {i['ema_alignment']}.")
    if i["atr_pct"] is not None:
        facts.append(f"ATR is {f.price(i['atr'])} ({i['atr_pct']:.2f}% of price), which sets typical candle range.")
    if i["volume_ratio"] is not None:
        v = i["volume_ratio"]
        facts.append(f"Volume is {v:.2f}x its 20-bar average ({'above average' if v >= 1.2 else 'moderate' if v >= 0.8 else 'below average'}).")
    if i["price_vs_vwap_pct"] is not None:
        facts.append(f"Price is {i['price_vs_vwap_pct']:+.2f}% from the session VWAP ({f.price(i['vwap'])}).")
    if i["macd_hist"] is not None:
        facts.append(f"MACD histogram is {'positive' if i['macd_hist'] > 0 else 'negative'}.")
    return Finding("technical", "Technical snapshot", facts, i, [{"kind": "indicator", "id": "ema50"}])

import numpy as np
import pytest

from app.analysis import engine, fair_value_gap, indicators as ind, liquidity, market_structure, risk, signals
from app.analysis.candles import Candles
from tests.synthetic import build, zigzag


# ------------------------------------------------------------------ indicators
def test_sma_ema_rsi_basic():
    v = np.arange(1.0, 31.0)
    assert ind.sma(v, 5)[4] == pytest.approx(3.0)
    assert np.isnan(ind.sma(v, 5)[3])
    assert ind.ema(v, 5)[-1] > ind.ema(v, 5)[-2]
    assert ind.rsi(v, 14)[-1] == pytest.approx(100.0)          # only gains
    assert ind.rsi(v[::-1].copy(), 14)[-1] == pytest.approx(0.0, abs=1e-9)


def test_atr_constant_range():
    n = 40
    h, l, c = np.full(n, 11.0), np.full(n, 9.0), np.full(n, 10.0)
    assert ind.last(ind.atr(h, l, c, 14)) == pytest.approx(2.0)


def test_vwap_resets_each_day():
    c = build([(10, 11, 9, 10)] * 30, step=3600)
    v = ind.vwap(c)
    day_start = np.where(np.diff(c.t // 86400) != 0)[0] + 1
    assert len(day_start) >= 1
    i = int(day_start[0])
    assert v[i] == pytest.approx((11 + 9 + 10) / 3)


# ------------------------------------------------------------------ structure
def test_uptrend_labels_and_bos():
    c = build(zigzag([100, 110, 104, 115, 108, 120, 113, 126]))
    st = market_structure.analyse(c, k=3)
    labels = [s.label for s in st.swings]
    assert "HH" in labels and "HL" in labels
    assert st.trend == "bullish"
    assert st.last_event("BOS", "bullish") is not None
    assert st.last_event("CHoCH") is None


def test_choch_when_uptrend_loses_swing_low():
    c = build(zigzag([100, 110, 104, 115, 108, 120, 113, 126, 118, 105, 95]))
    st = market_structure.analyse(c, k=3)
    choch = st.last_event("CHoCH", "bearish")
    assert choch is not None
    assert st.trend == "bearish"


def test_no_lookahead_swing_confirmation():
    c = build(zigzag([100, 110, 104, 115]))
    for s in market_structure.detect_swings(c, 3):
        assert s.confirmed_at == s.index + 3


# ------------------------------------------------------------------ FVG
def test_bullish_fvg_and_mitigation_states():
    rows = [(10, 10.5, 9.5, 10.2), (10.2, 12.5, 10.1, 12.4), (12.4, 13.5, 11.5, 13.2)]   # gap 10.5 -> 11.5
    c = build(rows + [(13.2, 14, 12.5, 13.8)])
    g = fair_value_gap.detect(c)
    assert len(g) == 1 and g[0].type == "bullish"
    assert (g[0].low, g[0].high) == (10.5, 11.5)
    assert g[0].status == "unmitigated"

    partial = build(rows + [(13.2, 13.4, 11.0, 12.0)])
    assert fair_value_gap.detect(partial)[0].status == "partially_mitigated"

    filled = build(rows + [(13.2, 13.4, 10.0, 11.0)])
    assert fair_value_gap.detect(filled) == []                    # fully filled gaps are dropped


def test_bearish_fvg():
    c = build([(20, 20.5, 19.5, 19.6), (19.6, 19.7, 17.5, 17.6), (17.6, 18.5, 16.5, 16.8)])
    g = fair_value_gap.detect(c)
    assert g[0].type == "bearish" and (g[0].low, g[0].high) == (18.5, 19.5)


# ------------------------------------------------------------------ liquidity
def sweep_series(close_back: bool = True) -> Candles:
    base = [(100, 100.2, 99.8, 100)] * 30
    rows = base + zigzag([100, 110, 98, 108, 96, 106, 97, 104])
    low_close = 98.0 if close_back else 94.0
    rows.append((104, 104.5, 94.5, low_close))     # wick below the 96 swing low
    rows.append((low_close, 100.0, low_close - 0.2, 99.5 if close_back else 93.5))
    return build(rows)


def test_sweep_and_reclaim_detected():
    c = sweep_series(True)
    st = market_structure.analyse(c, 3)
    lm = liquidity.build(c, st, ind.atr(c.h, c.l, c.c), tf_seconds=3600)
    sw = lm.recent_sweep(len(c), side="sell_side")
    assert sw is not None and sw.reclaimed
    assert sw.price == pytest.approx(95.6, abs=0.5)             # the 96 swing low (wick adds width)


def test_close_beyond_level_is_a_break_not_a_sweep():
    c = sweep_series(False)
    st = market_structure.analyse(c, 3)
    lm = liquidity.build(c, st, ind.atr(c.h, c.l, c.c), tf_seconds=3600)
    n = len(c)
    # the final candles closed beyond the swing low: that is a break, not a sweep
    assert all((l.swept_index or 0) < n - 2 for l in lm.sweeps() if l.kind == "SSL")
    assert not any(l.kind == "SSL" and abs(l.price - 95.6) < 0.5 for l in lm.levels)


def test_previous_day_levels():
    rows = []
    for d in range(3):
        for h in range(24):
            spike = d == 1
            rows.append((100, 101 + (h == 5 and spike) * 3, 99 - (h == 7 and spike) * 2, 100.5))
    c = build(rows, start=86400 * 20000)
    lm = liquidity.build(c, market_structure.analyse(c), None, tf_seconds=3600)
    by = {l.kind: l for l in lm.levels}
    assert by["PDH"].price == pytest.approx(104)
    assert by["PDL"].price == pytest.approx(97)
    assert by["PDH"].status == "active"


def test_equal_highs_clustered():
    pts = [100, 110, 102, 110.02, 101, 110.01, 103, 108]
    c = build(zigzag(pts, width=0.05))
    lm = liquidity.build(c, market_structure.analyse(c), ind.atr(c.h, c.l, c.c), tf_seconds=3600)
    assert any(l.kind == "EQH" for l in lm.levels)


# ------------------------------------------------------------------ risk
def test_position_size_respects_risk_and_cap():
    s = risk.position_size(100_000, 1.0, entry=100, stop=98)
    assert s["quantity"] == pytest.approx(500)
    assert s["risk_amount"] == pytest.approx(1000)
    capped = risk.position_size(100_000, 1.0, entry=100, stop=99.9, max_position_pct=25)
    assert capped["capped"] and capped["position_pct"] <= 25.0
    assert risk.position_size(100_000, 1, 100, 100)["quantity"] == 0


# ------------------------------------------------------------------ engine / signals
def test_engine_refuses_thin_history():
    with pytest.raises(engine.InsufficientData):
        engine.analyse(build([(1, 2, 0.5, 1)] * 10), "X", "1h", 3600)


def test_engine_payload_shape_and_wait_has_scenario_only():
    c = build(zigzag([100, 103, 99, 104, 100, 102], per_leg=15, width=0.3))
    a = engine.analyse(c, "TEST", "1h", 3600)
    for key in ("signal", "plan", "context", "liquidity", "structure", "fvg", "series", "indicators"):
        assert key in a
    n = a["bars"]
    assert all(len(v) == n for v in a["series"].values())
    if a["signal"]["action"] == "WAIT":
        assert a["plan"]["status"] == "conditional"
        assert a["signal"]["waiting_for"]
    assert "win_probability" not in str(a).lower()


def _sweep_then_rally(steps: int):
    rows = [(x["o"], x["h"], x["l"], x["c"]) for x in sweep_series(True).to_rows()]
    return build(rows + zigzag([99.5, 99.5 + steps * 1.2], per_leg=steps, width=0.2))


def test_sweep_reversal_also_needs_the_supertrend_to_agree():
    """All four sweep/CHoCH/reclaim/extension conditions can be met, but without a Supertrend turn it stays WAIT."""
    a = engine.analyse(_sweep_then_rally(6), "TEST", "1h", 3600, cfg=risk.RiskConfig(max_stop_atr=10), now=1e12)
    sig = a["signal"]
    required = {w["label"]: w["done"] for w in sig["waiting_for"]}
    if a["supertrend"]["direction"] != "up":
        assert sig["action"] == "WAIT"
        assert required.get("Supertrend is up") is False
        assert all(done for label, done in required.items() if label != "Supertrend is up")
    assert a["context"]["liquidity"]["swept"] == "sell_side"


def test_wait_when_confirmation_missing_and_when_extended():
    wide = risk.RiskConfig(max_stop_atr=10)
    before_choch = engine.analyse(_sweep_then_rally(2), "TEST", "1h", 3600, cfg=wide, now=1e12)["signal"]
    assert before_choch["action"] == "WAIT"
    assert any(not w["done"] for w in before_choch["waiting_for"])
    chase = engine.analyse(_sweep_then_rally(12), "TEST", "1h", 3600, cfg=wide, now=1e12)["signal"]
    assert chase["action"] == "WAIT"
    assert chase["action"] == "WAIT"


def test_downtrend_gives_short_levels_on_correct_side():
    a = engine.analyse(build(zigzag([100, 90, 95, 85, 92, 80], per_leg=12)), "T", "1h", 3600)
    p = a["plan"]
    if p["direction"] == "short":
        assert p["targets"][0]["price"] < p["entry"] < p["stop"]


# ------------------------------------------------------------------ tracked-setup outcomes
def test_outcome_stop_wins_ties_and_targets_progress():
    from app.services.outcome import evaluate
    tg = [{"name": "TP1", "price": 102, "r": 1}, {"name": "TP2", "price": 104, "r": 2}, {"name": "TP3", "price": 106, "r": 3}]
    cs = lambda *rows: [{"t": 100 + i, "o": 0, "h": r[0], "l": r[1], "c": r[2], "v": 0} for i, r in enumerate(rows)]
    assert evaluate("long", 100, 98, tg, cs((101, 99.5, 100.5)), 99)["state"] == "open"
    both = evaluate("long", 100, 98, tg, cs((103, 97, 100)), 99)       # touches stop and TP1 in one candle
    assert both["state"] == "stopped" and both["realised_r"] == -1.0
    seq = evaluate("long", 100, 98, tg, cs((102.5, 99, 102), (104.5, 101, 104), (107, 103, 106)), 99)
    assert seq["state"] == "target_3" and seq["realised_r"] == 3.0
    short = evaluate("short", 100, 102, [{"name": "TP1", "price": 98, "r": 1}], cs((100.5, 97.5, 98)), 99)
    assert short["state"] == "target_1"


def test_wide_structural_stop_downgrades_to_wait():
    sig = {"action": "LONG", "items": [], "waiting_for": [], "evidence": {}, "summary": ""}
    signals.gate_wide_stop(sig, risk_atr=8.7, max_atr=4.0)
    assert sig["action"] == "WAIT"
    assert any(not w["done"] and "close enough" in w["label"] for w in sig["waiting_for"])
    assert sig["evidence"]["missing"][0]["key"] == "stop_distance"


def test_choch_counts_as_the_recent_break_for_a_pullback():
    """A bearish CHoCH is itself a bearish structure break; a pullback short must not insist on a separate BOS."""
    from app.analysis.market_structure import Structure, StructureEvent
    c = build([(100, 101, 99, 100)] * 60)
    st = Structure(trend="bearish", events=[StructureEvent("CHoCH", "bearish", 55, 99.0, 40)])
    snap = signals.Snapshot(price=100, ema20=100.2, ema50=102, rsi=45, atr=1.0, volume_ratio=1.0, vwap=100)
    items, _ = signals._pullback_items("short", c, snap, st, [])
    structure = next(i for i in items if i["key"] == "structure")
    assert structure["state"] == "pass" and "CHoCH" in structure["detail"]


# ------------------------------------------------------------------ supertrend
def _supertrend_series():
    # steady climb, sharp drop, steady recovery: expect one Sell then one Buy
    pts = [100, 130, 70, 120]
    return build(zigzag(pts, per_leg=25, width=0.5))


def test_supertrend_flips_once_per_reversal_and_alternates():
    c = _supertrend_series()
    trend, up, dn, buy, sell = ind.supertrend(c.h, c.l, c.c, 10, 3.0)
    flips = [("buy" if buy[i] else "sell", i) for i in range(len(c)) if buy[i] or sell[i]]
    kinds = [k for k, _ in flips]
    assert kinds and all(a != b for a, b in zip(kinds, kinds[1:])), kinds          # strictly alternating
    assert "sell" in kinds and "buy" in kinds
    assert trend[-1] == 1                                                         # recovered
    assert not (buy & sell).any()


def test_supertrend_lines_only_on_their_side_and_ratchet():
    c = _supertrend_series()
    trend, up, dn, buy, sell = ind.supertrend(c.h, c.l, c.c, 10, 3.0)
    ok = ~np.isnan(up)
    assert ((np.isnan(up)) | (trend == 1)).all() and ((np.isnan(dn)) | (trend == -1)).all()
    run = np.where(ok)[0]
    seg = up[run[run < (np.where(sell)[0][0] if sell.any() else len(c))]]
    assert (np.diff(seg) >= -1e-9).all()                                           # support only ever rises within a run


def test_supertrend_is_stable_under_a_changing_last_candle():
    """Closed-candle logic: the value on candle i never depends on candles after i."""
    c = _supertrend_series()
    full = ind.supertrend(c.h, c.l, c.c, 10, 3.0)
    part = ind.supertrend(c.h[:-5], c.l[:-5], c.c[:-5], 10, 3.0)
    assert (full[0][:-5] == part[0]).all()


# ------------------------------------------------------------------ closed candles, supertrend entries, signal memory
from app.analysis.signal_memory import SignalMemory


def _v_series():
    return build(zigzag([100, 130, 70, 125], per_leg=28, width=0.5), vol=100)


def _buy_index(c):
    _, _, _, buy, _ = ind.supertrend(c.h, c.l, c.c)
    return int(np.where(buy)[0][-1])


def test_fresh_supertrend_buy_gives_a_long_with_the_stop_under_the_line():
    c = _v_series()
    k = _buy_index(c) + 3
    a = engine.analyse(c.slice(0, k), "T", "1h", 3600, now=1e12)
    assert a["signal"]["action"] == "LONG" and a["signal"]["setup_type"] == "supertrend_flip"
    p = a["plan"]
    assert p["stop"] < p["entry"] < p["targets"][0]["price"]
    assert a["supertrend"]["signals"][-1]["type"] == "buy"


def test_no_entry_levels_in_the_ai_context_while_waiting():
    a = engine.analyse(build(zigzag([100, 103, 99, 104, 100, 102], per_leg=15, width=0.3)), "T", "1h", 3600, now=1e12)
    assert a["signal"]["action"] == "WAIT" and a["context"]["plan"] is None


def test_forming_candle_cannot_change_the_signal():
    c = _v_series()
    k = _buy_index(c) + 3
    base = c.slice(0, k)
    now = int(base.t[-1]) + 1800                       # half way through the last candle: it is still forming
    first = engine.analyse(base, "T", "1h", 3600, now=now)
    wild = base.slice(0, len(base))
    wild.h[-1], wild.l[-1], wild.c[-1] = wild.h[-1] + 40, wild.l[-1] - 60, wild.c[-1] - 55   # violent move inside the candle
    second = engine.analyse(wild, "T", "1h", 3600, now=now)
    for key in ("action", "setup_type", "summary"):
        assert first["signal"][key] == second["signal"][key]
    assert first["plan"]["entry"] == second["plan"]["entry"] and first["plan"]["stop"] == second["plan"]["stop"]
    assert second["price"] != first["price"]            # the live price is still reported, just not used to decide


def test_a_triggered_setup_keeps_its_levels_instead_of_flipping_back():
    c = _v_series()
    k = _buy_index(c) + 3
    mem = SignalMemory()
    first = engine.analyse(c.slice(0, k), "T", "1h", 3600, memory=mem, now=1e12)
    assert first["signal"]["action"] == "LONG"
    later = engine.analyse(c.slice(0, k + 3), "T", "1h", 3600, memory=mem, now=1e12)     # flip is now stale
    without = engine.analyse(c.slice(0, k + 3), "T", "1h", 3600, now=1e12)
    assert without["signal"]["action"] == "WAIT"                                         # the flip-flop being prevented
    assert later["signal"]["action"] == "LONG"
    assert later["plan"]["entry"] == first["plan"]["entry"] and later["plan"]["stop"] == first["plan"]["stop"]
    assert later["signal"]["state"]["since_t"] == first["signal"]["state"]["since_t"]


def test_memory_releases_when_the_stop_is_hit_and_does_not_flip_without_a_supertrend_turn():
    c = _v_series()
    k = _buy_index(c) + 3
    mem = SignalMemory()
    first = engine.analyse(c.slice(0, k), "T", "1h", 3600, memory=mem, now=1e12)
    stop = first["plan"]["stop"]
    rows = c.slice(0, k).to_rows()
    last_t = rows[-1]["t"]
    rows.append({"t": last_t + 3600, "o": stop + 5, "h": stop + 6, "l": stop - 30, "c": stop - 25, "v": 100})   # closes through the stop
    out = engine.analyse(Candles.from_rows(rows), "T", "1h", 3600, memory=mem, now=1e12)
    assert out["signal"]["action"] != "LONG" or out["plan"]["stop"] != stop
    assert mem.get("T|1h") is None or mem.get("T|1h")["direction"] != "long"


def test_memory_expires_after_its_time_limit():
    mem = SignalMemory(ttl_bars=5)
    c = build([(100, 101, 99, 100)] * 70)
    sig = {"action": "LONG", "considered_direction": "long", "setup_type": "x", "summary": "", "items": []}
    plan = {"entry": 100.0, "stop": 90.0, "targets": [{"name": "TP1", "price": 110.0, "r": 1.0}], "status": "active"}
    mem.apply("k", sig, plan, c.slice(0, 60), st_dir=1)
    held, _, state = mem.apply("k", {**sig, "action": "WAIT"}, plan, c.slice(0, 64), st_dir=1)
    assert held["action"] == "LONG" and state["held"]
    gone, _, state = mem.apply("k", {**sig, "action": "WAIT"}, plan, c.slice(0, 68), st_dir=1)
    assert gone["action"] == "WAIT" and state is None
    mem.apply("k", sig, plan, c.slice(0, 60), st_dir=1)
    flipped, _, state = mem.apply("k", {**sig, "action": "WAIT"}, plan, c.slice(0, 62), st_dir=-1)      # supertrend turned
    assert flipped["action"] == "WAIT" and state is None

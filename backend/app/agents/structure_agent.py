from __future__ import annotations

from .common import Finding, Fmt, bars_ago


def run(a: dict, f: Fmt) -> Finding:
    st, n, ts = a["structure"], a["bars"], a["series"]["t"]

    def ago(t):
        return (n - 1 - ts.index(t)) if t in ts else None

    facts, refs = [f"Structure trend is {st['trend']}."], []
    labels = [s["label"] for s in st["swings"] if s["label"]][-4:]
    if labels:
        facts.append("Recent swing sequence: " + ", ".join(labels) + ".")
    for key, name in (("last_bos", "BOS"), ("last_choch", "CHoCH")):
        e = st.get(key)
        if e:
            facts.append(f"Last {name}: {e['direction']}, price closed through {f.price(e['level'])} "
                         f"{bars_ago(ago(e['t']))}.")
            refs.append({"kind": "structure", "id": e["id"]})
    if not st.get("last_bos") and not st.get("last_choch"):
        facts.append("No structure break (BOS/CHoCH) has occurred in the loaded history.")
    return Finding("structure", f"{st['trend'].capitalize()} structure", facts, st, refs)

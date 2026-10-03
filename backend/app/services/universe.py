"""The instrument catalogue. Any Yahoo ticker or Binance USDT pair outside it still works."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

IST, ET = 19800, -18000


@dataclass(frozen=True)
class Instrument:
    symbol: str            # id used in URLs
    name: str
    category: str          # Indices | India | US | Crypto | Metals
    provider: str          # binance | yahoo
    currency: str
    tz_offset: int = 0     # seconds; used to find "previous day" boundaries
    lot_size: float = 1.0  # 0 = fractional quantity (crypto)

    def public(self) -> dict:
        d = asdict(self)
        d["currency_symbol"] = CURRENCY_SYMBOL.get(self.currency, "")
        return d


CURRENCY_SYMBOL = {"INR": "₹", "USD": "$", "USDT": "$", "EUR": "€", "GBP": "£"}


def _in(sym, name): return Instrument(f"{sym}.NS", name, "India", "yahoo", "INR", IST)
def _us(sym, name): return Instrument(sym, name, "US", "yahoo", "USD", ET)
def _cx(sym, name): return Instrument(sym, name, "Crypto", "binance", "USDT", 0, 0.0)


INSTRUMENTS: list[Instrument] = [
    Instrument("^NSEI", "NIFTY 50", "Indices", "yahoo", "INR", IST, 0.0),
    Instrument("^NSEBANK", "BANK NIFTY", "Indices", "yahoo", "INR", IST, 0.0),
    Instrument("^BSESN", "SENSEX", "Indices", "yahoo", "INR", IST, 0.0),
    Instrument("^GSPC", "S&P 500", "Indices", "yahoo", "USD", ET, 0.0),
    Instrument("^IXIC", "NASDAQ Composite", "Indices", "yahoo", "USD", ET, 0.0),
    Instrument("^DJI", "Dow Jones", "Indices", "yahoo", "USD", ET, 0.0),
    _in("RELIANCE", "Reliance Industries"), _in("TCS", "Tata Consultancy Services"),
    _in("INFY", "Infosys"), _in("HDFCBANK", "HDFC Bank"), _in("ICICIBANK", "ICICI Bank"),
    _in("SBIN", "State Bank of India"), _in("BHARTIARTL", "Bharti Airtel"), _in("ITC", "ITC"),
    _in("LT", "Larsen & Toubro"), _in("HINDUNILVR", "Hindustan Unilever"),
    _in("KOTAKBANK", "Kotak Mahindra Bank"), _in("AXISBANK", "Axis Bank"),
    _in("MARUTI", "Maruti Suzuki"), _in("SUNPHARMA", "Sun Pharma"), _in("WIPRO", "Wipro"),
    _in("BAJFINANCE", "Bajaj Finance"), _in("ADANIENT", "Adani Enterprises"),
    _in("ASIANPAINT", "Asian Paints"), _in("TITAN", "Titan Company"),
    _us("AAPL", "Apple"), _us("MSFT", "Microsoft"), _us("NVDA", "NVIDIA"), _us("GOOGL", "Alphabet"),
    _us("AMZN", "Amazon"), _us("META", "Meta Platforms"), _us("TSLA", "Tesla"), _us("AMD", "AMD"),
    _us("NFLX", "Netflix"), _us("JPM", "JPMorgan Chase"),
    _cx("BTCUSDT", "Bitcoin"), _cx("ETHUSDT", "Ethereum"), _cx("SOLUSDT", "Solana"),
    _cx("BNBUSDT", "BNB"), _cx("XRPUSDT", "XRP"), _cx("ADAUSDT", "Cardano"), _cx("DOGEUSDT", "Dogecoin"),
    Instrument("GC=F", "Gold", "Metals", "yahoo", "USD", ET, 0.0),
    Instrument("SI=F", "Silver", "Metals", "yahoo", "USD", ET, 0.0),
    Instrument("HG=F", "Copper", "Metals", "yahoo", "USD", ET, 0.0),
]
_BY_SYMBOL = {i.symbol.upper(): i for i in INSTRUMENTS}

CATEGORY_LABELS = {"Indices": "Indices", "India": "Stocks — India", "US": "Stocks — US",
                   "Crypto": "Crypto", "Metals": "Metals"}


def lookup(symbol: str) -> Optional[Instrument]:
    return _BY_SYMBOL.get(symbol.upper())


def resolve(symbol: str) -> Instrument:
    """Catalogue entry, or a best-effort custom instrument for an unlisted ticker."""
    known = lookup(symbol)
    if known:
        return known
    s = symbol.upper()
    if s.endswith("USDT") and len(s) > 4:
        return Instrument(s, s, "Crypto", "binance", "USDT", 0, 0.0)
    tz = IST if s.endswith((".NS", ".BO")) else ET
    cur = "INR" if s.endswith((".NS", ".BO")) else "USD"
    return Instrument(s, s, "India" if cur == "INR" else "US", "yahoo", cur, tz)


def search(q: str, limit: int = 12) -> list[Instrument]:
    q = q.strip().lower()
    if not q:
        return INSTRUMENTS[:limit]
    scored = []
    for i in INSTRUMENTS:
        sym, name = i.symbol.lower(), i.name.lower()
        if sym == q or sym.replace(".ns", "") == q:
            rank = 0
        elif sym.startswith(q) or name.startswith(q):
            rank = 1
        elif q in sym or q in name:
            rank = 2
        else:
            continue
        scored.append((rank, i.symbol, i))
    scored.sort(key=lambda x: x[:2])
    return [x[2] for x in scored[:limit]]


MARKETS = {"India": ["India"], "US": ["US"], "Crypto": ["Crypto"], "Indices": ["Indices"], "Metals": ["Metals"],
           "All": ["India", "US", "Crypto", "Indices", "Metals"]}


def by_market(market: str) -> list[Instrument]:
    cats = MARKETS.get(market, MARKETS["All"])
    return [i for i in INSTRUMENTS if i.category in cats]

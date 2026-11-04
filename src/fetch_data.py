"""Data collection utilities for the oil event-hedging project.

All sources are free and need no API key. Verified Nov 3, 2026.

Usage examples:
    python fetch_data.py polymarket-search "strait of hormuz"
    python fetch_data.py polymarket-history 27199 --fidelity 1440
    python fetch_data.py polymarket-history 27199 --fidelity 60 --start 2025-06-10 --end 2025-07-01
    python fetch_data.py kalshi-candles KXEIACRUDEW KXEIACRUDEW-26OCT28-T418 --period 60
    python fetch_data.py yahoo CL=F --interval 1d --range 3y
    python fetch_data.py ovx
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"


def get(url, as_json=True):
    r = subprocess.run(["curl", "-sL", "--max-time", "60", "-A", UA, url],
                       capture_output=True)
    out = r.stdout.decode("utf-8", errors="replace")
    return json.loads(out) if as_json else out


def ts(date_str):
    return int(dt.datetime.fromisoformat(date_str).replace(tzinfo=dt.timezone.utc).timestamp())


def polymarket_search(query, limit=20):
    """Search events; returns the raw search payload."""
    from urllib.parse import quote
    return get(f"{GAMMA}/public-search?q={quote(query)}&limit_per_type={limit}")


def polymarket_event(event_id):
    return get(f"{GAMMA}/events/{event_id}")


def polymarket_token(event_id, market_index=0, outcome_index=0):
    """First CLOB token id (YES by default) of a market in an event."""
    e = polymarket_event(event_id)
    m = e["markets"][market_index]
    return json.loads(m["clobTokenIds"])[outcome_index], e.get("title", "")


def polymarket_history(token, fidelity=1440, start=None, end=None):
    """Price history. Daily (1440): full history via interval=max.
    Intraday (60 or 10): needs start/end; fetched in 5-day windows."""
    if fidelity >= 1440 and not start:
        d = get(f"{CLOB}/prices-history?market={token}&interval=max&fidelity={fidelity}")
        return d.get("history", [])
    pts, t, t_end = [], ts(start), ts(end)
    while t < t_end:
        t2 = min(t + 5 * 86400, t_end)
        d = get(f"{CLOB}/prices-history?market={token}&startTs={t}&endTs={t2}&fidelity={fidelity}")
        pts += d.get("history", [])
        t = t2
        time.sleep(0.3)
    return pts


def kalshi_markets(series_ticker, status=None):
    out, cursor = [], ""
    while True:
        url = f"{KALSHI}/markets?series_ticker={series_ticker}&limit=100"
        if status:
            url += f"&status={status}"
        if cursor:
            url += f"&cursor={cursor}"
        d = get(url)
        mk = d.get("markets", [])
        out += mk
        cursor = d.get("cursor")
        if not cursor or not mk:
            return out


def kalshi_candles(series_ticker, market_ticker, start_ts, end_ts, period=60):
    d = get(f"{KALSHI}/series/{series_ticker}/markets/{market_ticker}/candlesticks"
            f"?start_ts={start_ts}&end_ts={end_ts}&period_interval={period}")
    return d.get("candlesticks", [])


def yahoo(symbol, interval="1d", rng="3y", start=None, end=None):
    if start:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
               f"?period1={ts(start)}&period2={ts(end)}&interval={interval}")
    else:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
               f"?range={rng}&interval={interval}")
    r = get(url)["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    return [{"t": t, "close": c} for t, c in zip(r["timestamp"], q["close"]) if c]


def ovx():
    """Full OVX history from CBOE (CSV text)."""
    return get("https://cdn.cboe.com/api/global/us_indices/daily_prices/OVX_History.csv",
               as_json=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("polymarket-search")
    s.add_argument("query")

    s = sub.add_parser("polymarket-history")
    s.add_argument("event_id")
    s.add_argument("--fidelity", type=int, default=1440)
    s.add_argument("--start")
    s.add_argument("--end")

    s = sub.add_parser("kalshi-candles")
    s.add_argument("series_ticker")
    s.add_argument("market_ticker")
    s.add_argument("--period", type=int, default=60)
    s.add_argument("--start")
    s.add_argument("--end")

    s = sub.add_parser("yahoo")
    s.add_argument("symbol")
    s.add_argument("--interval", default="1d")
    s.add_argument("--range", default="3y")
    s.add_argument("--start")
    s.add_argument("--end")

    sub.add_parser("ovx")

    a = p.parse_args()
    if a.cmd == "polymarket-search":
        d = polymarket_search(a.query)
        for e in d.get("events", []):
            print(e["id"], e.get("closed"), round(float(e.get("volume") or 0)), e.get("title"))
    elif a.cmd == "polymarket-history":
        tok, title = polymarket_token(a.event_id)
        h = polymarket_history(tok, a.fidelity, a.start, a.end)
        print(f"# {title} ({len(h)} points)", file=sys.stderr)
        json.dump({"event_id": a.event_id, "title": title, "history": h}, sys.stdout)
    elif a.cmd == "kalshi-candles":
        m = get(f"{KALSHI}/markets/{a.market_ticker}").get("market", {})
        start = ts(a.start) if a.start else int(dt.datetime.fromisoformat(
            m["open_time"].replace("Z", "+00:00")).timestamp())
        end = ts(a.end) if a.end else int(dt.datetime.fromisoformat(
            m["close_time"].replace("Z", "+00:00")).timestamp())
        json.dump(kalshi_candles(a.series_ticker, a.market_ticker, start, end, a.period), sys.stdout)
    elif a.cmd == "yahoo":
        json.dump(yahoo(a.symbol, a.interval, a.range, a.start, a.end), sys.stdout)
    elif a.cmd == "ovx":
        sys.stdout.write(ovx())


if __name__ == "__main__":
    main()

"""Hourly collector for the 2026 oil geopolitical crisis.

Snapshots, for every market in watchlist.json:
  - last trade price, best bid/ask and sizes, depth within 5 cents of mid
    (Polymarket CLOB order book)
and for the oil complex: WTI (CL=F), Brent (BZ=F) last price (Yahoo) and
OVX close (CBOE, daily series).

Appends to:
  data/live/polymarket_snapshots.csv   one row per market per run
  data/live/oil_snapshots.csv          one row per run
  data/live/books/YYYYMMDD_HH.json.gz  full top-of-book dump (audit trail)

Run once (for Task Scheduler):  python collect_live.py
Run forever (manual session):   python collect_live.py --loop 3600
A run that fails on one market continues with the others; errors go to
data/live/collector.log.
"""
import argparse
import csv
import datetime as dt
import gzip
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIVE = os.path.join(ROOT, "data", "live")
BOOKS = os.path.join(LIVE, "books")
LOG = os.path.join(LIVE, "collector.log")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def get(url, as_json=True):
    r = subprocess.run(["curl", "-sL", "--max-time", "30", "-A", UA, url],
                       capture_output=True)
    out = r.stdout.decode("utf-8", errors="replace")
    return json.loads(out) if as_json else out


def log(msg):
    line = f"{dt.datetime.now(dt.timezone.utc).isoformat()} {msg}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def depth_within(levels, mid, cents=0.05):
    """Sum of share size on levels priced within `cents` of mid."""
    tot = 0.0
    for lv in levels or []:
        p, s = float(lv["price"]), float(lv["size"])
        if abs(p - mid) <= cents:
            tot += s
    return round(tot, 1)


def snapshot_polymarket(watchlist, now_iso):
    rows, books_dump = [], {}
    for m in watchlist:
        tok = m["yes_token"]
        try:
            book = get(f"https://clob.polymarket.com/book?token_id={tok}")
            bids = sorted(book.get("bids") or [], key=lambda x: float(x["price"]), reverse=True)
            asks = sorted(book.get("asks") or [], key=lambda x: float(x["price"]))
            bb = float(bids[0]["price"]) if bids else None
            ba = float(asks[0]["price"]) if asks else None
            mid = round((bb + ba) / 2, 4) if bb is not None and ba is not None else None
            last = get(f"https://clob.polymarket.com/last-trade-price?token_id={tok}")
            rows.append({
                "ts_utc": now_iso,
                "event_id": m["event_id"],
                "question": m["question"],
                "yes_token": tok,
                "last": last.get("price"),
                "best_bid": bb,
                "bid_size": float(bids[0]["size"]) if bids else None,
                "best_ask": ba,
                "ask_size": float(asks[0]["size"]) if asks else None,
                "mid": mid,
                "spread": round(ba - bb, 4) if bb is not None and ba is not None else None,
                "depth_5c_bid": depth_within(bids, mid) if mid else None,
                "depth_5c_ask": depth_within(asks, mid) if mid else None,
            })
            books_dump[tok] = {"q": m["question"], "bids": bids[:10], "asks": asks[:10]}
        except Exception as e:
            log(f"polymarket {m['market_id']} {m['question'][:40]!r}: {e}")
        time.sleep(0.2)
    return rows, books_dump


def snapshot_oil(now_iso):
    row = {"ts_utc": now_iso, "wti": None, "brent": None, "ovx": None, "ovx_date": None}
    for sym, key in [("CL%3DF", "wti"), ("BZ%3DF", "brent")]:
        try:
            d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=5m")
            meta = d["chart"]["result"][0]["meta"]
            row[key] = meta.get("regularMarketPrice")
        except Exception as e:
            log(f"yahoo {key}: {e}")
    try:
        txt = get("https://cdn.cboe.com/api/global/us_indices/daily_prices/OVX_History.csv",
                  as_json=False)
        last = [ln for ln in txt.strip().splitlines() if ln and ln[0].isdigit()][-1]
        d8, v = last.split(",")
        row["ovx"], row["ovx_date"] = float(v), d8
    except Exception as e:
        log(f"ovx: {e}")
    return row


def append_csv(path, rows):
    if not rows:
        return
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new:
            w.writeheader()
        w.writerows(rows)


def run_once():
    os.makedirs(BOOKS, exist_ok=True)
    watchlist = json.load(open(os.path.join(HERE, "watchlist.json"), encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, books = snapshot_polymarket(watchlist, now_iso)
    append_csv(os.path.join(LIVE, "polymarket_snapshots.csv"), rows)
    append_csv(os.path.join(LIVE, "oil_snapshots.csv"), [snapshot_oil(now_iso)])
    with gzip.open(os.path.join(BOOKS, now.strftime("%Y%m%d_%H%M") + ".json.gz"),
                   "wt", encoding="utf-8") as f:
        json.dump({"ts_utc": now_iso, "books": books}, f)
    log(f"ok: {len(rows)}/{len(watchlist)} markets")
    print(f"{now_iso} snapshot: {len(rows)}/{len(watchlist)} markets")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--loop", type=int, metavar="SECONDS",
                   help="run forever, sleeping SECONDS between snapshots")
    a = p.parse_args()
    if a.loop:
        while True:
            try:
                run_once()
            except Exception as e:
                log(f"run failed: {e}")
                print("run failed:", e, file=sys.stderr)
            time.sleep(a.loop)
    else:
        run_once()


if __name__ == "__main__":
    main()

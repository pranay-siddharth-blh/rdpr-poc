"""Ping each app's /health endpoint every 10 seconds to keep it warm.

Usage:
  python keep_alive.py                                   # http://127.0.0.1:8000/health
  python keep_alive.py http://127.0.0.1:8000/health http://127.0.0.1:8001/health
  python keep_alive.py --interval 10 <url> [<url> ...]
Stop with Ctrl+C.
"""
import argparse
import time
import urllib.request
from datetime import datetime

DEFAULT_URLS = ["http://127.0.0.1:8000/health"]


def ping(url: str) -> str:
    start = time.time()
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return f"{resp.status} OK  {(time.time() - start) * 1000:.0f} ms"
    except Exception as exc:
        return f"FAIL ({exc})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs="*", default=DEFAULT_URLS)
    parser.add_argument("--interval", type=float, default=10)
    args = parser.parse_args()
    print(f"Pinging {len(args.urls)} app(s) every {args.interval:g}s - Ctrl+C to stop")
    while True:
        for url in args.urls:
            print(f"{datetime.now():%H:%M:%S}  {url}  {ping(url)}", flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")

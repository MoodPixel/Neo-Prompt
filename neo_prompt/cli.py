"""Launch isolated Neo Prompt on loopback, then open its browser interface."""
from __future__ import annotations

import argparse
import threading
import webbrowser
import sys

import uvicorn

from .settings import DATA_DIR, HOST, PORT
from .server_logging import build_log_config


def main():
    parser = argparse.ArgumentParser(description="Start independent Neo Prompt local workspace")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    url = f"http://{HOST}:{args.port}"
    print(f"Neo Prompt: {url} (Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        threading.Timer(1.6, lambda: webbrowser.open(url)).start()
    try:
        log_config = build_log_config(DATA_DIR)
    except OSError as exc:
        # A full/unwritable disk should not stop the user from opening the app.
        print(f"[Neo Prompt] Warning: Could not create log folder: {exc}", file=sys.stderr)
        print("[Neo Prompt] Request logging disabled; errors stay visible here.", file=sys.stderr)
        uvicorn.run("neo_prompt.api:app", host=HOST, port=args.port,
                    log_level="info", access_log=False, proxy_headers=False)
        return
    print(f"[Neo Prompt] HTTP logs: {DATA_DIR / 'logs'}", flush=True)
    uvicorn.run("neo_prompt.api:app", host=HOST, port=args.port,
                log_level="info", log_config=log_config, proxy_headers=False)


if __name__ == "__main__":
    main()

"""Launch isolated Neo Prompt on loopback, then open its browser interface."""
from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from .settings import HOST, PORT


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
    uvicorn.run("neo_prompt.api:app", host=HOST, port=args.port, log_level="info", proxy_headers=False)


if __name__ == "__main__":
    main()

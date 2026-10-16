"""App-local paths and server settings. No dependencies on other Neo applications."""
from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("NEO_PROMPT_DATA_DIR") or APP_ROOT / "neo_prompt_data").expanduser().resolve()
HOST = "127.0.0.1"
PORT = int(os.environ.get("NEO_PROMPT_PORT", "7891"))

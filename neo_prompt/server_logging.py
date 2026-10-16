"""Neo Prompt's local server log configuration.

Keep the Windows launcher useful while retaining bounded HTTP diagnostics in the
app-owned data directory. Do not capture response bodies, prompts or query values.
"""
from __future__ import annotations

from copy import deepcopy
import logging
from pathlib import Path
from typing import Any

from uvicorn.config import LOGGING_CONFIG


LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 3


class SafeAccessLogFilter(logging.Filter):
    """Remove URL queries from Uvicorn's positional HTTP access arguments.

    AccessLogMiddleware passes (client, method, path?query, version, status).
    Only the request target is modified; status codes and paths remain useful.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) == 5:
            client, method, target, http_version, status = args
            if isinstance(target, str):
                path = target.partition("?")[0]
                # Avoid multi-line log injection and pathological request targets.
                path = "".join(c if c.isprintable() else "?" for c in path)[:2048]
                record.args = (client, method, path, http_version, status)
        return True


def build_log_config(data_dir: Path) -> dict[str, Any]:
    """Create rotating access/server files and console-only server status.

    Does not alter the global/root Python logger or application API middleware.
    The data root can be overridden through NEO_PROMPT_DATA_DIR, as before.
    """
    logs = Path(data_dir) / "logs"
    logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Verify both files are writable before Uvicorn starts. With delayed file
    # handlers, this would otherwise fail during the first logged request.
    for filename in ("access.log", "server.log"):
        with (logs / filename).open("a", encoding="utf-8"):
            pass

    config = deepcopy(LOGGING_CONFIG)
    config.setdefault("filters", {})["safe_neo_access"] = {
        "()": "neo_prompt.server_logging.SafeAccessLogFilter",
    }
    config["formatters"]["neo_file"] = {
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }
    shared = {
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "neo_file",
        "maxBytes": LOG_MAX_BYTES,
        "backupCount": LOG_BACKUPS,
        "encoding": "utf-8",
        "delay": True,
    }
    config["handlers"]["neo_access_file"] = {
        **shared,
        "filename": str(logs / "access.log"),
        "filters": ["safe_neo_access"],
    }
    config["handlers"]["neo_server_file"] = {
        **shared,
        "filename": str(logs / "server.log"),
    }
    # Errors/startup continue to appear in the console AND go to server.log.
    config["loggers"]["uvicorn"]["handlers"] = ["default", "neo_server_file"]
    # Browser requests only go to access.log; no more hundreds of GET lines.
    config["loggers"]["uvicorn.access"]["handlers"] = ["neo_access_file"]
    config["loggers"]["uvicorn.access"]["propagate"] = False
    return config

"""Read-only connection probes against explicitly selected *loopback* inference servers.

Probing an API or model list never proves generation or vision capabilities.
"""
from __future__ import annotations

import ipaddress
import json
import hashlib
import re
from typing import Any
from urllib.parse import urlsplit

import httpx


class ConnectionConfigError(ValueError):
    pass


def normalize_endpoint(value: str) -> str:
    """No credentials, paths, redirects, remote IPs, or DNS hostnames for backend URLs."""
    raw = value.strip()
    try:
        parts = urlsplit(raw)
        if parts.scheme.lower() != "http" or not parts.hostname:
            raise ValueError()
        if parts.username or parts.password or parts.query or parts.fragment or parts.path not in ("", "/"):
            raise ValueError()
        hostname = parts.hostname.lower()
        if hostname != "localhost":
            address = ipaddress.ip_address(hostname)
            if not address.is_loopback:
                raise ValueError()
        if parts.port is None or not 1 <= parts.port <= 65535:
            raise ValueError()
        # Fix the address to loopback to avoid localhost DNS rebinding.
        normalized_host = "[::1]" if hostname == "::1" else "127.0.0.1"
        return f"http://{normalized_host}:{parts.port}"
    except (ValueError, TypeError):
        raise ConnectionConfigError("Only local HTTP backend URLs are supported, such as http://127.0.0.1:PORT (or localhost/::1); do not add paths, credentials or remote hosts.") from None


async def _small_json(client: httpx.AsyncClient, url: str) -> Any:
    """Bound network response size and duration; never follow redirects."""
    async with client.stream("GET", url, headers={"Accept": "application/json"}) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        count = 0
        async for part in response.aiter_bytes():
            count += len(part)
            if count > 512 * 1024:
                raise ValueError("Backend probe response exceeds 512 KB")
            chunks.append(part)
        return json.loads(b"".join(chunks))


async def inspect_kobold_model(endpoint: str, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
    """Best-effort *live* read-only model identification; no speculative capabilities.

    `/api/v1/model` is supported by KoboldCPP. A server may still refuse it.
    No user prompt is sent; no GGUF paths or model weights are fetched.
    """
    base = normalize_endpoint(endpoint)
    result = {'model': None, 'model_fingerprint': None, 'model_identity_state': 'unavailable'}
    try:
        timeout = httpx.Timeout(timeout_seconds, connect=min(1.0, timeout_seconds))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            payload = await _small_json(client, base + '/api/v1/model')
        if isinstance(payload, dict) and isinstance(payload.get('result'), str):
            original = payload['result'].strip()[:1024]
            model = re.split(r'[/\\]', original)[-1][:160]
            if model:
                result.update(model=model, model_fingerprint=hashlib.sha256(original.encode('utf-8')).hexdigest()[:16], model_identity_state='reported')
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, json.JSONDecodeError):
        pass
    return result


async def probe(kind: str, endpoint: str) -> dict[str, Any]:
    base = normalize_endpoint(endpoint)
    result: dict[str, Any] = {
        "reachable": False,
        "model": None,
        "message": "Not checked",
        "text_ready": "not_verified",
        "vision_ready": "not_verified",
        "qwen_pe_ready": "not_verified",
    }
    timeout = httpx.Timeout(3.5, connect=2.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False) as client:
            if kind == "comfyui":
                payload = await _small_json(client, base + "/system_stats")
                if not isinstance(payload, dict) or not isinstance(payload.get("system"), dict):
                    raise ValueError("ComfyUI /system_stats did not return a recognizable system object")
                result.update(reachable=True, message="ComfyUI responded. Use Detect installed models to check compatible LLM, VLM and Qwen PE nodes and models; verify with a real task.")
            elif kind == "koboldcpp":
                payload = await _small_json(client, base + "/api/v1/model")
                if not isinstance(payload, dict) or not isinstance(payload.get("result"), str):
                    raise ValueError("KoboldCPP /api/v1/model did not return a recognizable result")
                original = payload["result"].strip()[:1024]
                model = re.split(r'[/\\]', original)[-1][:160]
                result.update(reachable=True, model=model or None,
                              model_identity_state="reported" if model else "unavailable",
                              model_fingerprint=hashlib.sha256(original.encode("utf-8")).hexdigest()[:16] if model else None,
                              chat_template="not_exposed_by_probe", context_size="not_exposed_by_probe",
                              message="KoboldCPP reports its currently loaded model. Text and vision readiness require real requests; model changes are reflected on the next check.")
            else:
                raise ConnectionConfigError("Unsupported backend type")
    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            detail = f"HTTP {exc.response.status_code} from expected probe route"
        elif isinstance(exc, httpx.ConnectError):
            detail = "Connection refused or host unreachable"
        elif isinstance(exc, httpx.TimeoutException):
            detail = "Connection timed out"
        else:
            detail = "Backend did not return the expected JSON response"
        result["message"] = f"{detail}. Check the server type, port, and whether it is running."
    return result

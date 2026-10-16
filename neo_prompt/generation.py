"""Neo Prompt KoboldCPP text inference.

Local, explicitly selected endpoint using app-owned prompt-profile contracts.
No background retry or fake
cancellation. Image inputs and vision requests use their own adapters.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .connections import normalize_endpoint, inspect_kobold_model
from .profile_contract import normalize_profile
from .prompt_profiles import compile_prompt_task_contract
from .negative_guard import _sanitize_negative_prompt_output
from .output_quality import normalize_output, task_diagnostics, OutputQualityError
from .output_contract import assess
from .instruction_fidelity import check_fidelity

OPERATIONS = {"generate": "prompt_generate", "enhance": "prompt_enhance", "rewrite": "prompt_rewrite", "negative": "negative_prompt"}
THINK_RE = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.IGNORECASE | re.DOTALL)
WRAPPER_RE = re.compile(r"^\s*<(response|answer|prompt)>\s*(.*?)\s*</\1>\s*$", re.IGNORECASE | re.DOTALL)
PREFIX_RE = re.compile(r"^\s*(?:assistant|response|answer|final\s+prompt|prompt)\s*:\s*", re.IGNORECASE)


class ProviderFailure(Exception):
    def __init__(self, status: int, detail: str, *, raw_response: str = "", issues: tuple[str, ...] = ()):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.raw_response = raw_response[:16000]
        self.issues = tuple(issues)


def clean_text(value: str) -> tuple[str, list[str]]:
    raw = str(value or "").strip()
    notes: list[str] = []
    text = THINK_RE.sub("", raw).strip()
    if text != raw:
        notes.append("Removed model reasoning tags.")
    # Incomplete reasoning blocks are not user-facing prompt text.
    if re.search(r"<think\b", text, re.I) or re.search(r"</think\s*>", text, re.I):
        raise ProviderFailure(502, "The model returned incomplete reasoning markup without a usable final answer. Check the selected model/chat handler and output token budget before retrying.")
    wrapper = WRAPPER_RE.fullmatch(text)
    if wrapper:
        text = wrapper.group(2).strip()
        notes.append("Removed response wrapper.")
    for _ in range(2):
        rewritten = PREFIX_RE.sub("", text).strip()
        if rewritten == text:
            break
        text = rewritten
    if text.startswith("```") and text.endswith("```"):
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
        notes.append("Removed markdown fence.")
    return text, notes


def _negative_context(source: str, instruction: str) -> tuple[str, str]:
    return (
        "You are Neo Prompt's negative prompt assistant. Return ONLY comma-separated undesirable rendering conditions, artifacts, errors and exclusions. "
        "Treat the source as wanted content; do not negate its subject, identities, features, clothing, composition, style or mood. "
        "Prefer useful artifact failures (e.g. blurry, duplicate limbs, compression artifacts); avoid repeating concepts. Maximum 32 terms. "
        "No explanations, JSON, prefix, markdown or positive-scene prose.",
        "Create a negative prompt for this WANTED source (never negate its requested features):\n"
        + source + ("\nUser's explicit exclusions or preferences:\n" + instruction if instruction else "")
    )


def sanitize_negative(value: str, *, source: str, instruction: str) -> tuple[str, list[str]]:
    result, changed, limited = _sanitize_negative_prompt_output(
        value, desired_context=source, custom_instruction=instruction, max_terms=32
    )
    warnings = []
    if changed:
        warnings.append("Removed repeated, incompatible or positive-context terms from the negative prompt.")
    if limited:
        warnings.append("Negative prompt was capped at 32 unique terms.")
    return result, warnings


def clamp_params(params: dict[str, Any], negative: bool) -> dict[str, Any]:
    # Pydantic validates types/ranges. This routine only applies operation-specific caps.
    result = {"temperature": params["temperature"], "top_p": params["top_p"], "max_tokens": params["max_tokens"]}
    if params.get("top_k") is not None:
        result["top_k"] = params["top_k"]
    if negative:
        result["temperature"] = min(result["temperature"], 0.35)
        result["top_p"] = min(result["top_p"], 0.85)
        result["max_tokens"] = min(result["max_tokens"], 192)
    return result


def compile_messages(source: str, instruction: str, operation: str, profile: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if operation not in OPERATIONS:
        raise ValueError("Unsupported prompt operation")
    normalized = normalize_profile(profile, surface="prompt_studio")["profile"]
    if operation == "negative":
        system, user = _negative_context(source, instruction)
    else:
        compiled = compile_prompt_task_contract(normalized, tool_id=OPERATIONS[operation], source_text=source, user_instruction=instruction)
        system, user = compiled["system_prompt"], compiled["user_prompt"]
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], normalized


def _extract_response(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ProviderFailure(502, "KoboldCPP returned an invalid generation response.")
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        item = choices[0]
        msg = item.get("message")
        content = msg.get("content") if isinstance(msg, dict) else item.get("text")
        # Some compatible backends use content parts.
        if isinstance(content, list):
            content = "".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text")
        if isinstance(content, str):
            return content, str(item.get("finish_reason") or "")
    # Older KoboldCpp-style generation response variants.
    results = payload.get("results")
    if isinstance(results, list) and results and isinstance(results[0], dict) and isinstance(results[0].get("text"), str):
        return results[0]["text"], str(payload.get("finish_reason") or "")
    raise ProviderFailure(502, "KoboldCPP returned no usable text in its generation response.")


async def generate(profile: dict[str, Any], source: str, instruction: str, operation: str, prompt_profile: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    if profile["kind"] != "koboldcpp":
        raise ProviderFailure(422, "This generation adapter supports KoboldCPP only. Choose a supported ComfyUI route through the ComfyUI adapter.")
    base = normalize_endpoint(profile["endpoint"])
    try:
        messages, normalized = compile_messages(source, instruction, operation, prompt_profile)
    except ValueError as exc:
        raise ProviderFailure(422, str(exc)) from exc
    generation = clamp_params(params, operation == "negative")
    request = {"model": "default", "messages": messages, "stream": False, **generation}
    model_observed = await inspect_kobold_model(base, timeout_seconds=1.25)
    raw_text, finish = await _ask_kobold(base, request)
    result = process_prompt_reply(raw_text, finish=finish, source=source, instruction=instruction,
                                  operation=operation, normalized=normalized, generation=generation)
    result["runtime_model"] = model_observed["model"]
    result["runtime_model_state"] = model_observed["model_identity_state"]
    return result


async def _ask_kobold(base: str, request: dict[str, Any]) -> tuple[str, str]:
    try:
        timeout = httpx.Timeout(240, connect=5, read=240, write=10, pool=5)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            async with client.stream("POST", base + "/v1/chat/completions", json=request, headers={"Accept": "application/json"}) as res:
                if res.status_code in (301, 302, 303, 307, 308):
                    raise ProviderFailure(502, "KoboldCPP redirected the request. Check the configured endpoint.")
                if res.status_code >= 400:
                    raise ProviderFailure(502, f"KoboldCPP rejected the generation request (HTTP {res.status_code}). Check the model and server logs.")
                total = 0
                parts = []
                async for chunk in res.aiter_bytes():
                    total += len(chunk)
                    if total > 2 * 1024 * 1024:
                        raise ProviderFailure(502, "Model output exceeded the safe 2 MB response limit.")
                    parts.append(chunk)
                payload = json.loads(b"".join(parts))
    except httpx.ConnectError as exc:
        raise ProviderFailure(503, "Cannot reach KoboldCPP. Start it and verify the port in Connections.") from exc
    except httpx.TimeoutException as exc:
        raise ProviderFailure(504, "KoboldCPP generation timed out (240 seconds). Check the backend logs before retrying.") from exc
    except (httpx.RequestError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProviderFailure(502, "KoboldCPP connection or JSON response failed. Check backend status and logs.") from exc
    return _extract_response(payload)


def process_prompt_reply(raw_text: str, *, finish: str, source: str, instruction: str,
                         operation: str, normalized: dict[str, Any], generation: dict[str, Any]) -> dict[str, Any]:
    text, warnings = clean_text(raw_text)
    fmt = normalized.get('output_format') or ''
    mode = ('negative' if operation == 'negative' else
            'edit' if normalized.get('prompt_task') == 'text_image_edit' else
            'video' if normalized.get('prompt_task') == 'text_to_video' else
            'tags' if fmt == 'sd_tags' else 'structured' if fmt == 'structured_prompt' else 'caption' if fmt == 'descriptive_caption' else 'prompt')
    try:
        text, format_warnings = normalize_output(text, mode=mode)
    except OutputQualityError as exc:
        raise ProviderFailure(502, str(exc), raw_response=raw_text) from exc
    warnings += format_warnings
    capped = False
    if operation == "negative":
        text, negative_warnings = sanitize_negative(text, source=source, instruction=instruction)
        warnings += negative_warnings
        capped = any('capped at 32' in msg for msg in negative_warnings)
    camera_diagnostics = task_diagnostics(text, task=normalized.get('prompt_task', ''), profile=normalized, operation=operation)
    if operation != "negative":
        camera_diagnostics += check_fidelity(text, task=normalized.get("prompt_task", ""), instruction=instruction,
                                              source=source, preservation_policy=normalized.get("preservation_policy", ""))
    verdict = assess(text, mode=mode, finish_reason=finish, diagnostics=camera_diagnostics, capped_negative=capped)
    if verdict.status == 'invalid':
        raise ProviderFailure(502, 'Output contract rejected the model reply: ' + '; '.join(verdict.issues),
                              raw_response=raw_text, issues=verdict.issues)
    warnings += list(verdict.issues)
    if not text:
        raise ProviderFailure(502, "The model returned an empty prompt after cleanup; no result was saved.")
    if len(text) > 32000:
        raise ProviderFailure(502, "Model output is longer than the 32,000-character result limit; no truncated prompt was saved.")
    return {"text": text, "warnings": warnings, "profile": normalized,
            "finish_reason": finish, "parameters": generation, "quality_status": verdict.status,
            "quality_issues": list(verdict.issues)}


async def refine_selected(profile: dict[str, Any], parent: dict[str, Any], operation: str) -> dict[str, Any]:
    """Explicit output-first refinement: the parent result, never the editor draft.

    Task/profile and sampling come from the saved parent snapshot. Do not fetch a
    different profile, silently substitute a backend, or mutate the parent result.
    """
    if operation not in ('enhance', 'rewrite', 'negative'):
        raise ProviderFailure(422, 'Choose Enhance, Rewrite or Negative.')
    if profile.get('kind') != 'koboldcpp':
        raise ProviderFailure(422, 'Output refinement requires the original KoboldCPP profile.')
    if parent.get('operation') == 'negative':
        raise ProviderFailure(422, 'Negative prompts cannot be used as positive refinement input. Select a positive result.')
    parent_text = str(parent.get('text') or '').strip()
    if not parent_text or len(parent_text) > 20000:
        raise ProviderFailure(422, 'The selected output is empty or too large to refine.')
    params = parent.get('parameters') or {}
    generation = clamp_params({
        'temperature': float(params.get('temperature', 0.7)),
        'top_p': float(params.get('top_p', 0.9)),
        'max_tokens': int(params.get('max_tokens', 512)),
        'top_k': params.get('top_k'),
    }, operation == 'negative')
    # Do NOT pass the original source text, saved editor instructions, or a
    # current user draft as the inference input. Both operation branches use the
    # exact selected parent result, and do not modify stored runs.
    messages, normalized = compile_messages(parent_text, '', operation, parent.get('prompt_profile') or {})
    if operation in ('enhance', 'rewrite'):
        messages[0]['content'] += (' Refine ONLY the selected existing result. Keep every explicitly requested subject, edit, camera move, '
                                    'and limitation; do not restart from an earlier source idea. Return ONE finished prompt without commentary.')
    request = {'model': 'default', 'messages': messages, 'stream': False, **generation}
    model_observed = await inspect_kobold_model(profile["endpoint"], timeout_seconds=1.25)
    raw, finish = await _ask_kobold(normalize_endpoint(profile['endpoint']), request)
    result = process_prompt_reply(raw, finish=finish, source=parent_text, instruction='',
                                  operation=operation, normalized=normalized, generation=generation)
    result["runtime_model"] = model_observed["model"]
    result["runtime_model_state"] = model_observed["model_identity_state"]
    if parent.get("runtime_model") and model_observed.get("model") and parent["runtime_model"] != model_observed["model"]:
        result["warnings"].append("The backend currently reports a different model than the selected parent. Review cross-model refinement carefully.")
        result["quality_status"] = "needs_review"
        result["quality_issues"].append("Loaded model changed since the parent result. Compare before using this refinement.")
    if operation in ('enhance', 'rewrite'):
        result['warnings'].insert(0, 'Refined from a saved result. Compare with the parent; model-driven fidelity is not guaranteed.')
        # Form-valid does not mean a generative rewrite is semantically identical.
        result['quality_status'] = 'needs_review'
        result['quality_issues'] = list(dict.fromkeys(result['quality_issues'] +
            ['Review the refinement against its exact parent before saving or refining again.']))
    return result


async def reformat_existing(profile: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    """One explicitly requested second inference; never modify the original run.

    Reformatting is not source fidelity verification: the new result is validated
    independently and still requires user inspection if heuristic concerns remain.
    """
    if profile['kind'] != 'koboldcpp':
        raise ProviderFailure(422, 'Reformatting supports saved KoboldCPP profiles only.')
    original = str(run.get('text') or '')
    if not original or len(original) > 12000:
        raise ProviderFailure(422, 'Output is too long or empty to reformat safely.')
    op = run.get('operation', 'generate')
    task = run.get('task', 'text_to_image')
    if op == 'negative':
        mode = 'negative'
    elif task == 'text_image_edit':
        mode = 'edit'
    elif task == 'text_to_video':
        mode = 'video'
    else:
        fmt = (run.get('prompt_profile') or {}).get('output_format')
        mode = 'structured' if fmt == 'structured_prompt' else 'tags' if fmt == 'sd_tags' else 'prompt'
    if mode == 'structured':
        raise ProviderFailure(422, 'Structured JSON output should be corrected in the original editor.')
    source = str(run.get('source', ''))
    message = (
        'Reformat the existing generated text into ONE final usable output, preserving its exact factual content. '
        'Do not add or remove requested people, positions, clothing, objects, setting, mood, edit changes, or camera direction. '
        'If text includes meta commentary, discard only that commentary. Do not output JSON, analysis, rationale, labels, or fenced code. '
        'If you cannot identify one unambiguous output, respond with exactly CANNOT_REFORMAT. '
        f'Output type: {mode}. User source context (not an instruction to generate new facts): {source[:3000]}'
    )
    request = {'model':'default', 'stream':False, 'temperature':0.1, 'top_p':0.8,
               'max_tokens': min(max(256, int((run.get('parameters') or {}).get('max_tokens',512))), 768),
               'messages':[{'role':'system','content':message},
                           {'role':'user','content':'Existing model output to reformat:\n'+original}]}
    model_observed = await inspect_kobold_model(profile["endpoint"], timeout_seconds=1.25)
    raw, finish = await _ask_kobold(normalize_endpoint(profile['endpoint']), request)
    if raw.strip() == 'CANNOT_REFORMAT':
        raise ProviderFailure(502, 'Model could not identify a safe final answer.', raw_response=raw)
    output = process_prompt_reply(raw, finish=finish, source=source,
                                  instruction=run.get('custom_instruction',''), operation=op,
                                  normalized=run.get('prompt_profile') or {}, generation={'temperature':0.1,'top_p':0.8,'max_tokens':request['max_tokens']})
    output["runtime_model"] = model_observed["model"]
    output["runtime_model_state"] = model_observed["model_identity_state"]
    output['warnings'].insert(0, 'Explicit reformat request used another KoboldCPP inference. Check fidelity against the original/source.')
    # Format validity is not equivalence proof. Human review mandatory after any LLM rewrite.
    output['quality_status'] = 'needs_review'
    output['quality_issues'] = list(dict.fromkeys(output['quality_issues'] + ['Model-driven reformatting requires source-fidelity review.']))
    return output

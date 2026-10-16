"""conservative provider-output normalization and task-fit diagnostics.

Preserve model wording; never create unseen facts, invent a camera move, or silently
re-prompt a paid/expensive local model. Ambiguous structured replies fail closed.
"""
from __future__ import annotations

import json
import re
from typing import Any


class OutputQualityError(ValueError):
    pass


# Strictly final-answer fields; descriptive JSON fields such as background and
# mood must not be joined into a fabricated user instruction.
_FIELDS = {
    'edit': ('final_edit_instruction', 'edit_instruction', 'instruction', 'final_prompt', 'prompt', 'output_text', 'text'),
    'video': ('final_video_prompt', 'video_prompt', 'final_prompt', 'prompt', 'output_text', 'text'),
    'negative': ('negative_prompt', 'negative', 'exclusions', 'terms', 'final_prompt', 'prompt', 'text'),
    'caption': ('final_caption', 'caption', 'alt_text', 'final_prompt', 'prompt', 'output_text', 'text'),
    'tags': ('tags', 'keywords', 'final_prompt', 'prompt', 'text'),
    'prompt': ('final_prompt', 'prompt', 'output_prompt', 'output_text', 'text'),
    'structured': (),
}

_META_START = re.compile(
    r'^(?:here\s+(?:is|are)\s+(?:your|the|an?)\s+(?:final\s+)?(?:prompt|caption|instruction)\s*[:\-–—]\s*|'
    r'(?:the\s+)?(?:final\s+)?(?:prompt|caption|edit\s+instruction)\s*[:\-–—]\s*|'
    r'(?:the\s+)?(?:final\s+)?prompt\s+is\s*:\s*|'+
    r'the\s+prompt\s+for\s+this\s+image\s+generation\s+is\s+to\s+|'+
    r'the\s+edit\s+instruction\s+is\s*:\s*)', re.I)
_VIDEO_PREAMBLE = re.compile(
    r'^the\s+prompt\s+for\s+this\s+video\s+generation\s+(?:involves|describes|features)\s+', re.I)
_META_PARAGRAPH = re.compile(
    r'^(?:this\s+(?:prompt|caption|instruction)\s+(?:should|will|is\s+(?:designed|intended))\b|'
    r'(?:note|explanation|rationale)\s*[:\-])', re.I)
_META_INLINE = re.compile(
    r'\b(?:the\s+prompt\s+(?:for|requires|should)|this\s+prompt\s+(?:should|will)|'
    r'the\s+scene\s+should\s+depict|the\s+prompt\s+is\s+(?:about|intended))\b', re.I)
_FINAL_MARKER = re.compile(
    r'(?:^|\n)\s*(?:here\s+is\s+)?(?:the\s+)?final(?:\s+(?:image|video|edit))?\s+(?:prompt|instruction)\s*'
    r'(?:is\s*)?(?::|[–—])\s*', re.I)


def _text_candidate(value: Any, *, mode: str) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        if mode in ('negative', 'tags') and value and all(isinstance(v, str) for v in value):
            return ', '.join(v.strip() for v in value if v.strip())
        if len(value) == 1 and isinstance(value[0], str):
            return value[0].strip()
    raise OutputQualityError('The model returned multiple or unsupported structured answers. No result was saved; retry with one final prompt.')


def _extract_structured(raw: str, mode: str) -> tuple[str, bool]:
    if mode == 'structured' or not raw.startswith(('{', '[')):
        return raw, False
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError) as exc:
        # Not all text beginning with '[' is JSON: [wide shot] can be a tag.
        if raw.startswith('[') and not re.match(r'^\[\s*[\{"\d]', raw):
            return raw, False
        raise OutputQualityError('The model returned malformed structured output; it was not saved as a prompt. Retry generation.') from exc
    if isinstance(obj, dict):
        for field in _FIELDS[mode]:
            value = obj.get(field)
            if value is not None:
                selected = _text_candidate(value, mode=mode)
                if selected:
                    return selected, True
        raise OutputQualityError('The model returned JSON analysis without one identifiable final instruction. Nothing was saved; retry generation.')
    return _text_candidate(obj, mode=mode), True


def _unwrap_quotes(text: str) -> tuple[str, bool]:
    changed = False
    for _ in range(2):
        if len(text) >= 2 and (text[0], text[-1]) in {('\"', '\"'), ("'", "'"), ('“', '”'), ('‘', '’')}:
            text = text[1:-1].strip()
            changed = True
        else:
            break
    return text, changed


def normalize_output(raw: str, *, mode: str = 'prompt') -> tuple[str, list[str]]:
    """Convert explicit final answers only; never synthesize content from analysis."""
    if mode not in _FIELDS:
        raise ValueError('Unknown output task')
    text = str(raw or '').strip()
    warnings: list[str] = []
    if not text:
        return '', warnings
    if mode != 'structured' and re.search(r'```\s*json\s*[\r\n]', text, re.I) and not text.startswith('```'):
        raise OutputQualityError('Model mixed a prompt with an extra JSON block. No unambiguous final answer was saved.')
    if mode != 'structured' and re.search(r'(?:[.!?]\s+|\n)the\s+prompt\s*:', text, re.I):
        raise OutputQualityError('Model embedded a second prompt inside its response. Review and retry.')
    text, extracted = _extract_structured(text, mode)
    if extracted:
        warnings.append('Extracted an explicit final answer from structured model output; other analysis fields were not used.')
    # Strip a whole-answer quote wrapper, never mid-sentence quotation marks.
    text, unquoted = _unwrap_quotes(text)
    if unquoted:
        warnings.append('Removed enclosing quotation marks.')
    # Legacy service's last explicit final marker wins, but never invent a final
    # answer if the marker has no suffix.
    matches = list(_FINAL_MARKER.finditer(text))
    if matches and matches[-1].end() < len(text):
        text = text[matches[-1].end():].strip()
        warnings.append('Kept only the explicitly marked final instruction.')
    match = _META_START.match(text)
    if match and match.end() < len(text):
        text = text[match.end():].strip()
        text = text[:1].upper() + text[1:]
        warnings.append('Removed the response label.')
    if mode == 'video':
        match = _VIDEO_PREAMBLE.match(text)
        if match and match.end() < len(text):
            text = text[match.end():].strip()
            text = text[:1].upper() + text[1:]
            warnings.append('Removed a video-prompt preamble; review the remaining shot wording.')
    # An independent afterword is removable only when it is a separate paragraph
    # whose subject is the prompt itself. Never chop off single-paragraph content.
    paras = re.split(r'\n\s*\n', text)
    if len(paras) > 1:
        while len(paras) > 1 and _META_PARAGRAPH.match(paras[-1].strip()):
            paras.pop()
            warnings.append('Removed an explanatory afterword.')
        text = '\n\n'.join(paras).strip()
    if mode == 'caption':
        # This canned closing statement describes the model's compliance,
        # not the image. Safe to remove without inventing a visual claim.
        tail_claim = re.search(r'(?<=[.!?])\s+The image is grounded in visible facts, focusing on[^.!?]{1,250}[.!?]\s*$', text, re.I)
        if tail_claim:
            text = text[:tail_claim.start()].strip()
            warnings.append('Removed a detached instruction-echo statement about visual grounding.')
    if mode in ('prompt', 'video', 'edit', 'caption'):
        tail = re.search(r'(?<=[.!?])[\'\"”’]?\s+(?:No JSON fields, sections, or analysis are needed;[^.!?]*[.!?]|The final prompt should be straightforward[^.!?]*[.!?])(?:[\'\"”’])?\s*$', text, re.I)
        if tail:
            text = text[:tail.start()].strip().strip('\"\'“”‘’').strip()
            warnings.append('Removed a detached formatting instruction repeated by the model.')
    text, unquoted = _unwrap_quotes(text)
    if unquoted:
        warnings.append('Removed enclosing quotation marks.')
    if not text:
        raise OutputQualityError('The model returned an empty final answer after normalization.')
    if mode not in ('tags', 'negative', 'structured') and _META_INLINE.search(text):
        warnings.append('Model output still contains wording about a prompt rather than direct instructions. Review or retry.')
    return text, warnings


_CAMERA_TOKENS = {
    'pan_left': (r'\bpan(?:s|ning)?\s+(?:(?:smoothly|slowly)\s+)?(?:to\s+(?:the\s+)?)?left\b', r'\bpan(?:s|ning)?\s+(?:(?:smoothly|slowly)\s+)?(?:to\s+(?:the\s+)?)?right\b'),
    'pan_right': (r'\bpan(?:s|ning)?\s+(?:(?:smoothly|slowly)\s+)?(?:to\s+(?:the\s+)?)?right\b', r'\bpan(?:s|ning)?\s+(?:(?:smoothly|slowly)\s+)?(?:to\s+(?:the\s+)?)?left\b'),
    'static': (r'\b(?:locked.off|stationary|static\s+camera|camera\s+remains\s+still)\b', None),
    'orbit': (r'\b(?:orbit(?:s|ing)?|circles?\s+around)\b', None),
    'push_in': (r'\b(?:push(?:es|ing)?\s+in|doll(?:y|ies)\s+in)\b', None),
    'pull_back': (r'\b(?:pull(?:s|ing)?\s+back|doll(?:y|ies)\s+out)\b', None),
    'tracking': (r'\b(?:track(?:s|ing)?|follow(?:s|ing)\s+(?:the\s+)?subject)\b', None),
    'handheld': (r'\bhandheld\b', None),
    'tilt': (r'\btilt(?:s|ing)?\b', None),
}


def task_diagnostics(text: str, *, task: str, profile: dict[str, Any] | None = None, operation: str = '') -> list[str]:
    """Advisory heuristic, not an assertion that visual/semantic fidelity was proven."""
    if operation == 'negative' or task not in ('text_to_video', 'image_to_video'):
        return []
    choice = str((profile or {}).get('camera_behavior') or 'preserve_auto')
    pattern_pair = _CAMERA_TOKENS.get(choice)
    if not pattern_pair:
        return []
    expected, contradictory = pattern_pair
    if contradictory and re.search(contradictory, text, flags=re.I):
        return [f'Camera direction may contradict the selected {choice.replace("_", " ")} profile. Review before use.']
    if not re.search(expected, text, flags=re.I):
        return [f'The selected {choice.replace("_", " ")} camera behavior was not explicitly identified in the final text. Review before use.']
    return []

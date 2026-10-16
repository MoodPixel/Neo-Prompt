"""deterministic task-output acceptance after output normalization.

Rules protect output *format*, not semantic truth. We cannot certify that a local
model followed source, identity or visual-grounding requirements without review.
No invented facts, no automatic extra inference, no hidden successful history.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re


@dataclass(frozen=True)
class Verdict:
    status: str                  # ready | needs_review | invalid
    issues: tuple[str, ...]


# Explanatory phrases and leaked instruction text, NOT ordinary phrases such as
# 'a prompt on the wall' within genuine scene content.
_META = re.compile(
    r'\b(?:the\s+(?:final\s+)?prompt\s+(?:for\s+(?:this|the)|is\s+to|should\b|requires\b)|'
    r'this\s+prompt\s+(?:should|will)|the\s+edit\s+instruction\s+is\b|'
    r'the\s+final\s+prompt\s+is\b|the\s+scene\s+should\s+depict\b|'
    r'no\s+JSON\s+fields\b|no\s+(?:additional\s+)?narrative\s+or\s+meta\s+description\b|'
    r'the\s+image\s+should\s+be\s+generated\b|'
    r'the\s+prompt\s+is\s+to\s+(?:create|render|generate)\b)', re.I)
_MIXED_JSON = re.compile(r'```\s*json\s*[\r\n]|(?:^|\n)\s*\{\s*"[\w-]+"\s*:', re.I)
_EMBEDDED_PROMPT = re.compile(r'(?:[.!?]\s+|\n)the\s+prompt\s*:\s*[\'"“]?', re.I)
_EDIT_DESCRIPTION = re.compile(r'^\s*(?:the image depicts|the image shows|this is an image of)\b', re.I)
_LEAKED_RESPONSE = re.compile(r'<\/?(?:response|answer|final|analysis)\s*>|(?:^|\n)\s*```(?:json)?\s*$',re.I)
_MULTIPLE_FINAL = re.compile(r'\b(?:the\s+final\s+prompt\s+should\s+be|the\s+final\s+(?:video|image)\s+generation\s+prompt\s+should\s+be|i(?:\s+have|\'ve)\s+generated\s+(?:a|the)\s+(?:polished|final)\s+prompt|no\s+JSON\s+fields|the\s+goal\s+is\s+to\s+create\s+a\s+(?:balanced|clear)\s+prompt)\b',re.I)
_CAPTION_SECTION_LEAK = re.compile(r'(?:^|\n)\s*(?:\*\*)?(?:Image Description|Additional Details|Final Requested Text)\s*:', re.I)
_INCOMPLETE_TAIL = re.compile(r'(?:\b(?:the\s+final\s+prompt\s+is|this\s+prompt\s+should|no\s+JSON\s+fields)\s*:?\s*$|[,:;]\s*$)', re.I)


def assess(text: str, *, mode: str, finish_reason: str = '', diagnostics: list[str] | None = None,
           capped_negative: bool = False) -> Verdict:
    """Return an honest structural verdict, without editing or extrapolating output.

    The provider's finish_reason is authoritative for truncation even if a
    partial answer looks grammatically complete. Unsupported finish reasons are
    not assumed to be truncated. JSON is intentional only for structured mode.
    """
    issues: list[str] = list(diagnostics or [])
    if not text or not text.strip():
        return Verdict('invalid', ('Model produced no usable final answer.',))
    if finish_reason.strip().lower() in {'length', 'max_tokens', 'token_limit'}:
        return Verdict('invalid', ('The model hit its token limit. Incomplete output was not saved as a successful result.',))
    if mode == 'structured':
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return Verdict('invalid', ('Structured output is not valid JSON.',))
        if not isinstance(parsed, (list, dict)) or not parsed:
            return Verdict('invalid', ('Structured output needs a nonempty JSON object or array.',))
        return Verdict('ready', ())
    if mode == 'negative':
        terms = [x.strip() for x in text.split(',') if x.strip()]
        if not terms:
            return Verdict('invalid', ('No acceptable negative exclusions remained after filtering.',))
        if len(terms) > 32:
            return Verdict('invalid', ('Negative prompt exceeds 32 terms.',))
        if capped_negative:
            issues.append('The original negative response contained more than 32 terms; only the first 32 accepted terms were retained. Review the selection.')
        if any(len(t) > 150 for t in terms):
            issues.append('A negative term is unusually long and may contain explanatory prose.')
    else:
        if _MIXED_JSON.search(text) and not text.lstrip().startswith('{'):
            return Verdict('invalid', ('Output mixes prompt prose and an additional JSON/analysis block; no unambiguous final answer.',))
        if _EMBEDDED_PROMPT.search(text):
            return Verdict('invalid', ('Output contains a second embedded prompt; Neo cannot safely decide which text is final.',))
        if mode == 'caption' and _CAPTION_SECTION_LEAK.search(text):
            issues.append('Caption contains analysis or multiple section headings instead of one final caption.')
        if mode == 'edit' and _EDIT_DESCRIPTION.search(text):
            issues.append('Image-edit output describes an image instead of directly instructing the edit.')
        if mode == 'prompt' and _EDIT_DESCRIPTION.search(text):
            issues.append('Image output describes an existing image rather than giving direct generation directions.')
        if _META.search(text) or _MULTIPLE_FINAL.search(text):
            issues.append('Output contains meta-instructions or text about the prompt; review or explicitly reformat.')
        if _LEAKED_RESPONSE.search(text):
            issues.append('Output contains leaked response markup or a stray code fence; review before reuse.')
        if _INCOMPLETE_TAIL.search(text):
            issues.append('Output appears to end with incomplete or leaked formatting instructions.')
    # Stable unique issue order, preserve severity without extrapolating semantics.
    unique = tuple(dict.fromkeys(i for i in issues if i))
    return Verdict('needs_review' if unique else 'ready', unique)

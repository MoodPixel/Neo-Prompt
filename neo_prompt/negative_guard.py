"""positive-context protection and negative-term sanitizer.

Adapted from owner-supplied Neo Studio V2 Prompt/Captioning P23 logic.
App-owned module; no imports or runtime dependency on Studio.
"""
from __future__ import annotations

_PROMPT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "for", "from", "in", "into", "is", "it", "of", "on", "or", "the", "to", "under", "with", "wearing",
    "prompt", "image", "photo", "photograph", "generate", "create", "style", "editorial",
}

_NEGATIVE_PROMPT_MAX_TERMS = 32
_NEGATIVE_PROMPT_MAX_TOKENS = 192
_NEGATIVE_PROMPT_TEMPERATURE_CAP = 0.35
_NEGATIVE_PROMPT_TOP_P_CAP = 0.85

_NEGATIVE_TERM_ALIASES = {
    "pixelization": "pixelation",
    "excessive pixelization": "pixelation",
    "excessive pixelation": "pixelation",
    "color bleed": "color bleeding",
    "color bleeding": "color bleeding",
    "excessive color bleed": "color bleeding",
    "excessive color bleeding": "color bleeding",
    "color variance": "color variation",
    "color variation": "color variation",
    "excessive color variance": "color variation",
    "excessive color variation": "color variation",
    "color aberration": "chromatic aberration",
    "color fringing": "chromatic aberration",
    "chromatic aberration": "chromatic aberration",
    "excessive color aberration": "chromatic aberration",
    "excessive color fringing": "chromatic aberration",
    "excessive chromatic aberration": "chromatic aberration",
    "jpeg artifact": "jpeg/compression artifacts",
    "jpeg artifacts": "jpeg/compression artifacts",
    "compression artifact": "jpeg/compression artifacts",
    "compression artifacts": "jpeg/compression artifacts",
    "excessive jpeg artifact": "jpeg/compression artifacts",
    "excessive jpeg artifacts": "jpeg/compression artifacts",
    "excessive compression artifact": "jpeg/compression artifacts",
    "excessive compression artifacts": "jpeg/compression artifacts",
    "excessive compression": "jpeg/compression artifacts",
    "excessive blur": "blur",
    "excessive blurring": "blur",
    "overly blurred": "blur",
}


def _negative_term_key(value: str) -> str:
    """Return a conservative semantic key for one generated negative tag."""
    import re

    text = str(value or "").strip().lower()
    text = re.sub(r"^\s*(?:[-–—•*]+|\d+[.)])\s*", "", text)
    text = re.sub(r"^(negative\s+prompt|negative|avoid|exclude)\s*:\s*", "", text)
    text = text.strip(" \t\r\n.,;:!?()[]{}\"'")
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    if text in _NEGATIVE_TERM_ALIASES:
        return _NEGATIVE_TERM_ALIASES[text]
    compact = re.sub(r"^(?:excessive|overly|extreme|severe)\s+", "", text)
    if compact in _NEGATIVE_TERM_ALIASES:
        return _NEGATIVE_TERM_ALIASES[compact]
    return compact


_NEGATIVE_FAILURE_MODIFIERS = {
    "bad", "poor", "low", "lowres", "unrealistic", "unnatural", "incorrect", "wrong",
    "distorted", "deformed", "malformed", "extra", "missing", "duplicate", "duplicated",
    "mutated", "broken", "fused", "disconnected", "cropped", "outside", "blurry", "blur",
    "artifact", "artifacts", "noise", "grain", "pixelation", "pixelization", "jpeg",
    "compression", "aliasing", "chromatic", "aberration", "fringing", "banding",
    "overexposed", "underexposed", "oversaturated", "undersaturated", "desaturated",
    "excessive", "overly", "lack", "lacking", "unwanted", "unrequested", "inconsistent",
    "asymmetrical", "asymmetry", "ghosting", "posterization", "clipping", "muddy", "washed",
    "distortion", "warped", "warping", "misaligned", "uncanny", "harsh", "flat", "plastic", "waxy",
    "overprocessed", "oversmoothed", "oversharpened", "cross-eyed", "crossed", "blown", "crushed",
}

_NEGATIVE_CONTEXT_STOPWORDS = _PROMPT_STOPWORDS | {
    "render", "renders", "rendered", "rendering", "final", "shows", "show", "scene", "model",
    "overall", "aim", "ensure", "suitable", "context", "quality", "high", "scheme", "nature",
}

_NEGATIVE_PROTECTED_CONCEPT_GROUPS = (
    {"sensual", "sensuality", "sexual", "sexuality", "erotic", "seductive", "seductively", "suggestive", "allure", "intimate", "intimacy", "romantic", "romance"},
    {"realistic", "realism", "photorealistic", "photorealism", "naturalistic"},
    {"filmic", "cinematic", "cinema", "movie-like"},
    {"anime", "manga", "illustrated", "illustration"},
    {"watercolor", "watercolour", "painterly", "painting"},
)


def _negative_context_tokens(value: str) -> list[str]:
    import re

    return [
        token
        for token in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", str(value or "").lower())
        if len(token) >= 2 and token not in _NEGATIVE_CONTEXT_STOPWORDS
    ]


def _negative_token_equivalent(left: str, right: str) -> bool:
    left = str(left or "").strip().lower()
    right = str(right or "").strip().lower()
    if not left or not right:
        return False
    if left == right:
        return True
    # Conservative morphology tolerance: pose/posed, seductive/seductively,
    # emphasize/emphasizing, etc.  Avoid broad stemming that could merge unrelated words.
    if min(len(left), len(right)) >= 4 and abs(len(left) - len(right)) <= 3:
        if left.startswith(right) or right.startswith(left):
            return True
    pairs = (
        ("ively", "ive"), ("atively", "ative"), ("ically", "ic"), ("ally", "al"),
        ("ingly", "e"), ("ing", "e"), ("edly", "e"), ("ed", "e"), ("ly", ""),
    )
    left_forms = {left}
    right_forms = {right}
    for suffix, replacement in pairs:
        if left.endswith(suffix) and len(left) > len(suffix) + 2:
            left_forms.add(left[:-len(suffix)] + replacement)
        if right.endswith(suffix) and len(right) > len(suffix) + 2:
            right_forms.add(right[:-len(suffix)] + replacement)
    return bool(left_forms & right_forms)


def _negative_has_failure_modifier(term: str) -> bool:
    tokens = set(_negative_context_tokens(term))
    if tokens & _NEGATIVE_FAILURE_MODIFIERS:
        return True
    lowered = str(term or "").lower()
    return any(
        phrase in lowered
        for phrase in (
            "lack of ", "out of frame", "out-of-frame", "not requested", "not explicitly requested",
            "too much ", "too little ", "incorrectly ", "poorly ", "over-sharpen", "over sharpen",
        )
    )


def _negative_explicitly_requested(term: str, custom_instruction: str) -> bool:
    """Preserve a user-declared exclusion even when it overlaps wanted context."""
    import re

    candidate = re.sub(r"\s+", " ", str(term or "").strip().lower()).strip(" .,;:'\"")
    custom = str(custom_instruction or "").lower()
    if not candidate or not custom:
        return False
    escaped = re.escape(candidate)
    return bool(
        re.search(
            rf"\b(?:no|avoid|exclude|excluding|without|remove|removing|do\s+not\s+include)\b[^.;\n]{{0,80}}\b{escaped}\b",
            custom,
            flags=re.IGNORECASE,
        )
    )


_NEGATIVE_STANDALONE_EXCLUSION_PHRASES = (
    "watermark", "signature", "logo", "caption", "subtitle", "username", "artist name",
    "text artifact", "text artifacts", "compression artifact", "compression artifacts",
    "jpeg artifact", "jpeg artifacts", "chromatic aberration", "color fringing",
    "aliasing", "banding", "moire", "ghosting", "posterization", "pixelation", "pixelization",
)


def _negative_has_valid_exclusion_semantics(term: str, *, custom_instruction: str = "") -> bool:
    """Require a failure state or an explicit exclusion for contextual Negative runs.

    A local model may emit attractive descriptors that are neither copied verbatim
    from the positive prompt nor useful as exclusions (``elegance``, ``realism``,
    ``soft muted colors``).  Contextual Negative generation accepts only terms that
    have recognizable negative/failure semantics, or that the user explicitly
    requested through no/avoid/exclude/without language.
    """
    import re

    candidate = re.sub(r"\s+", " ", str(term or "").strip().lower()).strip(" .,;:'\"")
    if not candidate:
        return False
    if _negative_explicitly_requested(candidate, custom_instruction):
        return True
    if _negative_has_failure_modifier(candidate):
        return True
    if re.match(r"^(?:no|avoid|exclude|without|remove)\b", candidate):
        return True
    return any(phrase in candidate for phrase in _NEGATIVE_STANDALONE_EXCLUSION_PHRASES)


def _negative_term_is_protected_positive_echo(term: str, *, desired_context: str = "", custom_instruction: str = "") -> bool:
    """Return True when a generated negative term merely negates/copies wanted content.

    This is deliberately conservative: a failure-qualified term (``unrealistic
    anatomy``, ``lack of realism``, ``incorrect camera angle``) is retained.  Only
    unqualified terms that strongly match the user's wanted source/positive context
    are culled.  Explicit ``avoid/no/without`` user instructions override the guard.
    """
    import re

    candidate = re.sub(r"\s+", " ", str(term or "").strip().lower()).strip(" .,;:'\"")
    context = re.sub(r"\s+", " ", str(desired_context or "").strip().lower())
    if not candidate or not context:
        return False
    if _negative_explicitly_requested(candidate, custom_instruction):
        return False
    if _negative_has_failure_modifier(candidate):
        return False

    # Direct phrase echo from source/positive prompt.
    if len(candidate) >= 3 and candidate in context:
        return True

    candidate_tokens = _negative_context_tokens(candidate)
    context_tokens = _negative_context_tokens(context)
    if candidate_tokens and context_tokens:
        matched = sum(
            1
            for token in candidate_tokens
            if any(_negative_token_equivalent(token, wanted) for wanted in context_tokens)
        )
        overlap = matched / max(1, len(candidate_tokens))
        if len(candidate_tokens) >= 2 and overlap >= 0.72:
            return True

    # Catch close semantic echoes where local models swap one desired mood/style
    # adjective for a sibling synonym (e.g. sensual -> erotic).
    for group in _NEGATIVE_PROTECTED_CONCEPT_GROUPS:
        if any(re.search(rf"\b{re.escape(word)}\b", context) for word in group):
            if any(re.search(rf"\b{re.escape(word)}\b", candidate) for word in group):
                return True
    return False


def _sanitize_negative_prompt_output(output_text: str, *, max_terms: int = _NEGATIVE_PROMPT_MAX_TERMS, desired_context: str = "", custom_instruction: str = "") -> tuple[str, bool, bool]:
    """Deduplicate and bound model-generated negative prompt lists.

    Local text backends can occasionally enter comma-list repetition loops. Neo
    keeps the first useful wording for each concept, removes exact/common
    equivalent repeats, and hard-caps the final list without fabricating tags.
    """
    import re

    raw = str(output_text or "").strip()
    if not raw:
        return "", False, False

    raw = re.sub(r"^\s*(?:negative\s+prompt|negative)\s*:\s*", "", raw, flags=re.IGNORECASE)
    candidates = re.split(r"[,;\n]+", raw)
    terms: list[str] = []
    seen: set[str] = set()
    duplicates_removed = False
    truncated = False

    for candidate in candidates:
        term = re.sub(r"^\s*(?:[-–—•*]+|\d+[.)])\s*", "", str(candidate or "")).strip()
        term = term.strip(" \t\r\n.,;:|\"'")
        term = re.sub(r"\s+", " ", term)
        if not term:
            continue
        key = _negative_term_key(term)
        if not key:
            continue
        if _negative_term_is_protected_positive_echo(
            term,
            desired_context=desired_context,
            custom_instruction=custom_instruction,
        ):
            duplicates_removed = True
            continue
        if desired_context and not _negative_has_valid_exclusion_semantics(
            term,
            custom_instruction=custom_instruction,
        ):
            duplicates_removed = True
            continue
        if key in seen:
            duplicates_removed = True
            continue
        if len(terms) >= max(1, int(max_terms)):
            truncated = True
            break
        seen.add(key)
        terms.append(term)

    cleaned = ", ".join(terms).strip()
    changed = cleaned != raw.strip()
    return cleaned, bool(changed or duplicates_removed), truncated



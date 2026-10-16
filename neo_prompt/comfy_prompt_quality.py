"""task-oriented ComfyUI LLM requests and conservative output diagnostics.

No automatic reruns, text rewrites or model-specific assumptions. The same base
Prompt Studio compiler remains authoritative across independent backends.
"""
from __future__ import annotations

import re
from typing import Any

from .generation import compile_messages, process_prompt_reply, clamp_params, ProviderFailure


def messages_for_comfy(source: str, instruction: str, operation: str, profile: dict[str, Any]):
    messages, normalized = compile_messages(source, instruction, operation, profile)
    fmt = normalized.get('output_format', 'natural_prompt')
    # Do not apply paragraph formatting rules to deliberately structured/tag outputs.
    if fmt in ('natural_prompt', 'image_generation_prompt', 'video_generation_prompt', 'edit_instruction'):
        extra = (' Write the finished usable scene or instruction directly. ' 
                 'Write natural sentences with clear physical details; avoid keyword repetition, ' 
                 'explanations of how to write a prompt, and restating the task requirements. ' 
                 'A brief, coherent paragraph is preferred to repeated lists of descriptors. ')
    else:
        extra = (' Return exactly the selected output format and no surrounding explanation. '
                 'Avoid repeating the same phrases to fill the response. ')
    messages[0]['content'] += extra
    if operation in ('enhance', 'rewrite'):
        messages[0]['content'] += (' Refine ONLY the selected saved result. Preserve every explicitly '
                                   'stated subject identity, setting, edit or camera direction. '
                                   'Add plausible detail only where unspecified. Do not use any earlier editor draft.')
    return messages, normalized


def _repetition_issue(text: str) -> str | None:
    """Warn on strong word-sequence loops; do not confuse creative detail with drift."""
    words = re.findall(r"[\w'-]+", text.casefold())
    if len(words) < 45:
        return None
    # Very unlikely to occur three times in a legitimate short creative prompt.
    from collections import Counter
    for length in (12, 8):
        chunks = Counter(tuple(words[i:i+length]) for i in range(len(words)-length+1))
        if any(count >= 3 for count in chunks.values()):
            return 'Model repeated a substantial phrase several times; review or retry with adjusted sampling.'
    return None


def review_comfy_result(result: dict, *, raw: str):
    issue = _repetition_issue(result['text'])
    if issue:
        result['quality_status'] = 'needs_review'
        result['quality_issues'] = list(dict.fromkeys(result['quality_issues'] + [issue]))
        result['warnings'] = list(dict.fromkeys(result['warnings'] + [issue]))
    return result


def refinement_result(raw: str, *, parent: dict, operation: str, params: dict, model: str, prompt_id: str, workflow_name: str):
    """Uses the same negative sanitation and output contract as KoboldCPP."""
    if operation not in ('enhance','rewrite','negative'):
        raise ProviderFailure(422, 'Choose Enhance, Rewrite or Negative.')
    text = parent['text']
    result = process_prompt_reply(raw, finish='stop', source=text, instruction='', operation=operation,
                                  normalized=parent.get('prompt_profile') or {}, generation=params)
    review_comfy_result(result,raw=raw)
    if operation in ('enhance','rewrite'):
        issue = 'Review the refinement against its exact selected parent before saving or refining again.'
        result['quality_status'] = 'needs_review'
        result['quality_issues'] = list(dict.fromkeys(result['quality_issues'] + [issue]))
        result['warnings'] = list(dict.fromkeys(result['warnings'] + [issue]))
    result.update(runtime_model=model, runtime_model_state='selected_from_live_catalog',
                  comfy_prompt_id=prompt_id, workflow_name=workflow_name)
    return result

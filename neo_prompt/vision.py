"""bounded KoboldCPP vision requests using app-owned P23 caption contracts."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from .caption_profiles import compile_caption_task_contract, caption_sampling_params
from .profile_contract import normalize_profile
from .connections import normalize_endpoint, inspect_kobold_model
from .generation import ProviderFailure, clean_text, _extract_response
from .output_quality import normalize_output, task_diagnostics, OutputQualityError
from .output_contract import assess
from .instruction_fidelity import check_fidelity
from .caption_task_policy import effective_vision_options
from .qwen_pe import apply_pe_review

TASKS = {'describe': 'caption_image', 'recreate': 'image_recreation', 'edit': 'image_edit', 'video': 'image_to_video', 'dataset': 'dataset_prepare', 'library': 'library_caption'}


def build_vision_messages(task: str, instruction: str, image: bytes, mime: str, *, trigger: str = '', options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if task not in TASKS:
        raise ValueError('Unsupported caption task')
    if task == 'edit' and not instruction.strip():
        raise ValueError('Image edit prompt needs an edit instruction.')
    if task == 'describe':
        import re
        # Do not silently ignore a transform request by returning a static caption.
        if re.search(r'\b(?:change|replace|recolor|restyle|remove)\b.{0,100}\b(?:hair|shirt|clothing|pose|background|style|color|colour|to|into)\b', instruction, re.I) or re.search(r'\b(?:only\s+change|keep\s+everything\s+else\s+unchanged)\b', instruction, re.I):
            raise ValueError('Describe Image reports what is visible. Choose Image → Edit instruction for requested changes, or Recreate for target styling.')
    if trigger and (len(trigger) > 90 or not all(ch.isalnum() or ch in '_-' for ch in trigger)):
        raise ValueError('Trigger token must be 1–90 letters, numbers, underscore or hyphen.')
    surface = 'batch_dataset' if task == 'dataset' else ('batch_library' if task == 'library' else 'caption_studio')
    if (options or {}).get('analysis_scope') == 'custom_crop':
        raise ValueError('Custom crop requires a real image crop selection; choose a supported scope instead.')
    options = effective_vision_options(task, options)
    source = {k:v for k,v in options.items() if k in {'purpose','analysis_scope','visual_treatment','output_format','edit_intent','preservation_policy','motion_profile','camera_behavior','grounding','custom_visual_treatment','custom_purpose'}}
    profile = normalize_profile({**source, 'prompt_task': TASKS[task], 'surface': surface}, surface=surface)['profile']
    if task == 'dataset' and trigger:
        profile['trigger_token'] = trigger
    contract = compile_caption_task_contract(profile, user_instruction=instruction, caption_length='medium', detail_level='detailed')
    # Extra guard because some KoboldCPP templates may strip parts of the system prompt.
    user = contract['user_prompt']
    return [
        {'role': 'system', 'content': contract['system_prompt']},
        {'role': 'user', 'content': [
            {'type': 'text', 'text': user},
            {'type': 'image_url', 'image_url': {'url': 'data:' + mime + ';base64,' + base64.b64encode(image).decode('ascii')}}
        ]}
    ]


async def caption_image(profile: dict[str, Any], image_path: Path, mime: str, *, task: str, instruction: str = '', trigger: str = '', options: dict[str, Any] | None = None, max_tokens: int = 420, comfy_workflow: dict | None = None, comfy_session=None) -> dict[str, Any]:
    if profile.get('kind') not in ('koboldcpp','comfyui'):
        raise ProviderFailure(422,'Unsupported vision backend.')
    if profile.get('kind')=='comfyui' and comfy_workflow is None:
        raise ProviderFailure(422,'Select a trusted matching ComfyUI workflow for this vision task.')
    try:
        image = image_path.read_bytes()
    except OSError as exc:
        raise ProviderFailure(404, 'The image is no longer available. Upload it again.') from exc
    if len(image) > 10 * 1024 * 1024:
        raise ProviderFailure(413, 'Stored image exceeds the vision request limit.')
    try:
        messages = build_vision_messages(task, instruction, image, mime, trigger=trigger, options=options)
    except ValueError as exc:
        raise ProviderFailure(422, str(exc)) from exc
    try:
        effective_options = effective_vision_options(task, options)
    except ValueError as exc:
        raise ProviderFailure(422, str(exc)) from exc
    params = caption_sampling_params({'temperature': 0.3 if task == 'dataset' else 0.45, 'top_p': 0.85, 'max_tokens': max_tokens}, {'prompt_task': TASKS[task], 'surface': ('batch_dataset' if task == 'dataset' else ('batch_library' if task == 'library' else 'caption_studio'))})
    body = {'model': 'default', 'stream': False, 'messages': messages, 'temperature': params['temperature'], 'top_p': params['top_p'], 'max_tokens': max_tokens}
    if comfy_workflow is not None:
        from .comfy_adapter import execute as execute_comfy
        # Generic Comfy VLMs receive the same source task contract, PE-I2I takes
        # the direct edit instruction plus image; the graph owns its checkpoint.
        system_text = ''
        if comfy_workflow['mode'] == 'qwen_pe_i2i':
            user_text = instruction.strip()
            if effective_options.get('visual_treatment') not in ('source_accurate',None,''):
                user_text += '\nRequested visual treatment: ' + str(effective_options['visual_treatment']).replace('_',' ')
        elif comfy_workflow.get('auto_route') in ('vlm','vlm_mtmd'):
            system_text, user_text = messages[0]['content'], messages[1]['content'][0]['text']
        else:
            user_text = messages[0]['content'] + '\n\n' + messages[1]['content'][0]['text']
        comfy_kwargs = {'session': comfy_session} if comfy_session is not None else {}
        output = await execute_comfy(profile, comfy_workflow, prompt=user_text, image_path=image_path, mime=mime, system_prompt=system_text, **comfy_kwargs)
        result = finalize_caption_reply(output['text'], finish='stop',task=task,instruction=instruction,
            trigger=trigger,effective_options=effective_options,params=params,
            observed={'model':output['runtime_model'],'model_identity_state':output['runtime_model_state']})
        result['comfy_prompt_id'] = output.get('prompt_id')
        if comfy_workflow.get('auto_route')=='qwen_pe_i2i':
            result['pe_metadata'] = output.get('pe_metadata') or {}
            apply_pe_review(result, result['pe_metadata'])
        return result
    base = normalize_endpoint(profile['endpoint'])
    observed = await inspect_kobold_model(base, timeout_seconds=1.25)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5, read=300, write=20, pool=5), follow_redirects=False, trust_env=False) as client:
            async with client.stream('POST', base + '/v1/chat/completions', json=body, headers={'Accept': 'application/json'}) as response:
                if response.is_redirect:
                    raise ProviderFailure(502, 'Vision request redirected. Check the configured KoboldCPP endpoint.')
                if response.status_code >= 400:
                    raise ProviderFailure(502, f'Vision request failed (HTTP {response.status_code}). Enable a compatible vision model and multimodal projector (MMProj) in KoboldCPP, then retry.')
                count = 0
                chunks = []
                async for chunk in response.aiter_bytes():
                    count += len(chunk)
                    if count > 2 * 1024 * 1024:
                        raise ProviderFailure(502, 'Vision response exceeds the 2 MB limit.')
                    chunks.append(chunk)
                payload = json.loads(b''.join(chunks))
    except httpx.ConnectError as exc:
        raise ProviderFailure(503, 'KoboldCPP is offline. Start the selected server and verify its port.') from exc
    except httpx.TimeoutException as exc:
        raise ProviderFailure(504, 'Vision request timed out. Check the KoboldCPP console; processing might still be running.') from exc
    except (httpx.RequestError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProviderFailure(502, 'KoboldCPP returned a transport or JSON error. Check the model and vision setup.') from exc
    raw, finish = _extract_response(payload)
    return finalize_caption_reply(raw, finish=finish, task=task, instruction=instruction, trigger=trigger,
        effective_options=effective_options, params=params, observed=observed)


def finalize_caption_reply(raw: str, *, finish: str, task: str, instruction: str, trigger: str,
                           effective_options: dict, params: dict, observed: dict) -> dict:
    clean, warnings = clean_text(raw)
    try:
        clean, format_warnings = normalize_output(clean, mode=('edit' if task == 'edit' else 'video' if task == 'video' else 'tags' if effective_options.get('output_format') == 'tags_keywords' else 'caption'))
    except OutputQualityError as exc:
        raise ProviderFailure(502, str(exc), raw_response=raw) from exc
    warnings += format_warnings
    # A truncated response cannot be silently accepted as a complete caption.
    import re
    clean = re.sub(r'\[(?:Image|image)\s*\d*\]', '', clean).strip()
    clean = re.sub(r'^(?:caption|response|answer)\s*:\s*', '', clean, count=1, flags=re.I).strip()
    if task == 'dataset' and trigger:
        # Deterministic single trigger prefix instead of trusting the model to count.
        clean = re.sub(r'(?<![A-Za-z0-9_-])' + re.escape(trigger) + r'(?![A-Za-z0-9_-])', '', clean)
        clean = re.sub(r'^[,\s]+', '', clean).strip()
        clean = trigger + ', ' + clean if clean else ''
    mode = ('edit' if task == 'edit' else 'video' if task == 'video' else
            'tags' if effective_options.get('output_format') == 'tags_keywords' else 'caption')
    diagnostics = task_diagnostics(clean, task=('image_to_video' if task == 'video' else task), profile=effective_options)
    if task == 'edit':
        diagnostics += check_fidelity(clean, task='text_image_edit', instruction=instruction, preservation_policy=effective_options.get('preservation_policy', 'preserve_unrequested'))
        diagnostics += check_caption_edit_requirements(clean, instruction)
    elif task == 'video':
        diagnostics += check_caption_video_requirements(clean)
    # Advisory check: named descriptors explicitly supplied by a user should not
    # disappear without review. Do not infer identity from an image or fabricate
    # missing facts in the cleaner. The check applies to all Caption tasks.
    if instruction.strip():
        diagnostics += check_fidelity(clean, task='caption_image', instruction='', source=instruction)
    verdict = assess(clean, mode=mode, finish_reason=finish, diagnostics=diagnostics)
    if verdict.status == 'invalid':
        raise ProviderFailure(502, 'Caption contract rejected output: ' + '; '.join(verdict.issues),
                              raw_response=raw, issues=verdict.issues)
    warnings += list(verdict.issues)
    if not clean or len(clean) > 32000:
        raise ProviderFailure(502, 'Vision model did not return a valid nonempty caption. Nothing was saved.', raw_response=raw)
    # Unverified inputs cannot be certified as visually grounded, so always preserve model caveat.
    return {'text': clean, 'warnings': warnings, 'finish_reason': finish, 'task': task, 'params': params,
            'quality_status': verdict.status, 'quality_issues': list(verdict.issues),
            'runtime_model': observed['model'], 'runtime_model_state': observed['model_identity_state']}


def check_caption_edit_requirements(text: str, instruction: str) -> list[str]:
    """Conservative checks; not proof of semantic or pixel-level fidelity."""
    import re
    notes: list[str] = []
    if re.match(r"\s*(?:the|this) image (?:depicts|shows|features)\b", text, re.I):
        notes.append("Image Edit returned a source-image description rather than a usable change instruction.")
    if not re.search(r"\b(?:change|recolor|replace|remove|add|modify|turn|make|restyle|transform|adjust)\b", text, re.I):
        notes.append("Edit output does not contain a direct edit action.")
    # Requested hair alteration may be in plain language; require hair + target styling
    # but do not infer whether the model's edit is visually correct.
    if re.search(r"\b(?:hair|hairstyle|haircut)\b", instruction, re.I) and not re.search(r"\b(?:hair|hairstyle|haircut)\b", text, re.I):
        notes.append("The requested hair edit is missing from the result.")
    return notes


def check_caption_video_requirements(text: str) -> list[str]:
    import re
    notes = []
    if re.match(r"\s*(?:the|this) image (?:depicts|shows|features)\b", text, re.I):
        notes.append("Image-to-Video returned a static image description instead of a moving shot.")
    if not re.search(r"\b(?:camera|pan(?:s|ning)?|tilt(?:s|ing)?|orbit(?:s|ing)?|push[- ]in|zoom|track(?:s|ing)?|dolly|shot|frame|handheld)\b", text, re.I):
        notes.append("The video result does not describe camera behavior.")
    if not re.search(r"\b(?:move(?:s|ment|ing)?|motion|breath(?:es|ing)?|blink(?:s|ing)?|turn(?:s|ing)?|shift(?:s|ing)?|tilt(?:s|ing)?|pan(?:s|ning)?|orbit(?:s|ing)?|push(?:es|ing)?|zoom(?:s|ing)?|flow(?:s|ing)?|sway(?:s|ing)?|track(?:s|ing)?)\b", text, re.I):
        notes.append("The video result does not describe observable temporal motion.")
    return notes

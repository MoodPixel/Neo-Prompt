"""ComfyUI execution adapter for user-approved text/VLM prompt workflows.

No model/node-specific heuristics. Only loopback, bounded responses and exact output
bindings. Never falls back to KoboldCPP, silently downloads, or runs other Neo apps.
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from uuid import uuid4
import httpx
from .connections import normalize_endpoint
from .generation import ProviderFailure
from .comfy_workflows import bind_graph, extract_history_text, WorkflowError

class ComfyExecutionUncertain(ProviderFailure):
    """Prompt may still be queued/running remotely; unsafe to auto-retry or power off."""
    execution_uncertain = True

    def __init__(self, status: int, detail: str, *, prompt_id: str = ''):
        super().__init__(status, detail)
        self.prompt_id = prompt_id


class ComfyBatchSession:
    """Reuse the same bounded HTTP client and graph preflight within ONE batch.

    ComfyUI owns model-weight/VRAM caching. Neo never promises to pin a model
    or bypass ComfyUI's memory management. One sequential inference at a time.
    """
    def __init__(self, profile: dict, config: dict):
        self.base = normalize_endpoint(profile['endpoint'])
        self.profile_id = profile['id']
        self.config = config
        self.client = None
        self.checked = False
        self.completed = 0

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(25,connect=4,read=25,write=25,pool=5),
                                        trust_env=False,follow_redirects=False)
        return self

    async def __aexit__(self, *args):
        if self.client is not None:
            await self.client.aclose()
        self.client = None
        self.checked = False

    async def preflight(self):
        if not self.checked:
            await _preflight(self.client, self.base, self.config)
            self.checked = True


MAX_RESPONSE = 16 * 1024 * 1024  # /object_info can be large on node-heavy ComfyUI installations

async def _json(client: httpx.AsyncClient, method: str, url: str, **kw):
    try:
        async with client.stream(method, url, **kw) as response:
            if response.is_redirect:
                raise ProviderFailure(502, 'ComfyUI redirected an API request. Check the local endpoint.')
            if response.status_code >= 400:
                raise ProviderFailure(502, f'ComfyUI returned HTTP {response.status_code}; inspect its console and node dependencies.')
            size, blocks = 0, []
            async for part in response.aiter_bytes():
                size += len(part)
                if size > MAX_RESPONSE:
                    raise ProviderFailure(502, 'ComfyUI response exceeded the 16 MB safety limit.')
                blocks.append(part)
            return json.loads(b''.join(blocks))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProviderFailure(502, 'ComfyUI returned invalid JSON.') from exc

async def _preflight(client, base, config):
    classes = {node['class_type'] for node in config['graph'].values()}
    try:
        data = await _json(client, 'GET', base + '/object_info')
        if not isinstance(data, dict):
            raise ProviderFailure(502, 'ComfyUI did not return node metadata.')
        missing = sorted(classes - set(data))
    except ProviderFailure as exc:
        # A node-heavy installation can exceed the bulk /object_info response cap.
        # Use individually queried classes as a bounded fallback, not a larger unbounded read.
        if 'safety limit' not in exc.detail or len(classes) > 100:
            raise
        missing = []
        from urllib.parse import quote
        for class_name in sorted(classes):
            item = await _json(client,'GET',base+'/object_info/'+quote(class_name,safe=''))
            if not isinstance(item,dict) or class_name not in item:
                missing.append(class_name)
    if missing:
        raise ProviderFailure(422,'Workflow needs missing ComfyUI node classes: ' + ', '.join(missing[:10]))

async def _execute_with_client(client, base, config, *, prompt, image_path, mime, system_prompt, timeout_seconds):
    filename = None
    if image_path is not None:
        # Upload a bounded copy of a file already validated in Neo Prompt's media store.
        raw = image_path.read_bytes()
        if len(raw) > 10 * 1024 * 1024:
            raise ProviderFailure(413, 'Selected image exceeds the 10 MB upload limit.')
        filename = 'neo_prompt_' + uuid4().hex + image_path.suffix.lower()
        uploaded = await _json(client,'POST',base+'/upload/image', files={'image':(filename,raw,mime or 'image/png')}, data={'overwrite':'false','type':'input'})
        if not isinstance(uploaded,dict) or not isinstance(uploaded.get('name'),str):
            raise ProviderFailure(502,'ComfyUI did not confirm the image upload.')
        filename = uploaded['name']
    try:
        graph = bind_graph(config, text=prompt, uploaded_filename=filename, system_prompt=system_prompt)
    except WorkflowError as exc:
        raise ProviderFailure(422,str(exc)) from exc
    job = await _json(client,'POST',base+'/prompt', json={'prompt':graph,'client_id':'neo-prompt-'+uuid4().hex})
    if not isinstance(job,dict) or not isinstance(job.get('prompt_id'),str):
        raise ProviderFailure(502,'ComfyUI did not issue a prompt ID; check workflow validation errors in its console.')
    prompt_id=job['prompt_id']
    # This is polling only our own prompt's history; never enumerate/delete global queue/history.
    deadline=asyncio.get_running_loop().time()+timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(1.5)
        try:
            history = await _json(client,'GET',base+'/history/'+prompt_id)
        except ProviderFailure as exc:
            raise ComfyExecutionUncertain(exc.status, 'ComfyUI accepted prompt '+prompt_id+' but history could not be checked. Inspect its queue before resuming or retrying.', prompt_id=prompt_id) from exc
        if not isinstance(history,dict) or prompt_id not in history:
            continue
        detail = history[prompt_id]
        status = detail.get('status') or {}
        if status.get('status_str') in ('error','failed') or status.get('completed') is False:
            raise ProviderFailure(502,'ComfyUI workflow execution failed; inspect its history/console. Nothing was saved.')
        if not status.get('completed') and not detail.get('outputs'):
            continue
        try:
            output=extract_history_text(config, detail)
        except WorkflowError as exc:
            raise ProviderFailure(502, str(exc)) from exc
        pe_meta = {}
        if config.get('auto_route') in ('qwen_pe_t2i','qwen_pe_i2i'):
            from .qwen_pe import metadata_from_history
            pe_meta = metadata_from_history(config,detail)
        return {'text': output,'prompt_id':prompt_id,'finish_reason':'stop', 'pe_metadata':pe_meta,
                'runtime_model': config.get('auto_model'), 'runtime_model_state':'selected_from_live_catalog' if config.get('auto_model') else 'not_exposed_by_workflow', 'workflow_name':config['name']}
    raise ComfyExecutionUncertain(504, 'ComfyUI prompt '+prompt_id+' is still unconfirmed after the wait limit. Check its queue/history before resuming or retrying; automatic shutdown was disarmed.', prompt_id=prompt_id)


async def execute(profile: dict, config: dict, *, prompt: str, image_path: Path | None = None, mime: str | None = None,
                  system_prompt: str = '', timeout_seconds: int = 900, session: ComfyBatchSession | None = None) -> dict:
    if profile.get('kind') != 'comfyui' or config['profile_id'] != profile.get('id') or not config.get('trusted'):
        raise ProviderFailure(422, 'Select an explicitly trusted workflow belonging to this ComfyUI profile.')
    base = normalize_endpoint(profile['endpoint'])
    try:
        if session is not None:
            if session.client is None or session.profile_id != profile['id'] or session.base != base or session.config is not config:
                raise ProviderFailure(422, 'The Batch execution session does not match the selected ComfyUI graph or backend.')
            await session.preflight()
            result = await _execute_with_client(session.client, base, config, prompt=prompt, image_path=image_path,
                                                mime=mime, system_prompt=system_prompt, timeout_seconds=timeout_seconds)
            session.completed += 1
            return result
        timeout = httpx.Timeout(25, connect=4, read=25, write=25, pool=5)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False) as client:
            await _preflight(client, base, config)
            return await _execute_with_client(client, base, config, prompt=prompt, image_path=image_path,
                                              mime=mime, system_prompt=system_prompt, timeout_seconds=timeout_seconds)
    except (httpx.ConnectError,httpx.ConnectTimeout) as exc:
        raise ProviderFailure(503,'ComfyUI is unreachable at the selected loopback endpoint.') from exc
    except httpx.TimeoutException as exc:
        raise ComfyExecutionUncertain(504, 'ComfyUI transport timed out. Processing may continue remotely; inspect its queue before resuming or retrying.') from exc
    except (httpx.RequestError,OSError) as exc:
        raise ComfyExecutionUncertain(502, 'ComfyUI transport failed; queued work may continue remotely. Check its queue before resuming.') from exc

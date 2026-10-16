"""Standalone Neo Prompt local API with app-owned backend profiles."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote
import asyncio
from typing import Literal, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .connections import ConnectionConfigError, normalize_endpoint, probe
from .security import bootstrap_session, local_guard
from .storage import DataStore, timestamp
from .settings import DATA_DIR
from .generation import ProviderFailure, generate, reformat_existing, refine_selected
from .output_contract import assess
from .profile_contract import get_profile_manifest, normalize_profile
from .images import ImageError, save_image, image_path, MAX_IMAGE_BYTES
from .vision import caption_image, TASKS
from .batches import new_job, run_job, job_progress, export_zip
from .library_browser import browse
from .library_organization import category_label, entry_name
from .power import PowerCoordinator, windows_supported
from .comfy_workflows import validate_definition, WorkflowError
from .comfy_adapter import execute as execute_comfy
from .comfy_auto import inspect as inspect_comfy_auto, discover as discover_comfy_auto, prepare as prepare_comfy_auto
from .generation import process_prompt_reply, clamp_params, compile_messages
from .comfy_prompt_quality import messages_for_comfy, review_comfy_result, refinement_result
from .qwen_pe import apply_pe_review

UI_DIR = Path(__file__).resolve().parent / "ui"
PROMPT_TASKS = {"text_to_image", "text_image_edit", "text_to_video"}


def task_profile(profile: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_profile(profile, surface="prompt_studio")["profile"]
    if normalized.get("prompt_task") not in PROMPT_TASKS:
        raise HTTPException(422, "Supported prompt tasks are text-to-image, text-image-edit and text-to-video.")
    return normalized


class ProfileBody(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    kind: Literal["koboldcpp", "comfyui"]
    endpoint: str = Field(min_length=7, max_length=200)


class ProfileSelectionBody(BaseModel):
    profile_id: str = Field(default="", max_length=100)


class DraftBody(BaseModel):
    text: str = Field(max_length=20000)
    task: str = Field(default="", max_length=64)



class GenerationParams(BaseModel):
    temperature: float = Field(default=0.7, ge=0, le=2)
    top_p: float = Field(default=0.9, ge=0, le=1)
    max_tokens: int = Field(default=512, ge=1, le=8192)
    top_k: int | None = Field(default=None, ge=0, le=1000)


class PromptWorkspace(BaseModel):
    profile_id: str = Field(default="", max_length=100)
    operation: Literal["generate", "enhance", "rewrite", "negative"] = "generate"
    prompt_profile: dict[str, Any] = Field(default_factory=dict)
    params: GenerationParams = Field(default_factory=GenerationParams)
    custom_instruction: str = Field(default="", max_length=4000)
    workflow_id: str = Field(default="", max_length=40)
    auto_route: str = Field(default="", max_length=32)
    auto_model: str = Field(default="", max_length=300)
    auto_mmproj: str = Field(default="", max_length=300)
    auto_chat_handler: str = Field(default="", max_length=120)
    runtime_options: dict[str, Any] = Field(default_factory=dict)


class PromptGeneration(PromptWorkspace):
    source: str = Field(min_length=1, max_length=20000)


class RefineRequest(BaseModel):
    operation: Literal["enhance", "rewrite", "negative"]


class SavedPromptBody(BaseModel):
    title: str = Field(default="", max_length=120)
    name: str = Field(default="", max_length=120)
    category: str = Field(default="General", max_length=64)
    text: str = Field(min_length=1, max_length=32000)
    source: str = Field(default="", max_length=20000)
    operation: Literal["generate", "enhance", "rewrite", "negative"] = "generate"
    origin_run_id: str = Field(default="", max_length=50)
    name: str = Field(default="", max_length=120)
    category: str = Field(default="General", max_length=64)


class CaptionGeneration(BaseModel):
    profile_id: str = Field(min_length=1, max_length=100)
    image_id: str = Field(min_length=32, max_length=32, pattern=r'^[0-9a-f]{32}$')
    task: Literal['describe','recreate','edit','video','dataset'] = 'describe'
    instruction: str = Field(default='', max_length=4000)
    trigger: str = Field(default='', max_length=90)
    options: dict[str, str] = Field(default_factory=dict)
    workflow_id: str = Field(default="", max_length=40)
    auto_route: str = Field(default="", max_length=32)
    auto_model: str = Field(default="", max_length=300)
    auto_mmproj: str = Field(default="", max_length=300)
    auto_chat_handler: str = Field(default="", max_length=120)
    runtime_options: dict[str, Any] = Field(default_factory=dict)

class SavedCaption(BaseModel):
    name: str = Field(default="", max_length=120)
    category: str = Field(default="General", max_length=64)
    image_id: str = Field(min_length=32, max_length=32, pattern=r'^[0-9a-f]{32}$')
    text: str = Field(min_length=1, max_length=32000)
    task: str = Field(default='describe', max_length=40)
    origin_run_id: str = Field(default='', max_length=50)

class BatchCreation(BaseModel):
    category: str = Field(default="", max_length=64)
    profile_id: str = Field(min_length=1, max_length=100)
    image_ids: list[str] = Field(min_length=1)
    notes: str = Field(default='', max_length=4000)
    trigger: str = Field(default='', max_length=90)
    options: dict[str, str] = Field(default_factory=dict)
    mode: Literal['dataset', 'library'] = 'dataset'
    shutdown_enabled: bool = False
    shutdown_confirmed: bool = False
    workflow_id: str = Field(default="", max_length=40)
    auto_route: str = Field(default="", max_length=32)
    auto_model: str = Field(default="", max_length=300)
    auto_mmproj: str = Field(default="", max_length=300)
    auto_chat_handler: str = Field(default="", max_length=120)
    runtime_options: dict[str, Any] = Field(default_factory=dict)

class BatchResumeConfirmation(BaseModel):
    backend_queue_checked: bool = False

class ComfyAutoSelectionBody(BaseModel):
    profile_id: str = Field(min_length=1, max_length=100)
    mode: Literal['auto','custom'] = 'auto'
    route: str = Field(default='', max_length=32)
    model: str = Field(default='', max_length=300)
    mmproj: str = Field(default='', max_length=300)
    chat_handler: str = Field(default='', max_length=120)
    runtime_options: dict[str, Any] = Field(default_factory=dict)

class ComfyWorkflowBody(BaseModel):
    name: str
    profile_id: str
    task: str
    mode: str = 'generic'
    graph: dict[str, Any]
    text_node: str
    text_field: str = 'prompt'
    image_node: str = ''
    image_field: str = 'image'
    output_node: str
    output_field: str = 'text'
    trusted: bool = False

class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class LibraryNameChange(BaseModel):
    category: str = Field(default="General", max_length=64)
    name: str = Field(default="", max_length=120)


class PresetBody(BaseModel):
    name: str = Field(min_length=1, max_length=90)
    settings: PromptWorkspace



def create_app(data_dir: Path | None = None) -> FastAPI:
    store = DataStore(data_dir if data_dir is not None else DATA_DIR)
    app = FastAPI(title="Neo Prompt", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.middleware("http")(local_guard)
    prompt_run_lock = asyncio.Lock()
    vision_run_lock = asyncio.Lock()
    batch_manager_lock = asyncio.Lock()
    batch_tasks: dict[str, asyncio.Task] = {}
    store.interrupt_orphan_batches()
    power = PowerCoordinator(store)
    power.disarm_on_startup()

    def get_workflow(profile: dict, workflow_id: str, task: str) -> dict:
        if profile['kind'] != 'comfyui':
            raise HTTPException(422, 'This is not a ComfyUI connection.')
        workflow = next((w for w in store.comfy_workflows() if w['id'] == workflow_id), None)
        if not workflow or workflow['profile_id'] != profile['id'] or workflow['task'] != task or not workflow.get('trusted'):
            raise HTTPException(422, 'Select a trusted ComfyUI workflow matching this exact task and connection. No automatic fallback is used.')
        return workflow
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

    def refresh_prompt_quality() -> list[dict[str, Any]]:
        """Re-check older Ready ratings against current quality rules, preserving original text.

        This is monotonic (never automatically upgrades earlier review decisions).
        Older results whose format errors escaped earlier checks become
        review-required and remain in history instead of being silently reused.
        """
        items = store.prompt_runs()
        for item in items:
            if item.get('quality_status', 'ready') != 'ready':
                continue
            data = item.get('prompt_profile') or {}
            fmt = data.get('output_format')
            op = item.get('operation')
            task = item.get('task')
            mode = ('negative' if op == 'negative' else 'edit' if task == 'text_image_edit' else
                    'video' if task == 'text_to_video' else 'tags' if fmt == 'sd_tags' else
                    'structured' if fmt == 'structured_prompt' else 'caption' if fmt == 'descriptive_caption' else 'prompt')
            verdict = assess(item.get('text', ''), mode=mode,
                             finish_reason=item.get('finish_reason', ''))
            if verdict.status != 'ready':
                updated = store.edit_prompt_run(item['id'], {
                    'quality_status': verdict.status, 'quality_issues': list(verdict.issues),
                    'review_approved': False,
                    'warnings': list(dict.fromkeys((item.get('warnings') or []) + list(verdict.issues)))
                })
                if updated:
                    item.update(updated)
        return items

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(UI_DIR / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/health")
    def health():
        return {"app": "neo_prompt", "version": __version__, "status": "running", "generation_available": True, "generation_backends": ["koboldcpp", "comfyui_auto", "comfyui_workflow"], "vision_available": True, "vision_backends": ["koboldcpp", "comfyui_auto", "comfyui_workflow"]}

    @app.get("/api/v1/bootstrap")
    def bootstrap(request: Request, response: Response):
        csrf = bootstrap_session(request, response)
        return {"app": "neo_prompt", "version": __version__, "csrf": csrf,
                "profiles": store.profiles(), "data_root": str(store.root),
                "generation_available": True, "generation_backends": ["koboldcpp", "comfyui_auto", "comfyui_workflow"], "vision_available": True, "vision_backends": ["koboldcpp", "comfyui_auto", "comfyui_workflow"]}

    @app.get('/api/v1/comfy/workflows')
    def list_comfy_workflows():
        # Graph contents are executable implementation details; public list omits their bytes.
        return {'items': [{k:v for k,v in w.items() if k != 'graph'} for w in store.comfy_workflows()]}

    @app.get('/api/v1/comfy/auto/selections')
    def comfy_auto_selections():
        return {'items':store.comfy_auto_selections()}

    @app.put('/api/v1/comfy/auto/selections/{workspace}')
    def put_comfy_auto_selection(workspace:Literal['prompt','caption','batch'],body:ComfyAutoSelectionBody):
        profile=next((p for p in store.profiles() if p['id']==body.profile_id and p['kind']=='comfyui'),None)
        if profile is None:raise HTTPException(422,'Select an existing ComfyUI profile.')
        settings={'mode':body.mode,'route':body.route,'model':body.model,'mmproj':body.mmproj,'chat_handler':body.chat_handler,'runtime_options':body.runtime_options}
        store.save_comfy_auto_selection(workspace,body.profile_id,settings)
        return {'selection':settings}

    @app.get('/api/v1/comfy/auto/capabilities')
    async def comfy_auto_capabilities(profile_id: str):
        profile = next((p for p in store.profiles() if p['id']==profile_id and p['kind']=='comfyui'), None)
        if not profile:raise HTTPException(422,'Choose a saved ComfyUI connection first.')
        try:return discover_comfy_auto(await inspect_comfy_auto(profile))
        except ProviderFailure as exc:raise HTTPException(exc.status,exc.detail) from exc

    async def select_comfy(profile:dict, workflow_id:str, task:str, route:str, model:str, mmproj:str='', params=None, chat_handler:str='', runtime_options=None):
        if workflow_id:
            if runtime_options:raise HTTPException(422, 'Automatic runtime tuning does not modify Advanced custom workflows.')
            return get_workflow(profile,workflow_id,task)
        if not route or not model:
            raise HTTPException(422,'Select an automatic ComfyUI route and a detected model, or choose an Advanced custom workflow.')
        try:return await prepare_comfy_auto(profile,route=route,model=model,mmproj=mmproj,chat_handler=chat_handler,task=task,params=params,runtime_options=runtime_options)
        except ProviderFailure as exc:raise HTTPException(exc.status,exc.detail) from exc

    @app.post('/api/v1/comfy/workflows', status_code=201)
    def add_comfy_workflow(body: ComfyWorkflowBody):
        profile = next((p for p in store.profiles() if p['id'] == body.profile_id and p['kind'] == 'comfyui'), None)
        if not profile: raise HTTPException(422, 'Choose an existing ComfyUI connection.')
        try:
            data=validate_definition(body.model_dump())
        except WorkflowError as exc:
            raise HTTPException(422,str(exc)) from exc
        data.update(id=uuid4().hex, created_at=timestamp())
        store.save_comfy_workflow(data)
        return {k:v for k,v in data.items() if k != 'graph'}

    @app.delete('/api/v1/comfy/workflows/{workflow_id}')
    def remove_comfy_workflow(workflow_id: str):
        if not store.delete_comfy_workflow(workflow_id):
            raise HTTPException(404, 'Workflow not found.')
        return {'removed': True}

    @app.get("/api/v1/profiles")
    def list_profiles():
        return {"items": store.profiles()}

    @app.post("/api/v1/profiles", status_code=201)
    def add_profile(body: ProfileBody):
        try:
            endpoint = normalize_endpoint(body.endpoint)
        except ConnectionConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        item = {"id": str(uuid4()), "name": body.name.strip(), "kind": body.kind,
                "endpoint": endpoint, "created_at": timestamp(), "updated_at": timestamp()}
        if len(item["name"]) < 2:
            raise HTTPException(422, "Profile name must contain at least two visible characters")
        store.put_profile(item)
        return item

    @app.put("/api/v1/profiles/{profile_id}")
    def edit_profile(profile_id: str, body: ProfileBody):
        current = next((p for p in store.profiles() if p["id"] == profile_id), None)
        if not current:
            raise HTTPException(404, "Profile not found")
        try:
            endpoint = normalize_endpoint(body.endpoint)
        except ConnectionConfigError as exc:
            raise HTTPException(422, str(exc)) from exc
        update = {**current, "name": body.name.strip(), "kind": body.kind, "endpoint": endpoint, "updated_at": timestamp()}
        if len(update["name"]) < 2:
            raise HTTPException(422, "Profile name must contain at least two visible characters")
        store.put_profile(update)
        return update

    @app.delete("/api/v1/profiles/{profile_id}")
    def remove_profile(profile_id: str):
        if not store.delete_profile(profile_id):
            raise HTTPException(404, "Profile not found")
        return {"removed": True}

    @app.post("/api/v1/profiles/{profile_id}/test")
    async def test_profile(profile_id: str):
        current = next((p for p in store.profiles() if p["id"] == profile_id), None)
        if not current:
            raise HTTPException(404, "Profile not found")
        report = await probe(current["kind"], current["endpoint"])
        store.record_activity({"id": str(uuid4()), "when": timestamp(), "type": "connection_test", "profile_name": current["name"],
                               "status": "responded" if report["reachable"] else "unreachable", "message": report["message"]})
        return report

    @app.get("/api/v1/profile-selections")
    def get_profile_selections():
        return {"selections": {
            "prompt": store.prompt_workspace().get("profile_id", ""),
            **store.profile_selections(),
        }}

    @app.put("/api/v1/profile-selections/{workspace}")
    def set_profile_selection(workspace: Literal["prompt", "caption", "batch"], body: ProfileSelectionBody):
        # Selections must be explicit and executable for the selected backend.
        if body.profile_id:
            selected = next((p for p in store.profiles() if p["id"] == body.profile_id), None)
            if selected is None:
                raise HTTPException(422, "This saved backend profile no longer exists.")
            # Automatic ComfyUI connections do not require imported workflow JSON.
            # Model/node readiness is checked on the automatic route at generation time.
        if workspace == "prompt":
            settings = store.prompt_workspace()
            settings["profile_id"] = body.profile_id
            store.save_prompt_workspace(settings)
        else:
            store.save_profile_selection(workspace, body.profile_id)
        return {"workspace": workspace, "profile_id": body.profile_id}

    @app.get("/api/v1/drafts/{kind}")
    def get_draft(kind: Literal["prompt", "caption"]):
        return store.draft(kind)

    @app.put("/api/v1/drafts/{kind}")
    def set_draft(kind: Literal["prompt", "caption"], body: DraftBody):
        return store.save_draft(kind, body.text, body.task)

    @app.get("/api/v1/activity")
    def activity():
        return {"items": store.activities()}

    @app.get("/api/v1/prompt/manifest")
    def prompt_manifest():
        manifest = get_profile_manifest()
        return {"profile_schema": "prompt_captioning.profile.v1", "manifest": manifest}

    @app.get("/api/v1/prompt/workspace")
    def prompt_workspace():
        return {"settings": store.prompt_workspace()}

    @app.put("/api/v1/prompt/workspace")
    def set_prompt_workspace(body: PromptWorkspace):
        data = body.model_dump()
        data["prompt_profile"] = task_profile(data["prompt_profile"])
        store.save_prompt_workspace(data)
        return {"settings": data}

    @app.post("/api/v1/prompt/generate")
    async def generate_prompt(body: PromptGeneration):
        source = body.source.strip()
        if not source:
            raise HTTPException(422, "Enter a source idea before generating.")
        if len(str(body.prompt_profile)) > 16000:
            raise HTTPException(422, "Prompt profile is too large.")
        task_profile(body.prompt_profile)
        current = next((p for p in store.profiles() if p["id"] == body.profile_id), None)
        if current is None:
            raise HTTPException(422, 'Choose a saved backend connection in Prompt Studio.')
        workflow = await select_comfy(current,body.workflow_id,task_profile(body.prompt_profile)['prompt_task'],body.auto_route,body.auto_model,body.auto_mmproj,body.params.model_dump(),body.auto_chat_handler,body.runtime_options) if current['kind']=='comfyui' else None
        if prompt_run_lock.locked():
            raise HTTPException(409, "A prompt is already generating. Wait for it to finish before starting another.")
        async with prompt_run_lock:
            try:
                if workflow:
                    if body.operation != 'generate':
                        raise ProviderFailure(422, 'ComfyUI workflow generation supports Generate. Use the separate KoboldCPP refinement actions for now.')
                    normalized = task_profile(body.prompt_profile)
                    # Qwen PE consumes a short source prompt; generic LLM workflows receive a full contract.
                    system_text = ''
                    if workflow['mode'].startswith('qwen_pe'):
                        source_text = source + ('\nRequested visual treatment: ' + normalized['visual_treatment'].replace('_',' ') if normalized.get('visual_treatment') not in ('source_accurate',None,'') else '') + ('\nAdditional requirements: ' + body.custom_instruction if body.custom_instruction.strip() else '')
                    else:
                        msgs, normalized = (messages_for_comfy(source, body.custom_instruction, 'generate', body.prompt_profile)
                                             if workflow.get('auto_route') == 'llm' else
                                             compile_messages(source, body.custom_instruction, 'generate', body.prompt_profile))
                        if workflow.get('auto_route') in ('llm','vlm','vlm_mtmd'):
                            system_text, source_text = msgs[0]['content'], msgs[1]['content']
                        else:
                            source_text = msgs[0]['content'] + '\n\n' + msgs[1]['content']
                    response = await execute_comfy(current, workflow, prompt=source_text, system_prompt=system_text)
                    gen = {}  # ComfyUI graph owns actual sampling; do not claim Prompt Studio knobs were applied
                    result = process_prompt_reply(response['text'],finish='stop',source=source,
                              instruction=body.custom_instruction, operation='generate',normalized=normalized,generation=gen)
                    if workflow.get('auto_route') == 'llm':
                        review_comfy_result(result, raw=response['text'])
                    elif workflow.get('auto_route') == 'qwen_pe_t2i':
                        apply_pe_review(result, response.get('pe_metadata') or {})
                        result['pe_metadata'] = response.get('pe_metadata') or {}
                    result['runtime_model'] = response['runtime_model']
                    result['runtime_model_state'] = response['runtime_model_state']
                    result['comfy_prompt_id']=response['prompt_id']
                    result['workflow_name']=response['workflow_name']
                    if workflow.get('auto_route')=='llm' and any(n['class_type']=='llama_cpp_parameters' for n in workflow['graph'].values()):
                        result['parameters']={**body.params.model_dump(), **{k:v for k,v in workflow.get('runtime_options_applied',{}).items() if k in ('max_tokens','temperature','top_p','top_k')}}
                else:
                    result = await generate(current, source, body.custom_instruction, body.operation,
                                            body.prompt_profile, body.params.model_dump())
            except ProviderFailure as exc:
                if exc.raw_response:
                    store.record_output_issue(surface='prompt', raw=exc.raw_response,
                                              issues=list(exc.issues) or [exc.detail], profile_name=current['name'])
                store.record_activity({"id": str(uuid4()), "when": timestamp(), "type": "prompt_generation",
                                       "profile_name": current["name"], "status": "failed", "message": exc.detail})
                raise HTTPException(exc.status, exc.detail) from exc
            record = {"id": str(uuid4()), "when": timestamp(), "profile_id": current["id"],
                      "profile_name": current["name"], "operation": body.operation,
                      "task": result["profile"].get("prompt_task", ""), "source": source,
                      "custom_instruction": body.custom_instruction, "prompt_profile": result["profile"],
                      "parameters": result["parameters"], "text": result["text"],
                      "warnings": result["warnings"], "finish_reason": result["finish_reason"],
                      "quality_status": result["quality_status"], "quality_issues": result["quality_issues"],
                      "runtime_model": result.get("runtime_model"), "runtime_model_state": result.get("runtime_model_state", "unavailable"),
                      "workflow_id": body.workflow_id or None, "comfy_prompt_id": result.get('comfy_prompt_id'), "workflow_name": result.get('workflow_name'), "comfy_auto_route": workflow.get('auto_route') if workflow else None,
                      "comfy_auto_model": workflow.get('auto_model') if workflow else None,
                      "comfy_auto_mmproj": body.auto_mmproj if workflow else "",
                      "comfy_auto_chat_handler": body.auto_chat_handler if workflow else "", "pe_metadata": result.get("pe_metadata"), "comfy_tuning_applied": workflow.get("runtime_options_applied",{}) if workflow else {},
                      "review_approved": False, "reformat_attempted": False,
                      "parent_run_id": None, "root_run_id": None, "lineage_depth": 0, "positive_run_id": None}
            store.add_prompt_run(record)
            if record['quality_status'] == 'needs_review':
                store.record_output_issue(surface='prompt-review', raw=result.get('text', ''),
                                          issues=record['quality_issues'], profile_name=current['name'])
            store.record_activity({"id": record["id"], "when": record["when"], "type": "prompt_generation",
                                   "profile_name": current["name"], "status": "completed", "message": "Generated " + body.operation + " prompt"})
            return {"result": record}

    @app.post('/api/v1/prompt/runs/{run_id}/refine')
    async def refine_prompt_run(run_id: str, body: RefineRequest):
        parent = next((r for r in refresh_prompt_quality() if r['id'] == run_id), None)
        if parent is None:
            raise HTTPException(404, 'Selected generated result not found. It may have expired from recent history.')
        if parent.get('quality_status', 'ready') == 'invalid' or (parent.get('quality_status') == 'needs_review' and not parent.get('review_approved')):
            raise HTTPException(409, 'Review and approve the selected result before refining it.')
        if parent.get('operation') == 'negative':
            raise HTTPException(409, 'Select a positive prompt rather than a negative prompt to refine.')
        if int(parent.get('lineage_depth') or 0) >= 12:
            raise HTTPException(409, 'This refinement chain reached the 12-step safety limit. Start from an earlier result.')
        backend = next((p for p in store.profiles() if p['id'] == parent.get('profile_id')), None)
        if not backend:
            raise HTTPException(422, 'The selected result’s original backend is unavailable. No alternative backend was used.')
        if backend['kind'] == 'comfyui' and (parent.get('comfy_auto_route') != 'llm' or parent.get('workflow_id')):
            raise HTTPException(422, 'Output-first ComfyUI refinement supports Automatic General LLM only. Custom and Qwen graphs remain advanced workflows.')
        if prompt_run_lock.locked():
            raise HTTPException(409, 'Another prompt request is already running.')
        async with prompt_run_lock:
            try:
                if backend['kind'] == 'comfyui':
                    selected_model = parent.get('comfy_auto_model') or parent.get('runtime_model')
                    if not selected_model or parent.get('runtime_model_state') not in ('selected_from_live_catalog',):
                        raise ProviderFailure(422, 'The saved automatic model identity is unavailable. Start a new ComfyUI result before refining.')
                    previous_params = parent.get('parameters') or {}
                    params = clamp_params({'temperature':float(previous_params.get('temperature',0.7)),
                                           'top_p':float(previous_params.get('top_p',0.9)),
                                           'max_tokens':int(previous_params.get('max_tokens',512)),
                                           'top_k':previous_params.get('top_k')},body.operation=='negative')
                    # Inherit parent route tuning; Negative keeps its safer independent sampling caps.
                    inherited_tuning = dict(parent.get('comfy_tuning_applied') or {})
                    if body.operation == 'negative':
                        for field in ('temperature','top_p','top_k','max_tokens'):
                            inherited_tuning.pop(field,None)
                    # Live model catalog verification on every child. Do not switch to currently selected UI model.
                    workflow = await prepare_comfy_auto(backend,route='llm',model=selected_model,
                                                         task=parent.get('task','text_to_image'),params=params,runtime_options=inherited_tuning)
                    messages, normalized = messages_for_comfy(parent['text'], '', body.operation,
                                                                parent.get('prompt_profile') or {})
                    response = await execute_comfy(backend,workflow,prompt=messages[1]['content'],
                                                    system_prompt=messages[0]['content'])
                    effective_params = ({**params, **{k:v for k,v in workflow.get('runtime_options_applied',{}).items() if k in ('max_tokens','temperature','top_p','top_k')}}
                                        if any(n['class_type']=='llama_cpp_parameters' for n in workflow['graph'].values()) else {})
                    output = refinement_result(response['text'],parent=parent,operation=body.operation,
                                               params=effective_params,model=selected_model,
                                               prompt_id=response['prompt_id'],workflow_name=response['workflow_name'])
                else:
                    output = await refine_selected(backend, parent, body.operation)
            except ProviderFailure as exc:
                if exc.raw_response:
                    store.record_output_issue(surface='prompt-refinement', raw=exc.raw_response,
                                              issues=list(exc.issues) or [exc.detail], profile_name=backend['name'])
                store.record_activity({'id':str(uuid4()),'when':timestamp(),'type':'prompt_refinement',
                                       'profile_name':backend['name'],'status':'failed','message':exc.detail})
                raise HTTPException(exc.status, exc.detail) from exc
            record = {'id':str(uuid4()),'when':timestamp(), 'profile_id':backend['id'],
                      'profile_name':backend['name'], 'operation':body.operation,
                      'task':output['profile'].get('prompt_task', parent.get('task','')),
                      'source':parent['text'], 'custom_instruction':'',
                      'prompt_profile':output['profile'], 'parameters':output['parameters'],
                      'text':output['text'],'warnings':output['warnings'],
                      'finish_reason':output['finish_reason'], 'quality_status':output['quality_status'],
                      'quality_issues':output['quality_issues'], 'runtime_model':output.get('runtime_model'), 'runtime_model_state':output.get('runtime_model_state', 'unavailable'), 'review_approved':False,
                      'reformat_attempted':False,'parent_run_id':parent['id'],
                      'comfy_auto_route':parent.get('comfy_auto_route') if backend['kind']=='comfyui' else None,
                      'comfy_auto_model':parent.get('comfy_auto_model') or parent.get('runtime_model') if backend['kind']=='comfyui' else None,
                      'comfy_prompt_id':output.get('comfy_prompt_id'), 'workflow_name':output.get('workflow_name'),
                      'workflow_id':None,
                      'comfy_tuning_applied':workflow.get('runtime_options_applied',{}) if backend['kind']=='comfyui' else {},
                      'root_run_id':parent.get('root_run_id') or parent['id'],
                      'lineage_depth':int(parent.get('lineage_depth') or 0)+1,
                      'positive_run_id':parent['id'] if body.operation=='negative' else None}
            store.add_prompt_run(record)
            if record['quality_status']=='needs_review':
                store.record_output_issue(surface='prompt-refinement-review',raw=record['text'],
                                          issues=record['quality_issues'],profile_name=backend['name'])
            store.record_activity({'id':record['id'],'when':record['when'],'type':'prompt_refinement',
                                   'profile_name':backend['name'],'status':'completed',
                                   'message':'Refined selected output: '+body.operation})
            return {'result':record}

    @app.post('/api/v1/prompt/runs/{run_id}/approve')
    def approve_prompt_run(run_id: str):
        run = next((r for r in refresh_prompt_quality() if r['id'] == run_id), None)
        if run is None:
            raise HTTPException(404, 'Prompt result not found.')
        if run.get('quality_status', 'ready') != 'needs_review':
            raise HTTPException(409, 'Only review-required results need manual approval.')
        return {'result': store.edit_prompt_run(run_id, {'review_approved': True})}

    @app.post('/api/v1/prompt/runs/{run_id}/reformat')
    async def reformat_prompt_run(run_id: str):
        run = next((r for r in refresh_prompt_quality() if r['id'] == run_id), None)
        if run is None:
            raise HTTPException(404, 'Prompt result not found.')
        if run.get('quality_status', 'ready') != 'needs_review':
            raise HTTPException(409, 'Only results needing review can be reformatted.')
        if run.get('reformat_attempted', False):
            raise HTTPException(409, 'This result already used its one reformat attempt.')
        profile = next((p for p in store.profiles() if p['id'] == run['profile_id']), None)
        if not profile:
            raise HTTPException(422, 'Original backend connection is missing or changed.')
        if profile['kind']=='comfyui' and (run.get('comfy_auto_route')!='llm' or run.get('workflow_id')):
            raise HTTPException(422, 'Reformat supports ComfyUI Automatic General LLM only; not custom or Qwen workflows.')
        if prompt_run_lock.locked():
            raise HTTPException(409, 'A prompt generation or reformat request is already running.')
        async with prompt_run_lock:
            # Consume the one allowed attempt BEFORE the HTTP call, including transport errors.
            old = store.edit_prompt_run(run_id, {'reformat_attempted': True})
            try:
                if profile['kind']=='comfyui':
                    original = str(old.get('text') or '')
                    if not original or len(original)>12000:
                        raise ProviderFailure(422, 'Selected output is empty or too long to reformat.')
                    model = old.get('comfy_auto_model') or old.get('runtime_model')
                    if not model or old.get('runtime_model_state')!='selected_from_live_catalog':
                        raise ProviderFailure(422, 'Saved model identity is unavailable. Generate a new ComfyUI result instead.')
                    params = {'temperature':0.1,'top_p':0.8,'max_tokens':min(max(256,int((old.get('parameters') or {}).get('max_tokens',512))),768),'top_k':40}
                    loader_tuning = {k:v for k,v in (old.get('comfy_tuning_applied') or {}).items() if k in ('n_ctx','vram_limit','force_offload')}
                    workflow = await prepare_comfy_auto(profile,route='llm',model=model,task=old.get('task','text_to_image'),params=params,runtime_options=loader_tuning)
                    system_text = ('Reformat the selected output into one directly usable final answer. '
                                   'Retain all explicit subject details, identity, action, setting, camera direction and edit/preservation constraints. '
                                   'Remove only surrounding commentary and markup. Do not add new scene content or JSON. '
                                   'If there is no unambiguous single output, respond exactly CANNOT_REFORMAT.')
                    answer = await execute_comfy(profile,workflow,prompt='Existing output to reformat:\n'+original,
                                                 system_prompt=system_text)
                    if answer['text'].strip()=='CANNOT_REFORMAT':
                        raise ProviderFailure(502,'Model could not identify a safe final answer.',raw_response=answer['text'])
                    effective = params if any(n['class_type']=='llama_cpp_parameters' for n in workflow['graph'].values()) else {}
                    result = process_prompt_reply(answer['text'],finish='stop',source=old.get('source',''),
                              instruction=old.get('custom_instruction',''),operation=old.get('operation','generate'),
                              normalized=old.get('prompt_profile') or {},generation=effective)
                    review_comfy_result(result,raw=answer['text'])
                    result.update(runtime_model=model,runtime_model_state='selected_from_live_catalog',
                                  comfy_prompt_id=answer['prompt_id'],workflow_name=answer['workflow_name'])
                    result['quality_status']='needs_review'
                    issue='Model-generated reformat requires comparison with the original before saving.'
                    result['quality_issues']=list(dict.fromkeys(result['quality_issues']+[issue]))
                    result['warnings']=list(dict.fromkeys(result['warnings']+[issue]))
                else:
                    result = await reformat_existing(profile, old)
            except ProviderFailure as exc:
                if exc.raw_response:
                    store.record_output_issue(surface='prompt-reformat', raw=exc.raw_response,
                                              issues=list(exc.issues) or [exc.detail], profile_name=profile['name'])
                raise HTTPException(exc.status, exc.detail) from exc
            new_run = {**old, 'id': str(uuid4()), 'when': timestamp(), 'text': result['text'],
                       'warnings': result['warnings'], 'quality_status': result['quality_status'],
                       'quality_issues': result['quality_issues'], 'finish_reason': result['finish_reason'],
                       'parameters': result['parameters'], 'review_approved': False,
                       'runtime_model': result.get('runtime_model'), 'runtime_model_state': result.get('runtime_model_state', 'unavailable'),
                       'reformat_attempted': True, 'reformatted_from': run_id,
                       'comfy_prompt_id':result.get('comfy_prompt_id'), 'workflow_name':result.get('workflow_name'),
                       'parent_run_id':run_id,'root_run_id':old.get('root_run_id') or run_id,
                       'lineage_depth':int(old.get('lineage_depth') or 0)+1,
                       'positive_run_id':old.get('positive_run_id') if old.get('operation')=='negative' else None}
            store.add_prompt_run(new_run)
            return {'result': new_run}

    @app.get("/api/v1/prompt/runs")
    def list_prompt_runs():
        return {"items": refresh_prompt_quality()}

    @app.get("/api/v1/library/browse")
    def browse_library(kind: Literal['captions', 'prompts'] = 'captions', q: str = '',
                       collection: str = 'all', sort: str = 'newest',
                       offset: int = 0, limit: int = 20, category: str = ''):
        """Read and filter existing records without modifying their source assets."""
        try:
            records = store.saved_captions() if kind == 'captions' else store.saved_prompts()
            return browse(records, kind=kind, query=q, collection=collection,
                          sort=sort, offset=offset, limit=limit, category=category)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get('/api/v1/library/categories')
    def library_categories(kind: Literal['captions', 'prompts'] | None = None):
        # 'kind' is accepted for older frontends; the registry is shared by all tasks.
        return {'items': store.library_categories()}

    @app.post('/api/v1/library/categories', status_code=201)
    def create_library_category(body: CategoryCreate):
        if not body.name.strip():
            raise HTTPException(422, 'Category name cannot be blank.')
        try:
            name, created = store.register_library_category(body.name)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {'name': name, 'created': created, 'items': store.library_categories()}

    @app.patch('/api/v1/library/items/{kind}/{item_id}')
    def rename_library(kind: Literal['captions','prompts'], item_id: str, body: LibraryNameChange):
        try:
            entry = store.rename_library_entry(kind, item_id, category=body.category, name=body.name)
            store.register_library_category(entry['category'])
        except KeyError:
            raise HTTPException(404, 'Saved entry not found')
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {'item': entry}

    @app.get("/api/v1/prompt/saved")
    def list_saved_prompts():
        return {"items": store.saved_prompts()}

    @app.post("/api/v1/prompt/saved", status_code=201)
    def add_saved_prompt(body: SavedPromptBody):
        if body.origin_run_id:
            origin = next((r for r in refresh_prompt_quality() if r['id'] == body.origin_run_id), None)
            if origin is None or origin.get('text') != body.text:
                raise HTTPException(422, 'Saved output must match the selected generated run.')
            if origin.get('quality_status') == 'invalid' or (origin.get('quality_status') == 'needs_review' and not origin.get('review_approved')):
                raise HTTPException(409, 'Review-required output must be explicitly approved before saving to Library.')
        record = {"id": str(uuid4()), "when": timestamp(), "title": body.title.strip(),
                  "text": body.text, "source": body.source, "operation": body.operation}
        if body.origin_run_id:
            # Server-owned provenance: a client cannot relabel a negative pair
            # as an ordinary generated prompt, or forge its original source.
            record['source'] = origin.get('source', '')
            record['operation'] = origin.get('operation', body.operation)
            record['origin_run_id'] = origin['id']
            if origin.get('pe_metadata') is not None:
                record['pe_metadata'] = origin['pe_metadata']
            record['parent_run_id'] = origin.get('parent_run_id')
            if origin.get('operation') == 'negative' and origin.get('positive_run_id'):
                positive = next((r for r in store.prompt_runs() if r['id'] == origin['positive_run_id']), None)
                if positive is None or positive.get('operation') == 'negative':
                    raise HTTPException(409, 'The linked positive result is no longer available. Save the negative alone from an unpaired run or regenerate the pair.')
                record['paired_positive_run_id'] = positive['id']
                record['paired_positive_text'] = positive['text']

        try:
            record, _ = store.organize_library_entry('prompts', {**record,
                'category': body.category, 'name': body.name or body.title})
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        store.register_library_category(record['category'])
        return record

    @app.delete("/api/v1/prompt/saved/{item_id}")
    def remove_saved_prompt(item_id: str):
        if not store.delete_saved_prompt(item_id):
            raise HTTPException(404, "Saved prompt not found")
        return {"removed": True}

    @app.get("/api/v1/prompt/presets")
    def list_prompt_presets():
        return {"items": store.prompt_presets()}

    @app.post("/api/v1/prompt/presets", status_code=201)
    def add_prompt_preset(body: PresetBody):
        cfg = body.settings.model_dump()
        cfg["prompt_profile"] = task_profile(cfg["prompt_profile"])
        record = {"id": str(uuid4()), "when": timestamp(), "name": body.name.strip(), "settings": cfg}
        store.add_prompt_preset(record)
        return record

    @app.delete("/api/v1/prompt/presets/{item_id}")
    def remove_prompt_preset(item_id: str):
        if not store.delete_prompt_preset(item_id):
            raise HTTPException(404, "Preset not found")
        return {"removed": True}

    def selected_vision_profile(profile_id: str) -> dict:
        profile = next((x for x in store.profiles() if x['id'] == profile_id), None)
        if not profile:
            raise HTTPException(422, 'Select a saved KoboldCPP connection.')
        if profile['kind'] not in ('koboldcpp','comfyui'):
            raise HTTPException(422,'Unsupported vision backend.')
        return profile

    @app.post('/api/v1/caption/images', status_code=201)
    async def upload_caption_image(request: Request):
        content_type = request.headers.get('content-type','').split(';')[0].lower()
        if content_type not in ('image/png','image/jpeg','image/webp'):
            raise HTTPException(415, 'Upload a PNG, JPEG or WebP image (not a JSON/data URL).')
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_IMAGE_BYTES:
                raise HTTPException(413, 'Maximum image upload is 10 MB.')
        try:
            item = save_image(store, bytes(data), source_name=unquote(request.headers.get('x-neo-source-name','')[:500])[:220], relative_path=unquote(request.headers.get('x-neo-relative-path','')[:1000])[:500], deduplicate=request.headers.get('x-neo-dedupe','')=='1')
        except ImageError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        return {'image': item}

    @app.get('/api/v1/caption/images')
    def list_caption_images():
        return {'items': store.images(limit=300)}

    @app.get('/api/v1/caption/images/{image_id}/view')
    def get_caption_image(image_id: str):
        try:
            path, record = image_path(store, image_id)
        except ImageError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        return FileResponse(path, media_type=record['mime'], headers={'Cache-Control': 'no-store', 'Content-Disposition': 'inline'})

    @app.post('/api/v1/caption/generate')
    async def generate_caption(body: CaptionGeneration):
        profile = selected_vision_profile(body.profile_id)
        workflow = await select_comfy(profile,body.workflow_id,body.task,body.auto_route,body.auto_model,body.auto_mmproj,params={'max_tokens':1024,'temperature':0.3 if body.task=='dataset' else 0.45,'top_p':0.85,'top_k':40},chat_handler=body.auto_chat_handler,runtime_options=body.runtime_options) if profile['kind']=='comfyui' else None
        try:
            image_file, meta = image_path(store, body.image_id)
        except ImageError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        if vision_run_lock.locked():
            raise HTTPException(409, 'Another vision request is running. Wait for it to finish before retrying.')
        async with vision_run_lock:
            try:
                output = await caption_image(profile, image_file, meta['mime'], task=body.task, instruction=body.instruction, trigger=body.trigger, options=body.options,
                                             comfy_workflow=workflow)
            except ProviderFailure as exc:
                if exc.raw_response:
                    store.record_output_issue(surface='caption', raw=exc.raw_response,
                                              issues=list(exc.issues) or [exc.detail], profile_name=profile['name'])
                store.record_activity({'id': str(uuid4()), 'when': timestamp(), 'type': 'caption_generation', 'profile_name': profile['name'], 'status': 'failed', 'message': exc.detail})
                raise HTTPException(exc.status, exc.detail) from exc
        record = {'id': str(uuid4()), 'when': timestamp(), 'image_id': body.image_id, 'profile_id': profile['id'], 'profile_name': profile['name'], 'task': body.task, 'instruction': body.instruction, 'text': output['text'], 'warnings': output['warnings'], 'finish_reason': output['finish_reason'], 'quality_status': output['quality_status'], 'quality_issues': output['quality_issues'], 'review_approved': False, 'runtime_model':output.get('runtime_model'), 'runtime_model_state':output.get('runtime_model_state', 'unavailable'),
                  'workflow_id':body.workflow_id if body.workflow_id else None,'workflow_name':workflow['name'] if workflow else None,'comfy_auto_route':workflow.get('auto_route') if workflow else None, 'pe_metadata':output.get('pe_metadata'), 'comfy_tuning_applied': workflow.get('runtime_options_applied',{}) if workflow else {}}
        store.add_caption_run(record)
        store.record_activity({'id': record['id'], 'when': record['when'], 'type': 'caption_generation', 'profile_name': profile['name'], 'status': 'completed', 'message': 'Generated ' + body.task + ' caption'})
        return {'result': record}

    @app.post('/api/v1/caption/runs/{run_id}/approve')
    def approve_caption_run(run_id: str):
        run = next((r for r in store.caption_runs() if r['id'] == run_id), None)
        if run is None:
            raise HTTPException(404, 'Caption result not found.')
        if run.get('quality_status', 'ready') != 'needs_review':
            raise HTTPException(409, 'Only review-required captions need manual approval.')
        return {'result': store.edit_caption_run(run_id, {'review_approved': True})}

    @app.get('/api/v1/caption/runs')
    def caption_runs():
        return {'items': store.caption_runs()[:100]}

    @app.get('/api/v1/caption/saved')
    def caption_saved():
        return {'items': store.saved_captions()[:250]}

    @app.post('/api/v1/caption/saved', status_code=201)
    def save_caption_result(body: SavedCaption):
        if body.origin_run_id:
            run = next((r for r in store.caption_runs() if r['id'] == body.origin_run_id), None)
            if not run or run.get('text') != body.text or run.get('image_id') != body.image_id:
                raise HTTPException(422, 'Saved caption does not match an existing result.')
            if run.get('quality_status') == 'invalid' or (run.get('quality_status') == 'needs_review' and not run.get('review_approved')):
                raise HTTPException(409, 'Approve this review-required caption before saving.')
        try:
            image_path(store, body.image_id)
        except ImageError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        record = {'id': str(uuid4()), 'when': timestamp(), **body.model_dump()}
        if body.origin_run_id and run.get('pe_metadata') is not None:
            record['pe_metadata'] = run['pe_metadata']
        try:
            record, _ = store.organize_library_entry('captions', record)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        store.register_library_category(record['category'])
        return record

    @app.delete('/api/v1/caption/saved/{caption_id}')
    def delete_saved_caption(caption_id: str):
        if not store.delete_caption(caption_id):
            raise HTTPException(404, 'Saved caption not found.')
        return {'removed': True}

    @app.get('/api/v1/batch/jobs')
    def list_jobs():
        return {'items': [job_progress(j) for j in store.batches()[:25]]}

    @app.get('/api/v1/batch/jobs/{job_id}')
    def get_job(job_id: str, offset: int = 0, limit: int = 30):
        if offset < 0 or limit < 1 or limit > 100:
            raise HTTPException(422, 'Invalid batch page; limit must be 1–100.')
        job = store.batch(job_id, offset=offset, limit=limit)
        if not job:
            raise HTTPException(404, 'Batch not found.')
        return {'job': job_progress(job)}

    async def verified_batch_workflow(job: dict, profile: dict):
        """Validate live saved ComfyUI backend BEFORE changing durable queue statuses."""
        if profile['kind'] != 'comfyui':
            return None
        if job.get('backend_endpoint') and normalize_endpoint(profile['endpoint']) != job['backend_endpoint']:
            raise HTTPException(409, 'Saved Batch ComfyUI endpoint has changed. Restore the original connection before resuming.')
        return await select_comfy(profile,job.get('workflow_id',''),job.get('mode','dataset'),
                                  job.get('auto_route',''),job.get('auto_model',''),job.get('auto_mmproj',''),
                                  params={'max_tokens':1024,'temperature':0.3 if job.get('mode')=='dataset' else 0.45,
                                          'top_p':0.85,'top_k':40},chat_handler=job.get('auto_chat_handler',''),runtime_options=job.get('runtime_options') or {})

    async def begin_batch(job_id: str, profile: dict, prepared_workflow=None):
        job = store.batch_header(job_id) or {}
        if profile['kind']=='comfyui' and job.get('backend_endpoint') and normalize_endpoint(profile['endpoint']) != job['backend_endpoint']:
            raise HTTPException(409, 'Saved Batch ComfyUI endpoint has changed. Restore the original connection before resuming.')
        workflow = prepared_workflow if prepared_workflow is not None else await verified_batch_workflow(job, profile)
        task = asyncio.create_task(run_job(store, job_id, vision_run_lock, profile, comfy_workflow=workflow))
        batch_tasks[job_id] = task
        def cleanup(t):
            batch_tasks.pop(job_id, None)
            try:
                t.result()
            except BaseException:
                power.cancel(job_id,reason='interrupted')
                store.update_batch(job_id, lambda j: j.update(status='interrupted'))
            else:
                power.offer(job_id)
        task.add_done_callback(cleanup)

    @app.post('/api/v1/batch/jobs', status_code=201)
    async def create_batch(body: BatchCreation):
        if body.shutdown_enabled and (not body.shutdown_confirmed or not power.supported):
            raise HTTPException(422, 'Windows shutdown requires explicit confirmation and a Windows host.')
        profile = selected_vision_profile(body.profile_id)
        if profile['kind']=='comfyui': await select_comfy(profile,body.workflow_id,body.mode,body.auto_route,body.auto_model,body.auto_mmproj,chat_handler=body.auto_chat_handler,runtime_options=body.runtime_options)
        if len(set(body.image_ids)) != len(body.image_ids):
            raise HTTPException(422, 'Choose each batch image once.')
        if body.trigger and not all(c.isalnum() or c in '_-' for c in body.trigger):
            raise HTTPException(422, 'Trigger token may use letters, numbers, underscores or hyphens only.')
        if body.options.get('analysis_scope') == 'custom_crop':
            raise HTTPException(422, 'Custom crop requires an actual crop selection; batch processing does not support it.')
        # Indexed existence checks; do not scan a large JSON image catalogue per entry.
        image_info={}
        for image_id in body.image_ids:
            record=store.image(image_id)
            if not record:raise HTTPException(404,'One or more selected images are missing.')
            image_info[image_id]=record
        async with batch_manager_lock:
            if batch_tasks:
                raise HTTPException(409, 'Another batch is running. Finish or cancel it first.')
            from_paths = {str(v.get('relative_path', '')).replace('\\','/').split('/')[0] for v in image_info.values() if '/' in str(v.get('relative_path','')).replace('\\','/')}
            proposed = body.category or (next(iter(from_paths)) if len(from_paths) == 1 else 'Batch Library')
            try:
                chosen_category = category_label(proposed)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            power.cancel_all()  # a new batch supersedes a pending PC shutdown
            job = new_job(body.image_ids, profile, notes=body.notes, trigger=body.trigger if body.mode == 'dataset' else '', options=body.options, mode=body.mode, category=chosen_category, workflow_id=body.workflow_id)
            job.update(auto_route=body.auto_route,auto_model=body.auto_model,auto_mmproj=body.auto_mmproj,auto_chat_handler=body.auto_chat_handler,runtime_options=body.runtime_options)
            if profile['kind']=='comfyui':
                job['backend_endpoint'] = normalize_endpoint(profile['endpoint'])
            job.update(shutdown_enabled=body.shutdown_enabled, shutdown_state='armed' if body.shutdown_enabled else 'disabled')
            for entry in job['items']:
                metadata=image_info[entry['image_id']]
                entry['source_name']=metadata.get('source_name') or metadata.get('name','')
                entry['relative_path']=metadata.get('relative_path','')
            store.add_batch(job)
            store.register_library_category(chosen_category)
            await begin_batch(job['id'], profile)
        return {'job':job_progress(store.batch(job['id']))}

    @app.post('/api/v1/batch/jobs/{job_id}/cancel')
    def cancel_batch(job_id: str):
        job = store.batch(job_id)
        if not job:
            raise HTTPException(404, 'Batch not found.')
        power.cancel(job_id)
        if job['status'] in ('running', 'queued', 'paused', 'pause_requested'):
            if job['status']=='paused':
                store.bulk_item_status(job_id,('queued',),'cancelled')
                job=store.update_batch(job_id,lambda j:j.update(status='cancelled'))
            else:
                job = store.update_batch(job_id, lambda j: j.update(status='cancel_requested'))
        return {'job': job_progress(job)}

    @app.post('/api/v1/batch/jobs/{job_id}/pause')
    def pause_batch(job_id: str):
        job=store.batch(job_id,limit=0)
        if not job:raise HTTPException(404,'Batch not found.')
        if job['status'] in ('running','queued'):
            power.cancel(job_id,reason='disarmed_on_pause')
            job=store.update_batch(job_id,lambda j:j.update(status='pause_requested'))
        return {'job':job_progress(job)}

    @app.post('/api/v1/batch/jobs/{job_id}/resume')
    async def resume_batch(job_id: str, body: BatchResumeConfirmation | None = None):
        async with batch_manager_lock:
            if batch_tasks:raise HTTPException(409,'Another batch is already running.')
            job=store.batch(job_id,limit=0)
            if not job:raise HTTPException(404,'Batch not found.')
            if job['status'] not in ('paused','interrupted'):
                raise HTTPException(409,'Only paused or interrupted jobs can resume.')
            if job.get('backend_check_required') and not (body and body.backend_queue_checked):
                raise HTTPException(409,'Check the ComfyUI queue/history for unfinished prompts, then explicitly confirm before resuming.')
            profile=selected_vision_profile(job['profile_id'])
            prepared=await verified_batch_workflow(job,profile)
            power.cancel_all()
            power.cancel(job_id,reason='disarmed_on_resume')
            store.promote_legacy_batch(job_id)
            store.bulk_item_status(job_id,('interrupted',),'queued')
            store.update_batch(job_id,lambda j:j.update(status='queued',backend_check_required=False))
            await begin_batch(job_id,profile,prepared)
            job=store.batch(job_id)
        return {'job':job_progress(job)}

    @app.post('/api/v1/batch/jobs/{job_id}/retry')
    async def retry_batch(job_id: str):
        async with batch_manager_lock:
            if batch_tasks:
                raise HTTPException(409, 'A batch is already running.')
            job = store.batch(job_id)
            if not job:
                raise HTTPException(404, 'Batch not found.')
            if job['status'] not in ('failed', 'completed_with_errors', 'interrupted', 'cancelled'):
                raise HTTPException(409, 'This batch cannot be retried in its current state.')
            if job.get('backend_check_required'):
                raise HTTPException(409, 'Check ComfyUI queue/history before retrying an uncertain request. Resume remaining items first.')
            profile = selected_vision_profile(job['profile_id'])
            prepared=await verified_batch_workflow(job,profile)
            power.cancel_all()
            power.cancel(job_id,reason='disarmed_on_retry')
            store.promote_legacy_batch(job_id)
            store.bulk_item_status(job_id,('failed','interrupted','cancelled','running'),'queued')
            job=store.update_batch(job_id,lambda j:j.update(status='queued',shutdown_enabled=False,shutdown_state='disabled',shutdown_deadline=None))
            await begin_batch(job_id,profile,prepared)
        return {'job': job_progress(job)}

    @app.post('/api/v1/batch/jobs/{job_id}/retry-failed')
    async def retry_failed_batch(job_id: str):
        """Retry only failed items, never successful ones. Requires an explicit user request."""
        async with batch_manager_lock:
            if batch_tasks:
                raise HTTPException(409, 'Another batch is running.')
            job=store.batch(job_id,limit=0)
            if not job:
                raise HTTPException(404,'Batch not found.')
            if job['status'] not in ('completed_with_errors','failed'):
                raise HTTPException(409,'Only finished jobs with errors can retry failed items.')
            if job.get('backend_check_required'):
                raise HTTPException(409,'Check the ComfyUI queue before retrying an uncertain request.')
            if not job['counts'].get('failed'):
                raise HTTPException(409,'No failed items are available for retry.')
            profile=selected_vision_profile(job['profile_id'])
            prepared=await verified_batch_workflow(job,profile)
            power.cancel_all()
            store.promote_legacy_batch(job_id)
            store.bulk_item_status(job_id,('failed',),'queued')
            store.update_batch(job_id, lambda j:j.update(status='queued',shutdown_enabled=False,shutdown_state='disabled',shutdown_deadline=None))
            await begin_batch(job_id,profile,prepared)
            return {'job':job_progress(store.batch(job_id))}

    @app.post('/api/v1/batch/jobs/{job_id}/shutdown/cancel')
    def cancel_batch_shutdown(job_id: str):
        job=store.batch_header(job_id)
        if not job:raise HTTPException(404,'Batch not found.')
        if not power.cancel(job_id):
            raise HTTPException(409,'No armed or pending shutdown for this job.')
        return {'job':job_progress(store.batch(job_id))}

    @app.get('/api/v1/batch/power-capabilities')
    def batch_power_capabilities():
        return {'windows_shutdown_supported':power.supported,'countdown_seconds':power.countdown,
                'default_enabled':False}

    @app.post('/api/v1/batch/jobs/{job_id}/items/{index}/approve')
    def approve_batch_item(job_id: str, index: int):
        job = store.batch(job_id,limit=0)
        if not job:raise HTTPException(404,'Batch not found.')
        if index < 0 or index >= job['total']:raise HTTPException(404,'Batch item not found.')
        item=store.batch_item(job_id,index)
        if item['status'] != 'completed' or item.get('quality_status')!='needs_review':
            raise HTTPException(409,'Only completed review-required items can be approved.')
        if item.get('review_approved'):
            return {'job':job_progress(store.batch(job_id))}
        saved_id=''
        if job.get('mode')=='library':
            from .batches import _save_library
            saved_id=_save_library(store,job_id,item['image_id'],item,approved=True)
        store.update_batch_item(job_id,index,{'review_approved':True,'saved_caption_id':saved_id})
        return {'job':job_progress(store.batch(job_id))}

    @app.get('/api/v1/batch/jobs/{job_id}/export')
    def export_batch(job_id: str):
        job = store.batch(job_id,limit=0)
        if not job:
            raise HTTPException(404, 'Batch not found.')
        if not job.get('exportable'):
            raise HTTPException(409, 'No completed image/caption pairs to export.')
        try:
            path = export_zip(store, job)
        except ImageError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        return FileResponse(path, filename='neo_prompt_dataset_' + job_id[:10] + '.zip', media_type='application/zip', background=BackgroundTask(lambda: path.unlink(missing_ok=True)))

    @app.get("/api/v1/settings")
    def settings():
        return {"data_root": str(store.root), "local_only": True, "generation_available": True, "generation_backends": ["koboldcpp"],
                "vision_available": True, "batch_available": True, "legacy_import_available": False, "theme": "neo-dark", "backend_access": "loopback_only"}

    return app


app = create_app()

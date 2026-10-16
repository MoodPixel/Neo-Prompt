"""Local, explicitly trusted ComfyUI API-format text/vision workflow definitions.

A Comfy workflow is user-supplied code in effect: importing never executes it;
execution requires explicit trust and a matching profile/task. Neo never loads nodes.
"""
from __future__ import annotations
import copy
import json
from typing import Any

TASKS = {'text_to_image', 'text_image_edit', 'text_to_video',
         'describe', 'recreate', 'edit', 'video', 'dataset', 'library'}
PE_KINDS = {'generic', 'qwen_pe_t2i', 'qwen_pe_i2i'}
MAX_GRAPH_BYTES = 2 * 1024 * 1024

class WorkflowError(ValueError):
    pass


def validate_definition(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise WorkflowError('Workflow definition must be a JSON object.')
    graph = data.get('graph')
    if not isinstance(graph, dict) or not 1 <= len(graph) <= 1200:
        raise WorkflowError('Import an API-format ComfyUI graph (1–1200 nodes), not the editor workflow format.')
    if len(json.dumps(graph, ensure_ascii=False).encode('utf-8')) > MAX_GRAPH_BYTES:
        raise WorkflowError('Workflow exceeds the 2 MB safe import limit.')
    for node_id, node in graph.items():
        if not isinstance(node_id, str) or not node_id.isdigit() or not isinstance(node, dict) or not isinstance(node.get('class_type'), str) or not isinstance(node.get('inputs'), dict):
            raise WorkflowError('Invalid API-format node. Export using ComfyUI “Save (API Format)”.')
        if len(node['class_type']) > 160:
            raise WorkflowError('Unrecognized node class.')
    task = data.get('task')
    mode = data.get('mode', 'generic')
    if task not in TASKS or mode not in PE_KINDS:
        raise WorkflowError('Select a supported task and workflow type.')
    if mode == 'qwen_pe_t2i' and task != 'text_to_image':
        raise WorkflowError('Qwen PE-T2I is reserved for Text → Image prompts.')
    if mode == 'qwen_pe_i2i' and task != 'edit':
        raise WorkflowError('Qwen PE-I2I requires the Caption Studio Image → Edit task and an uploaded reference image.')
    if not data.get('trusted') is True:
        raise WorkflowError('Explicit trust approval is required: imported ComfyUI graphs can execute custom nodes.')
    name = str(data.get('name', '')).strip()
    if not 2 <= len(name) <= 90:
        raise WorkflowError('Workflow name must be 2–90 characters.')
    inp = str(data.get('text_node', ''))
    inp_field = str(data.get('text_field', 'prompt'))
    out = str(data.get('output_node', ''))
    if inp not in graph or inp_field not in graph[inp]['inputs'] or not isinstance(graph[inp]['inputs'][inp_field], str):
        raise WorkflowError('Text binding must identify an existing editable STRING input on a node.')
    if out not in graph:
        raise WorkflowError('Output binding must identify a node whose text is exposed in ComfyUI /history.')
    if not data.get('output_field', 'text') in ('text', 'string', 'result'):
        raise WorkflowError('Output field must be text, string, or result.')
    image_node = str(data.get('image_node', '')).strip()
    image_field = str(data.get('image_field', 'image'))
    if task in ('describe','recreate','edit','video','dataset','library'):
        if image_node not in graph or image_field not in graph[image_node]['inputs'] or not isinstance(graph[image_node]['inputs'][image_field], str):
            raise WorkflowError('Vision workflows must bind a Load Image (or equivalent filename STRING) input.')
    elif image_node:
        raise WorkflowError('Prompt Studio workflows cannot silently use an image input.')
    if not str(data.get('profile_id', '')):
        raise WorkflowError('Choose a saved ComfyUI connection first.')
    return {'name':name,'profile_id':str(data['profile_id']),'task':task,'mode':mode,
            'graph':copy.deepcopy(graph),'text_node':inp,'text_field':inp_field,
            'image_node':image_node,'image_field':image_field,
            'output_node':out,'output_field':str(data.get('output_field', 'text')),
            'trusted':True}


def bind_graph(config: dict[str, Any], *, text: str, uploaded_filename: str | None = None, system_prompt: str = '') -> dict[str, Any]:
    if not text.strip() or len(text) > 24000:
        raise WorkflowError('Source text is empty or exceeds the 24,000-character limit.')
    graph = copy.deepcopy(config['graph'])
    # Auto-generated llama.cpp graphs have a dedicated system field. Imported
    # workflows don't gain authority to bind arbitrary nodes through this path.
    system_node = config.get('system_node') if config.get('auto_route') else ''
    if system_node:
        field = config.get('system_field')
        if (system_node not in graph or field != 'system_prompt' or
                graph[system_node]['inputs'].get(field) != '__NEO_AUTO_SYSTEM__'):
            raise WorkflowError('Automatic workflow system binding is no longer valid.')
        graph[system_node]['inputs'][field] = system_prompt
    elif config.get('auto_route') in ('llm','vlm','vlm_mtmd') and system_prompt:
        # Some node revisions lack a system_prompt socket; preserve the
        # instructions explicitly rather than silently dropping them.
        text = 'TASK INSTRUCTIONS:\n' + system_prompt + '\n\nUSER REQUEST:\n' + text
    graph[config['text_node']]['inputs'][config['text_field']] = text
    if config['image_node']:
        if not uploaded_filename:
            raise WorkflowError('This workflow requires a reference image.')
        graph[config['image_node']]['inputs'][config['image_field']] = uploaded_filename
    return graph


def extract_history_text(config: dict[str, Any], history: dict[str, Any]) -> str:
    outputs = history.get('outputs') or {}
    block = outputs.get(config['output_node']) or {}
    field = config.get('output_field', 'text')
    value = block.get(field)
    if value is None and isinstance(block.get('ui'), dict):
        value = block['ui'].get(field)
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError('No text was exposed by the selected output node in ComfyUI history. Connect a compatible Show Text / output bridge and bind its node ID.')
    if len(value) > 32000:
        raise WorkflowError('Text output exceeds Neo Prompt’s 32,000-character limit.')
    return value

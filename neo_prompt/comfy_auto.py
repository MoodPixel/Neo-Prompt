"""small, task-owned ComfyUI inference graphs, not a workflow editor.

Supports *advertised* llama.cpp nodes and Qwen Image 2.1 PE rewrite nodes.
No arbitrary class selection, silent fallback, global Comfy queue control or Neo-app link.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import httpx
from .connections import normalize_endpoint
from .generation import ProviderFailure
from .comfy_adapter import _json
from .route_tuning import advertised_controls, checked_tuning

TEXT_LOADER='llama_cpp_model_loader'
LEGACY_TEXT_LOADER='llama_cpp_loader'
TEXT_INSTRUCT='llama_cpp_instruct_adv'
PARAMS='llama_cpp_parameters'
MTMD_LOADER='NeoGenericMTMDModelLoader'
MTMD_INSTRUCT='NeoGenericMTMDInstruct'
NEO_OUTPUT='NeoPromptCaptionTextOutput'
PE_OUTPUT='NeoPromptPEResultOutput'
DEFERRED_SYSTEM='__NEO_AUTO_SYSTEM__'
Q_T2I='QwenImage21_T2IPromptRewrite'
Q_EDIT='QwenImage21_EditPromptRewrite'
MAX_DISCOVERY = 16*1024*1024
# LoadImage.image choices list *existing* ComfyUI input files. Auto graphs are
# compiled before /upload/image, so the deferred filename is not in that list.
DEFERRED_IMAGE = "__NEO_AUTO_IMAGE__"

def _fields(info, cls):
    record=info.get(cls) or {}
    inp=record.get('input') or {}
    return {**(inp.get('optional') or {}), **(inp.get('required') or {})}

def _choices(spec):
    return [v for v in spec[0] if isinstance(v,str)] if isinstance(spec,(list,tuple)) and spec and isinstance(spec[0],list) else []

def _options(info, cls, field):return _choices(_fields(info,cls).get(field))

def _has(info, cls, *fields):return cls in info and all(f in _fields(info,cls) for f in fields)

def _loader(info):
    # Do not assume every installation has the same llama.cpp custom-node pack.
    # Prefer the ComfyUI-llama-cpp_vlm / Studio V2 class when it is present.
    for cls in (TEXT_LOADER, LEGACY_TEXT_LOADER):
        if cls in info:
            return cls
    return TEXT_LOADER

def _present_projectors(names):
    return [x for x in names if x.casefold() not in ('none','null','off','')]

def _compatibility(info, *, loader, models, bridge, instruct_ok, vision_field, mmproj, handlers):
    issues=[]
    if loader not in info: issues.append('Missing llama.cpp model loader (llama_cpp_model_loader or llama_cpp_loader).')
    elif not _has(info,loader,'model'): issues.append('The llama.cpp loader does not advertise a model input.')
    elif not models: issues.append('The llama.cpp loader is installed but advertises no GGUF models. Check the model folder configured for this node pack, then restart or refresh ComfyUI.')
    if TEXT_INSTRUCT not in info:issues.append('Missing llama_cpp_instruct_adv inference node.')
    elif not instruct_ok:issues.append('llama_cpp_instruct_adv is installed but does not advertise llama_model and custom_prompt inputs.')
    if not bridge:issues.append('Missing NeoPromptCaptionTextOutput history-visible text-output bridge.')
    vision=[]
    if not vision_field:vision.append('Inference node does not advertise an image input (images/image_*).')
    if not _has(info,'LoadImage','image'):vision.append('Missing ComfyUI LoadImage.image input.')
    if not _present_projectors(mmproj):vision.append('No vision projector (mmproj) is advertised; None is not a vision projector.')
    usable=[h for h in handlers if h.casefold() not in ('none','null','off','')]
    if 'chat_handler' in _fields(info,loader) and not usable:vision.append('No vision-capable chat handlers are advertised.')
    return issues, vision

def _pe_output_indices(info, node):
    # ComfyUI exposes actual output names/types, which can differ across node versions.
    names=[str(x).casefold() for x in (info.get(node,{}).get('output_name') or [])]
    types=info.get(node,{}).get('output') or []
    return {name:index for index,name in enumerate(names) if index < len(types)}


def _pe_metadata_bridge(info, node):
    names=_pe_output_indices(info,node)
    available=_has(info,PE_OUTPUT,'text','parse_ok','wh_ratio','ratio_follow')
    types=info.get(node,{}).get('output') or []
    return bool(available and all(key in names for key in ('positive_prompt','parse_ok','wh_ratio'))
                and types[names['positive_prompt']]=='STRING'
                and types[names['parse_ok']]=='BOOLEAN'
                and types[names['wh_ratio']]=='STRING'
                and ('ratio_follow' not in names or types[names['ratio_follow']]=='STRING'))


def _pe_diagnostics(info, *, model_names, base_ok, node, kind):
    missing=[]
    if not _has(info,'CLIPLoader','clip_name','type') or 'qwen_image' not in _options(info,'CLIPLoader','type'):
        missing.append('Compatible CLIPLoader with qwen_image type not installed.')
    if node not in info:
        missing.append(f'Missing {node} prompt-rewrite node.')
    if not model_names:
        missing.append(f'No Qwen Image 2.1 PE-{kind.upper()} checkpoint advertised by CLIPLoader.')
    if not (_has(info,NEO_OUTPUT,'text') or _pe_metadata_bridge(info,node)):
        missing.append('Missing compatible Neo Prompt text-output bridge or typed PE metadata outputs.')
    return missing


def _is_pe_model(name, kind):
    import re
    key=re.sub(r'[^a-z0-9]+','_',Path(name.replace('\\','/')).name.lower())
    return 'qwen' in key and 'image' in key and ('2_1' in key or '21' in key) and 'pe' in key and (('t2i' in key) if kind=='t2i' else ('i2i' in key or 'edit' in key))

def discover(info: dict[str,Any]) -> dict:
    """Advertise only detected compatible routes, with actionable missing-component details."""
    loader=_loader(info)
    bridge=_has(info,NEO_OUTPUT,'text')
    pe_bridge=_has(info,PE_OUTPUT,'text')
    models=_options(info,loader,'model')
    mmp=_options(info,loader,'mmproj')
    handlers=_options(info,loader,'chat_handler')
    instruct_ok=_has(info,TEXT_INSTRUCT,'llama_model','custom_prompt')
    fields=_fields(info,TEXT_INSTRUCT)
    image_input='images' if 'images' in fields else next((f for f in fields if f.startswith('image_')),None)
    issues,vision_issues=_compatibility(info,loader=loader,models=models,bridge=bridge,instruct_ok=instruct_ok,vision_field=image_input,mmproj=mmp,handlers=handlers)
    # A required parameters input must be satisfiable by a parameters node.
    if 'parameters' in (info.get(TEXT_INSTRUCT,{}).get('input',{}).get('required') or {}) and PARAMS not in info:
        issues.append('Inference node requires llama_cpp_parameters, which is missing.')
    text_ok=not issues
    vision_ok=text_ok and not vision_issues
    generic_models=_options(info,MTMD_LOADER,'model')
    generic_mmproj=_present_projectors(_options(info,MTMD_LOADER,'mmproj'))
    generic_ok=bridge and _has(info,MTMD_LOADER,'model','mmproj') and _has(info,MTMD_INSTRUCT,'mtmd_model','image','custom_prompt') and _has(info,'LoadImage','image')
    pe_names=_options(info,'CLIPLoader','clip_name')
    clip_ok=_has(info,'CLIPLoader','clip_name','type') and 'qwen_image' in _options(info,'CLIPLoader','type')
    t2i_ok=clip_ok and (bridge or _pe_metadata_bridge(info,Q_T2I)) and _has(info,Q_T2I,'clip','prompt')
    edit_ok=clip_ok and (bridge or _pe_metadata_bridge(info,Q_EDIT)) and _has(info,Q_EDIT,'clip','prompt','image_1') and _has(info,'LoadImage','image')
    text_details=issues
    vlm_details=issues+vision_issues
    result = {'routes':{
       'llm':{'available':text_ok,'models':models if text_ok else [],'mmproj':[],'sampling':text_ok and _has(info,PARAMS,'max_tokens'), 'missing':text_details,'loader':loader if loader in info else None},
       'vlm':{'available':vision_ok,'models':models if vision_ok else [],'mmproj':_present_projectors(mmp) if vision_ok else [],'handlers':[x for x in handlers if x.casefold() not in ('none','null','off','')] if vision_ok else [],'missing':vlm_details,'loader':loader if loader in info else None},
       'vlm_mtmd':{'available':bool(generic_ok and generic_models and generic_mmproj),'models':generic_models if generic_ok else [],'mmproj':generic_mmproj if generic_ok else [],'missing':[] if generic_ok and generic_models and generic_mmproj else ['Generic MTMD node(s), model, projector or text-output bridge not available.']},
       'qwen_pe_t2i':{'available':bool(t2i_ok and any(_is_pe_model(x,'t2i') for x in pe_names)), 'models':[x for x in pe_names if t2i_ok and _is_pe_model(x,'t2i')],'mmproj':[], 'missing':_pe_diagnostics(info,model_names=[x for x in pe_names if _is_pe_model(x,'t2i')],base_ok=t2i_ok,node=Q_T2I,kind='t2i'), 'parse_metadata_supported':_pe_metadata_bridge(info,Q_T2I)},
       'qwen_pe_i2i':{'available':bool(edit_ok and any(_is_pe_model(x,'i2i') for x in pe_names)), 'models':[x for x in pe_names if edit_ok and _is_pe_model(x,'i2i')],'mmproj':[], 'missing':_pe_diagnostics(info,model_names=[x for x in pe_names if _is_pe_model(x,'i2i')],base_ok=edit_ok,node=Q_EDIT,kind='i2i')+([] if _has(info,'LoadImage','image') else ['Missing LoadImage for PE-I2I reference.']), 'parse_metadata_supported':_pe_metadata_bridge(info,Q_EDIT)},
    },'bridge_installed':bridge,'status':'detected' if bridge else 'missing_text_output_bridge',
    'llama_loader_detected':loader if loader in info else None,
    'llama_models_advertised':len(models), 'llama_instruct_detected':TEXT_INSTRUCT in info}
    for key, data in result['routes'].items():
        data['controls'] = advertised_controls(info, key, loader=loader) if data['available'] else {}
    return result

async def inspect(profile:dict):
    base=normalize_endpoint(profile['endpoint'])
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15,connect=3),trust_env=False,follow_redirects=False) as client:
            data=await _json(client,'GET',base+'/object_info')
        if not isinstance(data,dict):raise ProviderFailure(502,'ComfyUI returned invalid node metadata.')
        return data
    except httpx.RequestError as exc:raise ProviderFailure(503,'Unable to query ComfyUI /object_info on the selected local runtime.') from exc

def _input_default(spec):
    if not isinstance(spec,(tuple,list)) or len(spec)<2 or not isinstance(spec[1],dict):return None
    return spec[1].get('default')

def _value(info,cls,desired):
    record=info[cls]; meta=record.get('input') or {}; required=meta.get('required') or {}; optional=meta.get('optional') or {}
    merged={}
    for field,spec in required.items():
        if field in desired and desired[field] is not None: val=desired[field]
        else:
            val=_input_default(spec)
            if val is None:
                choices=_choices(spec)
                if len(choices)==1: val=choices[0]
                else:raise ProviderFailure(422,f'Automatic route cannot safely supply required {cls}.{field}. Choose a different supported node/model.')
        # A LoadImage filename is not known until /upload/image succeeds.
        # This exception is deliberately limited to our private placeholder
        # and the exact LoadImage.image input; every model/handler enumeration
        # remains validated against ComfyUI's advertised choices.
        deferred_image = (cls == 'LoadImage' and field == 'image' and val == DEFERRED_IMAGE)
        if isinstance(val,str) and _choices(spec) and val not in _choices(spec) and not deferred_image:
            raise ProviderFailure(422,f'{cls}.{field} is not offered by the current ComfyUI node catalog.')
        merged[field]=val
    for field,val in desired.items():
        if field in optional and val is not None:
            if isinstance(val,str) and _choices(optional[field]) and val not in _choices(optional[field]):raise ProviderFailure(422,f'{cls}.{field} is not offered by the current ComfyUI node catalog.')
            merged[field]=val
    return merged

def compile_auto(info, profile, *, route:str, model:str, mmproj:str='', chat_handler:str='', task:str, params:dict|None=None, runtime_options:dict|None=None) -> dict:
    """Build an internal graph with an editable text node and optional image-file binding."""
    live=discover(info)['routes']; support=live.get(route)
    if not support or not support['available']:
        details=' '.join(support.get('missing',[])) if support else 'Unknown route.'
        raise ProviderFailure(422,'Automatic '+route+' route unavailable: '+details)
    if model not in support['models']:raise ProviderFailure(422,'Selected model is not in ComfyUI’s current advertised catalog. Refresh models and select again.')
    vision_task=task in ('describe','recreate','edit','video','dataset','library')
    if vision_task and route not in ('vlm','vlm_mtmd','qwen_pe_i2i'):raise ProviderFailure(422,'This task needs a vision-capable automatic route.')
    if not vision_task and route not in ('llm','qwen_pe_t2i'):raise ProviderFailure(422,'This text task needs a text generation route.')
    if route=='qwen_pe_t2i' and task!='text_to_image':raise ProviderFailure(422,'Qwen PE-T2I is only available for Text → Image.')
    if route=='qwen_pe_i2i' and task!='edit':raise ProviderFailure(422,'Qwen PE-I2I is only available for Image → Edit.')
    if route in ('vlm','vlm_mtmd') and (not mmproj or mmproj not in support['mmproj']):raise ProviderFailure(422,'Select a detected vision projector (mmproj); no model-specific defaults are guessed.')
    p=params or {}
    tuning = checked_tuning(info, route, runtime_options or {}, loader=_loader(info))
    # Existing Prompt Studio sampling is also subject to the node's live ranges;
    # never let a legacy UI value bypass the same preflight used for overrides.
    available = advertised_controls(info, route, loader=_loader(info))
    checked_tuning(info, route, {k:v for k,v in p.items() if k in available and k not in tuning and v is not None}, loader=_loader(info))
    graph={}; image_node=''; text_node=''; text_field=''; output=''; system_node=''
    if route=='vlm_mtmd':
        graph['1']={'class_type':MTMD_LOADER,'inputs':_value(info,MTMD_LOADER,{'model':model,'mmproj':mmproj,'n_ctx':tuning.get('n_ctx',8192),'vram_limit':tuning.get('vram_limit',-1)})}
        image_node='2';graph[image_node]={'class_type':'LoadImage','inputs':_value(info,'LoadImage',{'image':DEFERRED_IMAGE})}
        text_node='3';text_field='custom_prompt'
        graph[text_node]={'class_type':MTMD_INSTRUCT,'inputs':_value(info,MTMD_INSTRUCT,{'mtmd_model':['1',0],'image':['2',0],'custom_prompt':'__NEO_AUTO_TEXT__','system_prompt':DEFERRED_SYSTEM,'max_tokens':tuning.get('max_tokens',p.get('max_tokens',768)),'top_k':tuning.get('top_k',p.get('top_k',40)),'top_p':tuning.get('top_p',p.get('top_p',0.9)),'temperature':tuning.get('temperature',p.get('temperature',0.45)),'force_offload':tuning.get('force_offload',task not in ('dataset','library'))})}
        output='4'
        if 'system_prompt' in graph[text_node]['inputs']:system_node=text_node
    elif route in ('llm','vlm'):
        loader_cls=_loader(info)
        loader={'model':model,'n_ctx':tuning.get('n_ctx',8192),'vram_limit':tuning.get('vram_limit',-1)}
        if 'mmproj' in _fields(info,loader_cls):
            choices=_options(info,loader_cls,'mmproj')
            loader['mmproj']=mmproj if route=='vlm' else ('None' if 'None' in choices else (choices[0] if len(choices)==1 else None))
        if 'chat_handler' in _fields(info,loader_cls):
            handlers=_options(info,loader_cls,'chat_handler')
            if route=='vlm':
                compatible=support.get('handlers',[])
                if chat_handler:
                    if chat_handler not in compatible:raise ProviderFailure(422,'Selected vision chat handler is not advertised by the current loader.')
                    loader['chat_handler']=chat_handler
                elif len(compatible)==1:loader['chat_handler']=compatible[0]
                else:raise ProviderFailure(422,'Select a detected vision chat handler; Neo will not guess which family matches your model.')
            elif 'None' in handlers:loader['chat_handler']='None'
            elif 'auto' in handlers:loader['chat_handler']='auto'
            elif 'Auto' in handlers:loader['chat_handler']='Auto'
            elif len(handlers)==1:loader['chat_handler']=handlers[0]
            else:raise ProviderFailure(422,'Select an Advanced custom workflow for an ambiguous required text chat handler.')
        # llama.cpp's Qwen-VL MTMD decoder explicitly warns that grounding
        # needs at least 1024 image tokens. Apply only to a user-selected
        # Qwen vision chat handler and only when the installed loader exposes
        # this setting. Never infer a handler or change unrelated models.
        if route=='vlm' and chat_handler.lower().startswith('qwen') and 'image_min_tokens' in _fields(info,loader_cls):
            if 'image_min_tokens' in tuning and tuning['image_min_tokens']<1024:
                raise ProviderFailure(422, 'Selected Qwen-VL handler requires at least 1024 minimum image tokens for grounding; clear the override or choose 1024+.')
            spec=_fields(info,loader_cls)['image_min_tokens']
            bounds=spec[1] if isinstance(spec,(list,tuple)) and len(spec)>1 and isinstance(spec[1],dict) else {}
            if int(bounds.get('max',4096))>=1024:
                loader['image_min_tokens']=max(1024,int(tuning.get('image_min_tokens',p.get('image_min_tokens',1024))))
        if route=='vlm' and 'image_max_tokens' in tuning:
            loader['image_max_tokens']=tuning['image_max_tokens']
        graph['1']={'class_type':loader_cls,'inputs':_value(info,loader_cls,loader)}
        nextid=2; paramref=None
        if _has(info,PARAMS,'max_tokens'):
            graph[str(nextid)]={'class_type':PARAMS,'inputs':_value(info,PARAMS,{'max_tokens':tuning.get('max_tokens',p.get('max_tokens',512)),'top_k':tuning.get('top_k',p.get('top_k',40)),'top_p':tuning.get('top_p',p.get('top_p',0.9)),'temperature':tuning.get('temperature',p.get('temperature',0.7)),'state_uid':-1})}
            paramref=[str(nextid),0];nextid+=1
        imref=None
        if route=='vlm':
            image_node=str(nextid);graph[image_node]={'class_type':'LoadImage','inputs':_value(info,'LoadImage',{'image':DEFERRED_IMAGE})};imref=[image_node,0];nextid+=1
        text_node=str(nextid);text_field='custom_prompt'
        data={'llama_model':['1',0],'custom_prompt':'__NEO_AUTO_TEXT__', 'preset_prompt':'Empty - Nothing','system_prompt':DEFERRED_SYSTEM, 'inference_mode':'one by one','force_offload':tuning.get('force_offload',False),'save_states':False,'parameters':paramref}
        if imref:
            field='images' if 'images' in _fields(info,TEXT_INSTRUCT) else next(f for f in _fields(info,TEXT_INSTRUCT) if f.startswith('image_'))
            data[field]=imref
        graph[text_node]={'class_type':TEXT_INSTRUCT,'inputs':_value(info,TEXT_INSTRUCT,data)}
        if 'system_prompt' in graph[text_node]['inputs']:system_node=text_node
        output=str(nextid+1)
    else:
        graph['1']={'class_type':'CLIPLoader','inputs':_value(info,'CLIPLoader',{'clip_name':model,'type':'qwen_image'})}
        rewrite=Q_T2I if route=='qwen_pe_t2i' else Q_EDIT
        inputs={'clip':['1',0],'prompt':'__NEO_AUTO_TEXT__'}
        if route=='qwen_pe_i2i':
            image_node='2';graph[image_node]={'class_type':'LoadImage','inputs':_value(info,'LoadImage',{'image':DEFERRED_IMAGE})}
            inputs['image_1']=['2',0]
            for f in [f for f in _fields(info,rewrite) if f.startswith('image_') and f!='image_1']:
                # Optional image sockets are left absent; required ones cannot be guessed.
                pass
            text_node='3';output='4'
        else:text_node='2';output='3'
        # A PE model owns its sampling. Limit output only if this exact node advertises a cap.
        for key in ('max_new_tokens','max_tokens','max_output_tokens'):
            if key in tuning and key in _fields(info,rewrite):inputs[key]=tuning[key]
        text_field='prompt';graph[text_node]={'class_type':rewrite,'inputs':_value(info,rewrite,inputs)}
    result_node=PE_OUTPUT if route.startswith('qwen_pe_') and _pe_metadata_bridge(info,rewrite) else NEO_OUTPUT
    bridge_inputs={'text':[text_node,0]}
    if result_node == PE_OUTPUT:
        positions=_pe_output_indices(info,rewrite)
        bridge_inputs['text']=[text_node,positions['positive_prompt']]
        bridge_inputs.update(parse_ok=[text_node,positions['parse_ok']],wh_ratio=[text_node,positions['wh_ratio']])
        if 'ratio_follow' in positions:
            bridge_inputs['ratio_follow']=[text_node,positions['ratio_follow']]
    graph[output]={'class_type':result_node,'inputs':bridge_inputs}
    return {'name':'Auto · '+route+' · '+Path(model.replace('\\','/')).name,'profile_id':profile['id'], 'task':task,'mode':'qwen_pe_t2i' if route=='qwen_pe_t2i' else ('qwen_pe_i2i' if route=='qwen_pe_i2i' else 'generic'),
      'graph':graph,'runtime_options_applied':tuning,'text_node':text_node,'text_field':text_field,'system_node':system_node,'system_field':'system_prompt' if system_node else '', 'image_node':image_node,'image_field':'image','output_node':output,'output_field':'text','trusted':True,'auto_model':model,'auto_route':route, 'pe_metadata_verified':result_node == PE_OUTPUT if route.startswith('qwen_pe_') else False}

async def prepare(profile, *,route,model,mmproj='',chat_handler='',task,params=None,runtime_options=None):
    info=await inspect(profile)
    return compile_auto(info,profile,route=route,model=model,mmproj=mmproj,chat_handler=chat_handler,task=task,params=params,runtime_options=runtime_options)

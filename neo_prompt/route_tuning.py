"""capability-gated ComfyUI settings. Do not emulate nonexistent node sockets."""
from __future__ import annotations
from .generation import ProviderFailure

FIELDS = ('max_tokens','temperature','top_p','top_k','n_ctx','vram_limit','image_min_tokens','image_max_tokens','force_offload','max_new_tokens','max_output_tokens')
PE_KEYS = ('max_new_tokens','max_tokens','max_output_tokens')
# Application safety bounds apply when the installed node omits its own limits.
SAFETY = {'temperature':(0,2),'top_p':(0,1),'top_k':(0,1000),'max_tokens':(1,8192),
          'max_new_tokens':(1,32768),'max_output_tokens':(1,32768),
          'n_ctx':(1024,327680),'vram_limit':(-1,1024),
          'image_min_tokens':(0,4096),'image_max_tokens':(0,4096)}

def _spec(info, cls, key):
    section=(info.get(cls) or {}).get('input') or {}
    return (section.get('required') or {}).get(key) or (section.get('optional') or {}).get(key)

def advertised_controls(info, route, *, loader='llama_cpp_model_loader'):
    """Give UI exact ranges/defaults advertised by installed node types, not invented knobs."""
    specs=[]
    if route in ('llm','vlm'):
        specs=[(loader, ('n_ctx','vram_limit','image_min_tokens','image_max_tokens') if route=='vlm' else ('n_ctx','vram_limit')),
               ('llama_cpp_parameters',('temperature','top_p','top_k','max_tokens')),
               ('llama_cpp_instruct_adv',('force_offload',))]
    elif route=='vlm_mtmd':
        specs=[('NeoGenericMTMDModelLoader',('n_ctx','vram_limit')),
               ('NeoGenericMTMDInstruct',('temperature','top_p','top_k','max_tokens','force_offload'))]
    elif route in ('qwen_pe_t2i','qwen_pe_i2i'):
        name='QwenImage21_T2IPromptRewrite' if route.endswith('t2i') else 'QwenImage21_EditPromptRewrite'
        # Only truly advertised caps; do not assume generic sampling affects Qwen PE.
        specs=[(name,PE_KEYS)]
    result={}
    for cls, names in specs:
        for key in names:
            raw=_spec(info,cls,key)
            if not isinstance(raw,(tuple,list)) or not raw:continue
            typ=str(raw[0]).upper() if isinstance(raw[0],str) else ''
            if typ not in ('INT','FLOAT','BOOLEAN'):continue
            cfg=raw[1] if len(raw)>1 and isinstance(raw[1],dict) else {}
            record={'type':typ.lower(),'node':cls}
            for prop in ('default','min','max','step'):
                if prop in cfg:record[prop]=cfg[prop]
            if key in SAFETY:
                low,high=SAFETY[key]
                record['min']=max(low,record.get('min',low))
                record['max']=min(high,record.get('max',high))
            result[key]=record
    return result

def checked_tuning(info, route, provided, *, loader='llama_cpp_model_loader'):
    if not isinstance(provided,dict):raise ProviderFailure(422,'Route settings must be an object.')
    controls=advertised_controls(info,route,loader=loader)
    if len(provided)>len(FIELDS):raise ProviderFailure(422,'Too many runtime settings.')
    result={}
    for key,value in provided.items():
        if key not in FIELDS or key not in controls:
            raise ProviderFailure(422,f'{key} is not an available setting for this ComfyUI route. Refresh detected nodes.')
        spec=controls[key]
        if spec['type']=='boolean':
            if type(value) is not bool:raise ProviderFailure(422,f'{key} requires true/false.')
        else:
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not __import__('math').isfinite(value):
                raise ProviderFailure(422,f'{key} requires a finite number.')
            if spec['type']=='int' and not isinstance(value,int):
                raise ProviderFailure(422,f'{key} requires an integer.')
            if 'min' in spec and value < spec['min'] or 'max' in spec and value > spec['max']:
                raise ProviderFailure(422,f'{key} falls outside the installed node range.')
        result[key]=value
    # The ComfyUI llama.cpp Qwen handler requires >=1024 for useful image grounding;
    # maintain the preexisting constraint even when users tune the other fields.
    if result.get('image_max_tokens',0)>0 and result.get('image_min_tokens',0)>result['image_max_tokens']:
        raise ProviderFailure(422,'Maximum image tokens cannot be lower than minimum image tokens.')
    return result

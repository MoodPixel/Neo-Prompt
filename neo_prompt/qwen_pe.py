"""Qwen Image 2.1 PE result health, not a model-specific prompt parser.

Official PE returns positive text, parse health and aspect-ratio hints.
Never mistake missing parser health for confirmed success.
"""
from __future__ import annotations
from .generation import ProviderFailure


def metadata_from_history(config: dict, history: dict) -> dict:
    if not config.get('pe_metadata_verified'):
        return {'parse_ok':None,'wh_ratio':'','ratio_follow':'','verified':False}
    block=(history.get('outputs') or {}).get(config['output_node']) or {}
    ui=block.get('ui') or {}
    def one(name):
        val=ui.get(name)
        return val[0] if isinstance(val,list) and len(val)==1 else None
    ok=one('parse_ok')
    # A string 'false' is not truthy parser success.
    if type(ok) is not bool:
        raise ProviderFailure(502,'Qwen PE output bridge did not return a boolean parse_ok state.')
    ratio=one('wh_ratio')
    follow=one('ratio_follow')
    if ratio is not None and not isinstance(ratio,str):
        raise ProviderFailure(502,'Qwen PE returned invalid aspect-ratio metadata.')
    if follow is not None and not isinstance(follow,str):
        raise ProviderFailure(502,'Qwen PE returned invalid ratio-follow metadata.')
    return {'parse_ok':ok,'wh_ratio':ratio or '', 'ratio_follow':follow or '', 'verified':True}


def apply_pe_review(result: dict, metadata: dict) -> dict:
    if metadata.get('parse_ok') is True and metadata.get('verified') is True:
        return result
    issue=('Qwen PE could not parse its final structured answer; check the generated text and retry if needed.'
           if metadata.get('parse_ok') is False else
           'Qwen PE parser health was not exposed by the installed text bridge. Review this result before saving.')
    result['quality_status']='needs_review'
    result['quality_issues']=list(dict.fromkeys(result.get('quality_issues',[])+[issue]))
    result['warnings']=list(dict.fromkeys(result.get('warnings',[])+[issue]))
    return result

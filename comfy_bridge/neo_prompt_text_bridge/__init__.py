"""Optional, app-bundled ComfyUI history-output bridge. Copy folder to ComfyUI/custom_nodes/."""
class NeoPromptCaptionTextOutput:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'text': ('STRING', {'forceInput': True, 'multiline': True})}}
    RETURN_TYPES=()
    FUNCTION='output'
    OUTPUT_NODE=True
    CATEGORY='Neo Prompt/Text'
    def output(self,text):
        return {'ui':{'text':[str(text)]},'result':()}
class NeoPromptPEResultOutput:
    """History-visible Qwen prompt and parser health. Not a graph editor."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'text': ('STRING', {'forceInput':True, 'multiline':True}),
                             'parse_ok': ('BOOLEAN', {'forceInput':True}),
                             'wh_ratio': ('STRING', {'forceInput':True})},
                'optional': {'ratio_follow': ('STRING', {'forceInput':True})}}
    RETURN_TYPES=()
    FUNCTION='output'
    OUTPUT_NODE=True
    CATEGORY='Neo Prompt/Text'

    def output(self, text, parse_ok, wh_ratio, ratio_follow=''):
        # Some node packs expose a single result as a one-element list.
        # Multiple candidates require user choice; never join them implicitly.
        if isinstance(text,(tuple,list)):
            if len(text)!=1 or not isinstance(text[0],str):
                raise ValueError('PE returned multiple prompts; Neo Prompt requires exactly one text result.')
            text=text[0]
        if not isinstance(text,str) or not text.strip():
            raise ValueError('PE returned no usable positive prompt.')
        return {'ui': {'text':[text], 'parse_ok':[bool(parse_ok)],
                       'wh_ratio':[str(wh_ratio or '')], 'ratio_follow':[str(ratio_follow or '')]},'result':()}

NODE_CLASS_MAPPINGS={'NeoPromptCaptionTextOutput':NeoPromptCaptionTextOutput,
                     'NeoPromptPEResultOutput':NeoPromptPEResultOutput}
NODE_DISPLAY_NAME_MAPPINGS={'NeoPromptCaptionTextOutput':'Neo Prompt Text Output',
                            'NeoPromptPEResultOutput':'Neo Prompt PE Result Output'}

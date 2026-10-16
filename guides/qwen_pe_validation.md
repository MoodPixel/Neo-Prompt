# Qwen Image 2.1 PE validation and usage

## Scope

Neo Prompt remains an independent text/caption application. Neo Spaces owns arbitrary ComfyUI workflow-to-UI authoring. **PE-T2I** expands text-to-image prompts; **PE-I2I** expands image editing instructions with reference images. Neither route renders an image or produces a dedicated negative prompt.

## Prerequisites

- A locally running ComfyUI endpoint saved under Connections, with an installed compatible Qwen PE prompt-rewrite node pack.
- Compatible PE-T2I or PE-I2I encoder checkpoints registered in ComfyUI's `CLIPLoader` as `qwen_image` type. A regular GGUF VLM or image-generation checkpoint alone does not satisfy this requirement.
- The Neo Prompt text-output bridge in ComfyUI `custom_nodes`. Install the updated bundled copy to expose parse/canvas metadata via `NeoPromptPEResultOutput` when the PE nodes advertise typed output names.

If capabilities show *unavailable*, click Detect installed models. The route now distinguishes a missing `CLIPLoader`, rewrite class, checkpoint choice, image loader or output bridge. Neo does not silently install or switch model files.

## PE-T2I

Prompt Studio → Text → Image → ComfyUI → Automatic → **Qwen PE · Text to Image** → detected PE-T2I model. Write a simple source idea and any necessary instructions, then Generate. The user reviews/copies/saves the positive prompt and checks `wh_ratio`. Sampling settings belong to the PE node; the General LLM sliders do not secretly change them.

## PE-I2I

Caption Studio → **Image → Edit instruction** → upload one reference → ComfyUI → Automatic → **Qwen PE · Image Editing** → detected PE-I2I model. State the requested change and preservation instructions. The internal graph sends the image to `image_1`, and the PE node may return `ratio_follow` such as `<image1>`. Keep it as canvas metadata, not part of generated edit text.

## Quality and saved work

- A successful model run is not automatically a successful PE rewrite.
- With the optional enhanced bridge, `parse_ok=true` verifies the PE node's parser reported success, *not* that the image prompt is semantically flawless. Review fidelity manually.
- `parse_ok=false` or absent health metadata produces Needs Review, not Ready. Saved results require approval for review-required outputs.
- Names, category folders, prompt and caption Library history remain compatible. The saved record includes the PE parser/ratio metadata where available.
- The previous text-only bridge is supported for actual prompt text, but cannot certify PE parsing and therefore requires review.
- Automatic PE supports one final output; multiple prompt candidates are not silently merged. Alternative custom node packs need Advanced workflow registration or a future explicit adapter.

## Troubleshooting

- **No PE encoder models listed:** Check the actual `CLIPLoader.clip_name` catalog, PE checkpoint installation and ComfyUI search paths.
- **No route:** Check node names `QwenImage21_T2IPromptRewrite` / `QwenImage21_EditPromptRewrite`, `CLIPLoader`, `LoadImage` for edits, and the Neo text bridge. Not all third-party packs expose these classes.
- **Parser not verified:** Replace the single installed bridge directory with the updated bundled bridge and restart ComfyUI. Ensure the PE node advertises `positive_prompt`, `parse_ok` (BOOLEAN), and `wh_ratio` (STRING).
- **PE parser failed:** Inspect the text; possibly incomplete/invalid model JSON. Neo does not quietly accept it as Ready.
- **Output has unsupported candidates/types:** Select a supported single-result node mode or Advanced custom workflow.

## Verification limitations

Automated tests use a simulated local ComfyUI server and typed node-catalog fixtures. Real generation and GPU/VRAM behavior, including installed checkpoint weights and exact node revisions, must be tested on the user's Windows setup. No Neo Spaces, Neo Studio, or KoboldCPP data is changed.


## Qwen PE runtime guidance

If your rewrite node advertises a maximum output token input, Neo exposes it in the optional Runtime tuning section. Otherwise the node's own output-token default remains authoritative. Avoid reducing the cap drastically just to speed generation: an incomplete PE result may fail parsing and require review. There are no model-agnostic temperature/top_p sliders for Qwen PE.

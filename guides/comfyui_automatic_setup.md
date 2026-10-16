# Automatic ComfyUI model setup

Neo Prompt is a **prompt/caption/dataset application**, not a second Neo Spaces workflow builder. Neo Spaces independently owns arbitrary workflow-to-UI authoring. The apps neither call nor import one another, nor share data directories. They may each connect to the same external ComfyUI runtime.

## User steps

1. Start ComfyUI separately, with compatible LLM/VLM or Qwen Image 2.1 *prompt-enhancer* model files and custom nodes installed. Neo Prompt never installs/downloads models or nodes.
2. In **Connections**, save a local ComfyUI endpoint, e.g. `http://127.0.0.1:8188`. A successful Connection test proves reachability, **not** model readiness.
3. In Prompt Studio, Caption Studio or Batch, select the saved ComfyUI backend, leave **Automatic** selected, then click **Detect installed models**. Select a compatible model and, for vision, an advertised **mmproj projector**. **No workflow JSON is required for this route.**
4. Generate normally. Neo builds the small inference graph *in memory*, queues that graph in the selected ComfyUI instance, and reads text from its explicitly bound history output. Qwen PE-T2I and PE-I2I output text, not images.
5. To use unusual Comfy node packs or full custom workflows, choose **Advanced · Import my own workflow**. General workflow authoring belongs in Neo Spaces and requires no cross-app link.

## Supported automatic adapters (only when detected)

| Task | Required compatible Comfy nodes | Model choice |
| --- | --- | --- |
| Prompt Studio, text | `llama_cpp_model_loader` (or legacy `llama_cpp_loader`), `llama_cpp_instruct_adv`, Neo text-output bridge; `llama_cpp_parameters` optional | Any model advertised by loader's model selector; no GGUF hardcoding |
| Caption Studio and Batch, vision | Same recognized llama.cpp loader/instruct, `LoadImage`, vision input, mmproj + text-output bridge | User-chosen advertised model and projector |
| Caption Studio and Batch, Generic MTMD VLM | `NeoGenericMTMDModelLoader`, `NeoGenericMTMDInstruct`, `LoadImage` + text-output bridge | User-chosen model and projector from the live MTMD catalog |
| Prompt Studio, Qwen Image 2.1 PE-T2I | `CLIPLoader` with `qwen_image`, `QwenImage21_T2IPromptRewrite`, Neo text-output bridge | Discovered text encoder explicitly identified as Qwen Image 2.1 **PE T2I** |
| Caption Studio Image → Edit, Qwen Image 2.1 PE-I2I | `CLIPLoader`, `LoadImage`, `QwenImage21_EditPromptRewrite`, Neo text-output bridge | Discovered **PE I2I** edit encoder |

**Not every ComfyUI installation exposes these node classes.** Neo never claims to support all custom Comfy node packs or that detected nodes guarantee successful model loading. Qwen's prompt-enhancer models are distinct from image-generation checkpoints.

## Text-output bridge

ComfyUI normally may not expose internal STRING values in `/history/<prompt_id>`. If missing, copy the supplied folder `comfy_bridge/neo_prompt_text_bridge` into your ComfyUI `custom_nodes` directory, then restart ComfyUI. It defines `NeoPromptCaptionTextOutput` for ordinary text and `NeoPromptPEResultOutput` for Qwen PE metadata. **Do not install a second copy if this node is already installed by another Neo prompt/captioning pack**; duplicate Comfy class mappings could conflict. Custom node code executes inside ComfyUI, so install only reviewed local files.

## Safety / limits

- All Neo Prompt backend connections are loopback-only. No automatic ComfyUI model installation, arbitrary graph ingestion, global GPU/VRAM arbitration, or Neo Spaces integration.
- Each automatic inference explicitly validates advertised node classes/models/projector and a history-visible output. Missing nodes or ambiguous required inputs cause actionable errors, **not** silent model substitutions.
- Prompt Studio's numerical sampling controls apply to automatic **General LLM** only if the discovered `llama_cpp_parameters` node supports them. For Qwen/other routes and custom graphs they are disabled; Comfy owns those parameters.
- A ComfyUI request may still be running when Neo times out. Inspect ComfyUI's own queue before repeating it.
- Existing trusted JSON workflows continue to work under Advanced. Existing KoboldCPP profiles, Caption/Batch history, category Library, shutdown and retry rules are unaffected.
- No model/weight files are packaged or installed. Windows verification must use the user's actual model/node installation; mocked HTTP tests only validate routing/compilation.

## Troubleshooting actual ComfyUI /object_info

The app checks **four distinct conditions** instead of displaying a generic “unavailable” message:

1. **Loader class:** `llama_cpp_model_loader` or `llama_cpp_loader` must appear in the ComfyUI node catalog.
2. **Model choices:** the loader must advertise at least one GGUF model. A response with `"model": [[]]` means the loader is installed but currently exposes **zero models**. This is not fixed by changing the Neo Prompt backend profile; configure the relevant ComfyUI node-pack model folder and refresh/restart ComfyUI.
3. **Inference and output:** `llama_cpp_instruct_adv` must advertise `llama_model` and `custom_prompt`, and `NeoPromptCaptionTextOutput` must be installed for history-visible text. Install only a reviewed local copy of the included optional bridge, and restart ComfyUI.
4. **Vision (only):** `LoadImage`, a compatible image socket on the inference node, a real mmproj (not `None`), and a compatible advertised vision chat handler must be present. **Choose** the matching handler for the actual loaded model. The model family isn't guessed or hardcoded. For text-only tasks Neo uses the supported `None` handler when available.

Node names in other custom packs may differ; don't reinstall models based only on an “unavailable” badge. The **Advanced custom workflow** route remains separate and Neo Spaces owns arbitrary ComfyUI workflow authoring. Runtime discovery does not certify generation quality; real Windows inference must be checked.

## Uploaded images and `LoadImage` dropdowns

`LoadImage.image` advertises **image filenames already in the ComfyUI input directory**. A browser-uploaded caption image does not have a ComfyUI filename when Neo Prompt compiles its graph, so checking the temporary binding against the discovery-time dropdown incorrectly fails. Neo Prompt defers validating only that internal filename, uploads the image to ComfyUI, uses the response filename in the graph, then submits it. Other enumerated fields—model, mmproj, chat handler—remain strictly checked.

For a captioning test: use Caption Studio → select the ComfyUI profile → Automatic vision route → detected model, mmproj, and model-appropriate chat handler → upload an image → Generate caption. **Text prompt success does not certify VLM compatibility.** For a failure after upload, inspect the ComfyUI console and the node-specific `object_info`; it may be a separate model/handler/vision-node problem. Do not fix this error by moving models or downloading arbitrary workflow JSON.

Real ComfyUI execution on your GPU remains a required acceptance check; mocked upload responses only verify image binding order and routing.

## ComfyUI prompt fidelity and Qwen vision notes

- **Automatic General LLM/VLM:** When `llama_cpp_instruct_adv` (or `NeoGenericMTMDInstruct`) advertises `system_prompt`, Neo binds the compiled task/system contract there and binds the source/request to `custom_prompt`. Do not manually copy contracts into both fields. If a supported revision lacks a system input, Neo labels the combined task/user parts in `custom_prompt`. This changes only the **Automatic** inference graphs; imported Advanced JSON graphs remain unchanged.
- **Output style:** Some models still prefer keyword/tag lists or repeat phrases even with a natural-language task contract. Such text may receive **Needs Review** and should not be automatically reformatted into misleading prose. Try a different compatible instruction-tuned GGUF, adjust supported sampling controls, or test the same task in KoboldCPP; a valid Comfy graph does not certify prompt quality.
- **Qwen-VL image tokens:** When the user explicitly selects a `Qwen...` vision chat handler and the llama.cpp model loader advertises `image_min_tokens`, Neo requests a 1024-token grounding floor (if permitted by that node's range). This is **not** a general default for Gemma/Mistral/other model families or text-only models. Caption and Batch Automatic VLM use a larger 1024-token text-output allowance. Longer generations may use more time and memory.
- **Handler/model compatibility:** The list of advertised chat handlers is *not* proof that the selected GGUF understands every handler. Select one appropriate for the actual model architecture. In particular, don't automatically use `Qwen3-VL-Thinking` with a Qwen2-VL checkpoint. If ComfyUI reports `load_tensors`, `ffn up/down`, or other loader diagnostics, inspect all following lines and try to run that exact model/handler independently within ComfyUI before attributing failure to Neo Prompt.
- **Incomplete reasoning:** `<think>` without a matching close/final answer is **Invalid**, not a caption. Increase the supported output budget, use a non-thinking model or compatible handler, or inspect loader/template errors. Neo must not silently strip partial reasoning into a training caption.
- **Validation:** Tests use a simulated ComfyUI HTTP server; Windows GPU/model/node compatibility remains an acceptance task. KoboldCPP, Qwen prompt-enhancer, Library and Batch recovery semantics are preserved.

## Output-first ComfyUI General LLM prompting

For **Prompt Studio → ComfyUI → Automatic → General LLM**, generated results expose Enhance, Rewrite and Negative actions beneath the output. The original result is never overwritten. Neo submits the **selected saved result** to the **same verified model**, not the current draft or the currently selected UI model. Review-required results must be explicitly approved before refinement; generative Enhance/Rewrite outputs require review again. Negative results remain linked to the selected positive result. One-time reformatting is available for review-required General LLM results.

**Compatibility:** This works only with supported automatic General LLM llama.cpp nodes that return text through the history-visible output bridge. The ComfyUI catalog must continue to advertise the exact GGUF selected for the parent. No automatic model swap, custom JSON graph replay or Qwen-specific enhancement is implied. ComfyUI image captioning continues separately via VLM adapters.

**Quality:** Neo provides a concise final-output directive and flags strong repeated phrase loops for review. It does not modify the model's result or assert semantic accuracy. Try a better-suited model, lower temperature, or smaller max-output budget when repetitive tag prose appears. A 'Ready' status verifies detectable output-contract properties, not creative quality.

**Windows acceptance:** Generate a Text → Image result with the ComfyUI General LLM route; verify the system/user graph fields in ComfyUI; Enhance it, approve it, Rewrite it, and generate a Negative pair. Check parent/child links, Library pair saving, one-time Reformat, and that switching or unloading the model prevents an unverified refinement. Confirm Caption Studio and Batch are unchanged.


## Batch model reuse and recovery

For Batch, Neo precompiles one supported vision graph per job and reuses a bounded HTTP connection and node validation. The image file is uploaded and submitted for **each item**; this is not a single combined ComfyUI graph. Generic MTMD Batch sets supported `force_offload` to false to allow caching. ComfyUI owns its own node cache, model loads and VRAM behavior. There is no Neo control that guarantees memory residency or changes other ComfyUI queues. If history cannot be checked after submission, processing pauses as interrupted, power-off is disarmed, and the operator must check ComfyUI's queue/history before resuming.

## Qwen PE parsing and canvas guidance

The automatic PE routes are **not** image generators and are not a replacement for automatic General LLM prompting. They use supported ComfyUI `CLIPLoader` + `QwenImage21_T2IPromptRewrite` or `QwenImage21_EditPromptRewrite` nodes and advertise only checkpoints identified for their respective task. Detection checks the live ComfyUI `/object_info` catalog and reports absent nodes/PE checkpoint choices explicitly.

The updated, optional `NeoPromptPEResultOutput` bridge reads the PE **positive_prompt**, `parse_ok`, `wh_ratio`, and (for edit) `ratio_follow` outputs according to the installed node's named output sockets. The `positive_prompt` text is saved separately from the optional canvas fields. When `parse_ok` is `false`, or when a compatible older text-only bridge cannot verify it, the result is **Needs Review**; it is not assumed valid because ComfyUI ran successfully. Explicit review approval is required before saving. The canvas metadata follows the result into the Library. Neither model is asked to invent a negative prompt.

**Compatibility limitation:** Only recognized node classes/outputs are automatic. Alternate PE packs with different node names, input shapes, lists of multiple prompts, or nonstandard output types need independent adaptation or an Advanced custom workflow. Do not assume a detected PE checkpoint proves that all required nodes are installed or that model weights can fit in VRAM. No node weights are bundled.

**Acceptance:** First PE-T2I with a short Text → Image request; check enhanced positive text and `wh_ratio`. Second PE-I2I with a single reference and an edit request; verify image upload, preservation instruction and `ratio_follow`. Review both results visually. Retest one failed parser response and confirm Needs Review. No Windows machine/GPU or physical ComfyUI installation was controlled by automated tests.


## Optional runtime tuning

ComfyUI Automatic routes expose only the controls actually advertised by their selected nodes. Expand **Runtime tuning** after detecting the catalog. Unsupported PE sampling controls are deliberately hidden. Refer to `comfyui_route_tuning.md` for ranges, Batch persistence and slow-model behavior.

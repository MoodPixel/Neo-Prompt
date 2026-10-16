# Caption Studio — KoboldCPP Vision
Neo Prompt can send uploaded images to a local KoboldCPP **vision-capable** model using the OpenAI-compatible `/v1/chat/completions` request. The model must understand `image_url` content and have its matching MMProj/projector and vision handler loaded. An ordinary text-only model may answer a health check but fail this route; no capability certification is made merely from connection status.

## Workflow

Open **Connections**, save your KoboldCPP endpoint, then go to **Caption Studio**. Drop, paste, or browse for one source image. Static PNG, JPEG and WebP work. Images are checked with Pillow, limited to 10 MB and 20 megapixels, EXIF-oriented, resized **only by format normalization** (no intentional change in pixel dimensions), and stored with private UUID names under `neo_prompt_data/images/`. Metadata is stripped. Supported output uses JPEG for RGB and PNG for alpha images. This normalization can affect pixel compression/colors; the original raw upload is not separately retained by Neo Prompt.

Choose a task: **Describe image**, **Image → Recreation prompt**, **Image → Edit instruction**, **Image → Video prompt**, or **Dataset caption**. Describe visible evidence; never treat unsupported identity/backstory details as fact. The **Edit** task requires an explicit instruction. The task-specific compiler provides task-specific analysis scope, purpose, visual-treatment, grounding, preservation and motion/camera rules. The Caption Task alone chooses the output format. The UI does not show an Output Format dropdown.

Generate, inspect the result, then explicitly **Copy**, **Save to Library** or **Use in Prompt Studio**. Saved caption history and user-approved library entries are separate. Never rely on model-generated text without visually inspecting its fidelity.

## Compatibility and limits

- ComfyUI Automatic LLM/VLM and Qwen PE routes are also available when their required nodes, models and bridges are detected.
- Per-request vision timeout is 300 seconds. Timeout/disconnect does not prove a backend request was cancelled.
- The application has no automatic vision-ready detection for an arbitrary KoboldCPP model; the first image generation is the compatibility test.
- Qwen PE image edits require a compatible PE-I2I checkpoint and the supported reference-image input. Neo Studio V2 data is not automatically imported.
- This is a standalone Neo application; it never calls Neo Spaces or any Neo Studio API.

## profile verification

Purpose, Analysis Scope, Treatment, Grounding, and Output Format affect compiled caption instructions on compatible tasks. Edit Intent/Preservation apply to image-edit outputs, while Motion/Camera apply to image-to-video outputs. Custom-purpose and custom-treatment text inputs appear when selected. Custom crop is not supported because Neo Prompt does not provide a crop selection; choose another scope. The animated working state shows elapsed time, not fabricated backend progress. A model can ignore individual instructions even when they reach its API request.

## output review

Caption Edit/Video and ordinary image captions share the conservative reply-format normalizer. Review notes now display below a generated caption. A visually grounded caption still requires human inspection; model-returned JSON fields are not verified source evidence. See [Output quality](prompt_output_quality.md).

## output review

Results are labeled **Ready** or **Needs Review**. You must explicitly approve a Needs Review result before **Save to Library** becomes available. An invalid/truncated response is rejected as a failed generation rather than recorded as successful history. No automatic reformat is performed for vision captions.


### Model switching and model labels

Caption Studio uses the KoboldCPP profile selected **for Caption**, regardless of which model is currently loaded in that backend. If `/api/v1/model` reports a model when the request starts, its name is added to the caption result. If not, the label is unknown. An actual image request remains the only reliable compatibility check; the model label or loaded projector name alone is not a guarantee of usable vision output. Edit captions with explicit 'only change ... leave everything else unchanged' wording now receive a review alert if the model fails to mention preservation. The user remains responsible for visual accuracy.


## Task-owned formatting and source versus target style

Choose the **Caption Task**. It alone determines the response contract; there is no second Output Format control. **Describe Image** returns a grounded descriptive caption about the existing image medium. Older descriptive variants remain understood by the backend for compatibility, but the main Caption Studio interface no longer exposes them as a separate selector. **Recreate** writes an image-generation prompt; its treatment can request an anime or other output style. **Image → Edit** generates an instruction focused on the explicitly requested change and preserving unrelated image content, without imposing an unrelated treatment. **Image → Video** generates a time-based shot with motion, camera behavior and continuity; **Dataset** remains grounded and strict.

If your notes say *change only the hair to pink spiky hair*, choose **Image → Edit**, not Describe. If you choose Describe with a clear change instruction, the app asks you to select the edit task rather than silently ignore the edit. A response that only describes the current photograph under an edit or video task is marked **Needs Review**, not Ready. Similarly, a returned static caption lacking camera/motion language is flagged for review in Video mode. These checks are deliberately conservative and cannot prove pixel-level fidelity.

A result marked Ready means it passed format and mechanically recognizable constraints, **not** proof the model perceived the image accurately. Vision success is shown for the selected backend after an existing successful caption run, but changing the loaded model can invalidate earlier compatibility assumptions. Users must still test vision inference after a model switch.

Folder import is available in Batch & Dataset; per-file upload limits still apply.

## Task-first interface

The five Caption Studio tasks are: **Describe image → Descriptive Caption**, **Recreate → Image Generation Prompt**, **Edit → Image Edit Instruction**, **Image → Video → Video Generation Prompt**, and **Dataset caption → Training Caption**. The actual generation request contains the task-derived format, even if earlier browser settings retained an obsolete format selection. An intentionally conflicting externally supplied API format is still rejected rather than silently changing the task.

Only controls relevant to the chosen task appear. Selecting Edit/Video without the correct instruction/action will still generate review notes or an error if required information is missing. Automatic Ready status is a structural result check, not guaranteed pixel-level or artistic fidelity.

After upgrading, restart Neo Prompt and hard-refresh the browser with Ctrl+F5 if the old UI remains cached.

## Selectable description emphasis and explicit user context

**Caption Task** is the only output-type control. The other analysis controls were not meant to disappear. In Describe, **Visual writing emphasis** is now selectable: Neutral, Cinematic, Anime, or other supported treatments influence which visible visual details the model discusses and the vocabulary it uses. Describe still reports the actual source medium; select **Image → Recreation** if you want an anime-style *generation prompt* or other target transformation. Dataset remains locked to strict grounding by design.

**User instructions / important reference notes** can supply context such as `He is a young Korean man`, or task-specific changes in Edit/Video/Recreation. The model receives this as **user-supplied information**, not as a visually inferred fact. If an explicitly named demographic descriptor such as `Korean` is omitted, Neo marks the answer **Needs Review**; it will not insert invented wording into the output. This is a limited, conservative text check and does not guarantee that arbitrary requests/avoidances are obeyed. Inspect results visually.


## ComfyUI optional backend

ComfyUI supports detected Automatic caption routes without workflow JSON, or Advanced trusted API-format custom workflows with explicit text outputs. The Comfy graph owns its model and sampling; Neo does not auto-switch backends. See `guides/comfyui_llm_vlm_qwen.md`.

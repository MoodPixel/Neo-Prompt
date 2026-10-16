# Advanced custom ComfyUI workflows

For the default setup **no API-format workflow JSON is required**. See `comfyui_automatic_setup.md`. This guide below documents the preserved **Advanced custom workflow** option only.

## Custom ComfyUI text/vision and Qwen prompt workflows

**Scope:** standalone Neo Prompt. ComfyUI remains an independent user-installed model runtime, **not** Neo Spaces. No Neo Studio or Neo Spaces connection is installed or required. The workflow mapping is app-owned and does not claim to convert arbitrary graphs automatically.

## Prepare your ComfyUI graph

1. Start ComfyUI on a local loopback port (often `http://127.0.0.1:8188`). Load your **chosen** text/VLM/Qwen enhancer model and required custom nodes within ComfyUI. Neo never chooses/checks model weights for you.
2. Your graph must contain an **editable STRING input** for the source prompt, and for vision tasks a node with a STRING image-filename input (normally `LoadImage`), connected to the VLM or edit enhancer.
3. **Crucial:** The final desired text must appear in ComfyUI's `GET /history/<prompt_id>` output under an output node's `text`, `string` or `result` field (possibly nested in `ui`). Most internal STRING graph outputs aren't returned in history by default. Attach a suitable text-display/output bridge such as the one provided by your trusted node pack, and select the **bridge node ID** as Output node in Neo. If the node reports only an image file, Neo deliberately rejects it.
4. Export **ComfyUI → Save (API Format)**. A normal visual-editor workflow JSON containing `nodes`/`links` cannot be queued directly. Do not paste arbitrary untrusted graphs; installed custom nodes execute with your ComfyUI process privileges.

## Import and bind in Neo Prompt

1. **Connections:** save a **ComfyUI** profile with a loopback URL. Test Connection proves server reachability only.
2. Under **ComfyUI text & vision workflows**, choose your saved connection, friendly workflow name, exact target task, and mode (**Generic**, **Qwen PE-T2I**, or **Qwen PE-I2I**). Upload the API-format JSON file.
3. Inspect the node list and explicitly identify the **Text input node ID/field** (usually `prompt`), the **Image input node ID/field** for vision (usually `LoadImage.image`), and the **Text output bridge node ID/field** (often `ShowText.text`). The UI suggests some IDs but never assumes they are correct.
4. Confirm trust, save. **Import does not queue a job.** Re-import after changing the ComfyUI graph's connections or model selection. The local config is saved under `neo_prompt_data/comfy_workflows.json`.
5. In **Prompt Studio** select the saved ComfyUI connection and a **workflow for the currently selected Prompt task**. In **Caption Studio** or **Batch**, select a compatible workflow for that task. ComfyUI and KoboldCPP can be configured concurrently; Neo does not auto-switch or fall back between them.

### Qwen Image 2.1 PE task mapping

| Mode | Task | Graph requirements | Output |
|---|---|---|---|
| Qwen PE-T2I | **Prompt Studio → Text → Image** | user-selected PE-T2I weights, T2I prompt rewrite node, text prompt input, text bridge connected to `positive_prompt` | Enhanced **text-to-image prompt** only |
| Qwen PE-I2I | **Caption Studio → Image → Edit** | user-selected PE-I2I weights, edit prompt rewrite node, `LoadImage` wired to `image_1`, text bridge connected to `positive_prompt` | Enhanced image-edit **instruction** only |
| Generic ComfyUI LLM/VLM | Exact selected Prompt/Caption/Batch task | installed compatible LLM/VLM nodes, bound prompt/optional image, text bridge | Task-specific text; validity checked after generation |

The user selects/installs the model and node pack. ComfyUI community examples include `benjiyaya/ComfyUI-Qwen-Image-2.1-Prompt-Enhancer` and `mozophe/ComfyUI-Qwen-Image-2.1-PromptEnhancer-MTP`; **Neo does not require either specific repository**. Different community nodes use different input/output contracts—inspect your actual imported API graph. Those PE models are distinct from Qwen Image **image generation** checkpoints; using a prompt enhancer does not generate images or require Neo Spaces.

## Execution behavior and safety

- Each request first asks ComfyUI for node-class availability. If required classes are missing, the run is rejected before queueing. Queue via `POST /prompt`, wait for the specific prompt ID in `/history/{id}`, then extract text **only from the explicitly bound output node**. No global queue deletion, model changes or history purges occur.
- Uploaded references are copies placed in ComfyUI's input directory. Neo cannot promise automatic deletion of ComfyUI-owned input copies or any files created by the imported graph.
- The ComfyUI graph owns generation temperature, token limits, seed, checkpoint and other sampler fields. **Prompt Studio's KoboldCPP sampling fields are not applied to ComfyUI**, nor are their values represented as executed sampling parameters.
- Timeout can leave a ComfyUI job running. Inspect the ComfyUI queue **before** starting the same generation again. No automatic retry or fallback to KoboldCPP occurs.
- Needs Review outputs require explicit approval before saving; Invalid outputs are not saved. Caption and dataset results keep their separate review requirements. Advanced custom ComfyUI results do not receive the Automatic General LLM **Reformat Once / Enhance / Rewrite / Negative** actions. For custom workflows, explicitly use the text as a new source if you want another generation.
- ComfyUI's `/system_stats` only proves reachability. Model identity is not reliably discoverable from arbitrary Comfy graph execution. The saved record identifies **workflow name, workflow ID and prompt ID**, not a fabricated model label. A workflow check does not prove the selected model behaves correctly until real inference succeeds.
- All connections are loopback-only and CSRF-protected. No direct app-to-app integration. Imported graphs and uploaded image content stay on the user's machine unless a trusted graph itself uses external/network nodes.

## Windows acceptance checklist

1. Back up `neo_prompt_data` before upgrading and verify that your existing KoboldCPP profiles are still visible.
2. In ComfyUI create/import a small **text-only** LLM graph with a history-visible text node. Generate one Prompt Studio output. Verify only the bound STRING input changed and the output is readable/savable.
3. Try a Qwen PE-T2I graph (if you installed the model); verify the T2I prompt output is direct text, no image render was assumed, and ComfyUI sampling controls live in the graph.
4. Run a **vision graph** using Caption Studio with a chosen reference image. Confirm the image was uploaded and the caption/edit output depends on it.
5. Run three images in **Batch** with a Dataset-specific workflow. Pause/resume and export, then test one intentional per-image error and **Retry failed only**. Keep shutdown disabled until you separately test the cancellation window.
6. Disconnect ComfyUI and confirm Neo reports an actionable error instead of saving an invented result; retest KoboldCPP text/vision separately. Switch models by editing your ComfyUI graph, not by changing Neo's endpoint profile.
7. Verify generated text, linked reference images, saved categories, Library, and independent Neo Spaces startup all remain intact. Preserve a rollback backup of pre-upgrade user data.

**Not validated in container:** actual ComfyUI node packs, GGUF/PE checkpoint loading, user GPU/VRAM consumption, Windows browser acceptance and shutdown power-off. Automated tests simulate the ComfyUI REST API and text-output bridge without downloading model weights.


### compatibility

The automatic llama.cpp route recognizes `llama_cpp_model_loader` and the legacy `llama_cpp_loader`. The live `/object_info` schema supplies model/MMProj/handler choices and required defaults; Neo does not choose a hardcoded GGUF or handler. For VLM prompts, explicit chat-handler selection may be required. The UI now separates missing node, empty model catalog, missing projector and missing text-output bridge errors. A loader that advertises `model: [[]]` does **not** have a usable model choice, even though the node itself is installed. This is a capability check, not a claim of successful physical inference.

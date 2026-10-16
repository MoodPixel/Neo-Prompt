# ComfyUI Route Controls & Runtime Tuning

Neo Prompt is a standalone application. ComfyUI model files and node packs stay in your ComfyUI installation; Neo Spaces is **not required**. There is no new workflow editor.

## Where to find the controls

1. Open Prompt Studio, Caption Studio or Batch & Dataset.
2. Choose a ComfyUI backend → **Automatic** → a supported route and detected model.
3. Click **Detect installed models**. The optional **Runtime tuning** section appears when the selected ComfyUI node advertises compatible settings. Expand it and change only the values you intend to override.
4. Empty settings mean **use the existing ComfyUI node default**; **Use node defaults** clears all overrides for the selected workspace/route.
5. Neo saves these settings per workspace and ComfyUI profile. A saved Batch keeps its selected overrides across pause/resume and failed-only retry. The settings never change weights or the ComfyUI global configuration.

## Which controls actually work?

- **Automatic General LLM**: Prompt Studio already has Temperature, Top P, Top K, Maximum Tokens under Sampling. Those apply only when the installed `llama_cpp_parameters` node exposes them. The optional runtime panel includes only additional loader/execution controls (e.g., context length, VRAM limit, model offload), if advertised.
- **Automatic Vision LLM (llama.cpp)**: Image minimum/maximum tokens (when the loader supports them), context, VRAM and node-supported generation settings. A selected Qwen vision handler still requires a minimum of **1024 image tokens for grounding**; clear an unsupported override instead of guessing. Match the selected chat handler to the actual model architecture.
- **Generic MTMD VLM**: Its own loader/instruct sockets are discovered independently; node-specific max output, sampling and offload controls may be available.
- **Qwen Image 2.1 PE-T2I / PE-I2I**: **No universal temperature/top_p controls.** The PE checkpoints own their decoding. A maximum output token setting appears *only* if the installed PE rewrite node exposes a supported cap. The original PE default is kept if you leave it empty. Setting a small cap can cause incomplete or invalid output. `parse_ok`, `wh_ratio` and `ratio_follow` remain separate output metadata.
- **Advanced custom JSON workflow**: Runtime fields are not injected into arbitrary user-supplied graphs. Use ComfyUI / Neo Spaces to customize those workflows independently.
- **KoboldCPP**: Unchanged; continues using its own backend profile and compatible Prompt Studio sampling controls.

### Why a field may disappear

The available settings come from **live `/object_info` metadata**, not a hardcoded model-family list. If a field is missing, the selected node does not advertise a supported socket. Neo never submits an invented field. Installing/updating nodes may change the supported ranges; click Detect installed models again. Stale overrides are rejected at generation rather than silently ignored.

### Slow generation feedback

Neo shows elapsed time and an animated waiting indicator. Large Qwen PE model staging and generation can take minutes, especially when memory is tight. **There is no fabricated progress percentage or token counter.** Actual progress remains visible in the ComfyUI console. Neo does not assume a delayed response has failed. If Neo loses the response after ComfyUI accepts a prompt, check ComfyUI's queue/history before retrying; the ComfyUI Batch adapter Batch uncertain-execution safeguards still apply.

### Safety and limits

- Values are validated against the installed node's declared type and numeric min/max (and Neo's conservative safety bounds when the node omits them). Invalid and non-applicable values fail **before** ComfyUI graph submission.
- Persisted tuning is associated with an individual ComfyUI connection and workspace. Per-job Batch settings are retained through restart and reuse without silently changing models.
- All existing user data and profiles remain in `neo_prompt_data`. Back it up before applying the changed-files patch.
- **Windows acceptance:** Test one General LLM request; one VLM caption with a deliberately changed max-token setting; one Qwen PE request with and without a supported cap; and one paused/resumed two-image Batch. Confirm the ComfyUI console and saved settings before trusting long unattended runs. Do not enable automatic Windows shutdown for the first tuning test.

# Neo Prompt — Saved backend profiles
Use **Connections** to create named external inference connection profiles once. These profiles belong to Neo Prompt alone; nothing is imported from Neo Studio/Spaces or shared with other Neo apps.

1. Launch KoboldCPP or ComfyUI independently.
2. Under **Connections**, enter a meaningful profile name, choose **KoboldCPP** or **ComfyUI**, and supply a local address including its port (e.g. `http://127.0.0.1:5001` or `http://127.0.0.1:8188`). Save.
3. Click **Test connection**. It checks a read-only server endpoint; it does **not** validate loaded models' real inference or VLM capability.
4. For a KoboldCPP profile, click **Use for Prompt**, **Use for Caption**, or **Use for Batch**. The three choices can be different profiles. You can also select them in the studio dropdowns.
5. Restart Neo Prompt: saved profiles and explicit selections are restored. If you intentionally clear a selection or delete a profile, Neo will not guess another backend.

Both KoboldCPP and ComfyUI support executable routes. For ComfyUI, choose **Automatic → Detect installed models** to use a recognized node/model route without importing JSON; unusual graphs can be explicitly imported under **Advanced custom workflows**. The selected ComfyUI server must expose a matching node catalog, model, and history-visible output bridge. KoboldCPP still needs a compatible chat or vision model with MMProj where required. A `/system_stats` response verifies reachability only. See [Automatic ComfyUI setup](comfyui_automatic_setup.md) and [Advanced workflows](comfyui_llm_vlm_qwen.md).

Backend profile selection is distinct from **Prompt task profiles** (task-specific dimensions such as image/video/edit prompt formatting) and from reusable **Prompt presets** (sampling and task settings). Selecting a backend profile does not rewrite those creative settings.

Selections are saved in `neo_prompt_data/prompt_workspace.json` (Prompt) and `neo_prompt_data/profile_selections.json` (Caption/Batch), without changing Studio data. Keep this directory when upgrading. The application does not automatically download models/custom nodes, start remote services, or change server-selected model files.


## Current-model discovery
A named KoboldCPP profile is an **endpoint connection**, not a stored GGUF selection. You can load different compatible GGUF models in KoboldCPP without creating a new Neo profile. Click **Test connection** to request a live model label from KoboldCPP's read-only `/api/v1/model` endpoint. This is advisory identity information and does not load weights or perform inference.

- When KoboldCPP returns a valid label, Neo displays the model name, with any local filesystem prefix removed, and attaches the reported label to new Prompt, Caption and Batch results.
- When a model label is unavailable, the UI states **Model not reported**; no Qwen/ToriiGate/other model is inferred.
- A new Connect/Test refreshes model identity after a switch. Existing history keeps the label observed at generation time, if available. The model may change again after a check; only the backend executes the request.
- The OpenAI-compatible API uses KoboldCPP's `model: default` alias. This is not the name of a specific GGUF or a requirement to load one. Neo does not alter KoboldCPP chat-template, Jinja, context-size or MMProj settings.
- Connected does not equal Text Ready or Vision Ready. Execute the actual task to validate the selected model's capabilities. A model that supports text may not support image inputs.

There is no remote discovery, auto-download, automatic provider substitution or shared Neo runtime service. The backend URL remains loopback-only.

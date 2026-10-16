# Neo Prompt

**A local-first creative language studio for prompting, image understanding and caption datasets.** Write reusable image, edit and video prompts; analyze source images; organize results; and process caption datasets using your own local AI models.

Neo Prompt runs independently. You do **not** need Neo Studio, Neo Spaces, or another Neo app. It does **not** bundle AI models, a GPU backend or model downloads. You choose and run **KoboldCPP** and/or **ComfyUI** separately.

> **First public release — v1.0.0 (16 October 2026).** Neo Prompt is a standalone application, released publicly for the first time. It is not an upgrade to a previously public Neo Prompt version. Hardware and model compatibility depend on your selected external backend; see [Current limitations](#current-limitations).

## What you can do

| Workspace | Features |
| --- | --- |
| **Prompt Studio** | Text → Image, image-edit instructions from text, Text → Video; reusable profiles, sampling where supported, Generate, Enhance, Rewrite, Negative, review and Library saves |
| **Caption Studio** | Upload, drag or paste an image; describe, recreate, propose edits, write image-to-video prompts or training captions; task-specific guidance and result review |
| **Batch & Dataset** | Select images or a folder; sequential, resumable vision jobs; per-item status and retry; Library destination or image/`.txt` dataset ZIP with CSV manifest |
| **Library** | Browse, search, categorize, rename and reuse prompts, captions and presets |
| **Connections** | Configure named local KoboldCPP/ComfyUI backends, test reachability and inspect supported ComfyUI models/nodes |
| **Activity / Settings** | Inspect local activity, data location and guidance; understand backend readiness |

Automatic ComfyUI routes support recognized **General LLM**, **vision LLM**, **Generic MTMD VLM** and **Qwen Image 2.1 Prompt Enhancer** node configurations. Runtime tuning is offered only when the selected installed nodes advertise those settings. Advanced users may import trusted API-format ComfyUI workflows with explicit text/result bindings.

## Install on Windows

**Requirements:** Windows 10/11, Python **3.10+** available from `py` or `python`, internet access for the first Python dependency install, and a modern browser. ComfyUI and KoboldCPP are external optional runtimes, installed separately; a compatible local model is necessary to generate anything. GPU and system-memory requirements depend on your chosen models.

1. Download the **complete** Neo Prompt source archive (not an incremental changed-files patch) and extract it to a folder you choose, e.g. `C:\Apps\Neo_Prompt\`. Do not run the app from inside an unextracted ZIP.
2. Confirm `run_neo_prompt.bat`, `setup_neo_prompt_venv.bat`, `requirements.txt` and the `neo_prompt/` package are **together** in the same app folder.
3. Double-click **`setup_neo_prompt_venv.bat`**. It creates a local `.venv` and installs the application's Python dependencies. It does **not** install or download language/vision model weights.
4. Start your chosen backend separately (see below), then double-click **`run_neo_prompt.bat`**. Keep the console window open while working.
5. The launcher opens **http://127.0.0.1:7891** in your browser. You can open it manually if the browser does not appear.
6. Go to **Connections → Add a connection → Test**, then select your saved profile in Prompt Studio, Caption Studio or Batch & Dataset.

A successful **Test** confirms that the server responds. It does **not** certify that its loaded model supports text, vision, a compatible chat handler, the selected MMProj projector or a particular ComfyUI graph. Run a small real task to verify the model.

### Connect KoboldCPP

Start KoboldCPP with a compatible text model and its local HTTP API. Use its displayed local URL, commonly `http://127.0.0.1:5001`, when creating a **KoboldCPP** profile. Prompt Studio sends text through the supported chat-completions API. For Caption Studio and Batch, load an actual **vision-capable** model with its matching image/projector components. An ordinary text GGUF without vision support is insufficient. Use [KoboldCPP prompting](guides/prompt_studio_koboldcpp.md) and [Caption Studio](guides/caption_studio_vision.md) for first runs.

### Connect ComfyUI

Run your own ComfyUI server, normally at `http://127.0.0.1:8188`. Create a **ComfyUI** connection; under a workspace choose **Automatic → Detect installed models → route and model**. Vision tasks may also need a compatible projector and chat handler. **Neo Prompt does not configure your model folders or install custom nodes automatically.** Consult [Automatic ComfyUI setup](guides/comfyui_automatic_setup.md), [ComfyUI route tuning](guides/comfyui_route_tuning.md), and [Qwen PE validation](guides/qwen_pe_validation.md).

## ComfyUI nodes and model requirements

You only need the **rows relevant to the route you use**. These are ComfyUI **node class names**, which may be provided by optional external node packs; not all ComfyUI installs include them. Neo checks the selected server's live `/object_info` and rejects unsupported/missing node and model combinations rather than guessing.

| Feature | Node(s) / assets to check | Notes |
| --- | --- | --- |
| **General LLM via llama.cpp** | `llama_cpp_model_loader` (or `llama_cpp_loader`), `llama_cpp_instruct_adv`, **`NeoPromptCaptionTextOutput`** | A compatible GGUF must appear in the selected loader's model catalog. `llama_cpp_parameters` is optional for supported sampling controls. |
| **Vision LLM via llama.cpp** | Recognized llama.cpp loader/instruct above, `LoadImage`, suitable vision-image input, **MMProj** where required, text-output bridge | Pick the handler appropriate for the **actual model architecture**; having a list of handlers does not prove compatibility. |
| **Generic MTMD vision** | `NeoGenericMTMDModelLoader`, `NeoGenericMTMDInstruct`, `LoadImage`, **`NeoPromptCaptionTextOutput`** | Requires its own compatible loader/model/projector route when reported by ComfyUI. |
| **Qwen Image 2.1 PE Text → Image** | `CLIPLoader`, `QwenImage21_T2IPromptRewrite`, **`NeoPromptPEResultOutput`** preferred | Requires a suitable **PE-T2I** text-encoder checkpoint. Text-only bridge fallback is less informative and requires manual review. |
| **Qwen Image 2.1 PE image edit** | `CLIPLoader`, `LoadImage`, `QwenImage21_EditPromptRewrite`, **`NeoPromptPEResultOutput`** preferred | Requires a separate compatible **PE-I2I** checkpoint and a user reference image. It produces **prompt text**, not edited image pixels. |
| **Advanced custom workflow** | User-selected trusted ComfyUI API workflow + configured text/result bindings | Only use graphs and custom nodes you trust. Arbitrary graph auto-authoring is not supported in this app. |

**Bundled Neo text-output bridge:** Copy `comfy_bridge/neo_prompt_text_bridge/` into your ComfyUI `custom_nodes/` directory, restart ComfyUI and detect models again. It defines `NeoPromptCaptionTextOutput` and `NeoPromptPEResultOutput`. Do **not** install duplicate packages defining the same class names. For Qwen Image 2.1 PE rewrite nodes, use a reviewed compatible ComfyUI implementation (e.g. [ComfyUI-Qwen-Image-2.1-Prompt-Enhancer](https://github.com/benjiyaya/ComfyUI-Qwen-Image-2.1-Prompt-Enhancer)); obtain weights and follow their own model licensing/install instructions. Their separate PE-T2I and PE-I2I checkpoints belong in the ComfyUI model folder recognized by that node setup, not in Neo Prompt.

The bridge is shipped as source for transparency. Custom nodes execute **inside ComfyUI**, so inspect files before installation and never install untrusted third-party code or workflow archives.

## First workflow

1. **Prompt:** Select a working text profile → enter an idea → choose Text → Image, Edit or Video → Generate → review or save the result.
2. **Caption:** Select a vision profile → drag, browse or paste an image → choose Describe, Recreate, Edit, Image → Video or Dataset → Generate → check the reference against the output.
3. **Dataset:** Import images/folder → choose a destination and vision backend → start a small batch → review individual results → export a dataset ZIP or Library copies. **Power off PC when done** is optional and **off by default**; test the cancel behavior before unattended use.

Generated results use **Ready**, **Needs Review** or **Invalid** format checks. **Ready is not a guarantee of factual/visual accuracy.** Review questionable outputs, especially training captions and image-edit preservation instructions.

## Data, updating and privacy

Neo Prompt saves its own settings, records, images and Batch index in `neo_prompt_data/` beside the application. Keep this folder private and **never commit it**. In particular, the diagnostic `output_issues.json` may contain model output or user text.

For a **first install**, follow [Install on Windows](#install-on-windows); no previous Neo Prompt installation is required. For **future updates**, close the app, back up `neo_prompt_data/`, and replace application source files while preserving that folder and `.venv/`. Rerun setup if requirements change; refresh with **Ctrl+F5**. To roll back a future update, restore the matching application version **and** its pre-update data backup. **No automatic Neo Studio V2 data importer is included in v1.0.0**; Neo Prompt does not read another Neo app's storage.

The web server binds to **127.0.0.1 only**. Backend profiles accept loopback HTTP endpoints, not remote servers. Neo Prompt has no global cross-app GPU scheduler: if ComfyUI or KoboldCPP is busy, reduce concurrency or wait for backend completion before retrying. Lost ComfyUI responses can leave work running remotely—check the ComfyUI queue/history first.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `No module named neo_prompt` | Extract the **complete** archive; run the `.bat` beside the `neo_prompt/` directory; rerun setup. |
| Python or dependency error | Install Python 3.10+; rerun `setup_neo_prompt_venv.bat`; read errors in the console. |
| Blank/old page | Close old launchers; use Ctrl+F5; confirm the new app version in Settings. |
| Connection Test passes, generation fails | Test one compatible model in its backend first; confirm backend API, model, chat handler and vision projector. |
| ComfyUI node/model missing | Restart ComfyUI after installing reviewed nodes, verify the model folder and use **Detect installed models**. |
| Vision input unavailable | Ensure the model/projector are vision-capable, and use an accepted image (PNG/JPEG/WebP; max 10 MB and 20 MP). |
| Qwen PE slow or no output | Large PE checkpoints may need extended loading/VRAM; read the ComfyUI console; wait for actual completion and inspect parser health. |
| Batch interrupted after uncertain ComfyUI request | Inspect remote Queue/History **before** confirming Resume; do not trigger automatic Windows shutdown while status is uncertain. |
| Port `7891` in use | Close the existing Neo Prompt launcher or run `python -m neo_prompt.cli --port 7892` from the local venv. |

## Guides

- [First-release setup](guides/first_release_setup.md) · [Getting started](guides/getting_started.md) · [Backend profiles](guides/backend_profiles.md) · [Prompt Studio](guides/prompt_studio_koboldcpp.md)
- [Caption Studio](guides/caption_studio_vision.md) · [Batch & Dataset](guides/batch_dataset.md) · [Library browser](guides/library_browser.md)
- [Automatic ComfyUI setup](guides/comfyui_automatic_setup.md) · [Advanced ComfyUI workflows](guides/comfyui_llm_vlm_qwen.md) · [Runtime tuning](guides/comfyui_route_tuning.md) · [Qwen PE](guides/qwen_pe_validation.md)
- [Output review](guides/prompt_output_quality.md)

## Current limitations

- The owner has demonstrated the Neo Prompt browser UI running locally on Windows. This is **not** proof of a clean-machine install, live KoboldCPP/ComfyUI text and vision generation, specialist PE execution, GPU compatibility or optional Windows shutdown behavior; those paths need independent validation with your chosen models.
- No Neo Studio legacy-data import, multi-user/remote hosting, model downloads, automatic model/node installation, universal ComfyUI node-pack support, cross-app linking, or coordinated global GPU management.
- The screenshot gallery will be added after real application screenshots are approved; no placeholder images are presented as working product views.

**Branding:** Neo Prompt's bundled mark and wordmark live under `neo_prompt/ui/assets/`; the mark is also used as the browser tab icon. Other Neo apps are separate installations with a consistent design language, not shared dependencies.

## Open-source license

Neo Prompt v1.0.0 is released under the **GNU General Public License version 3 (GPL-3.0-only)**. See [LICENSE](LICENSE) for the complete terms. Portions adapted from Neo Studio V2 retain their GPLv3 licensing obligations; original contributors retain copyright in their contributions. Third-party software and downloaded models retain their own licenses. See [Third-party notices](THIRD_PARTY_NOTICES.md). For first-release highlights see [Changelog](CHANGELOG.md).

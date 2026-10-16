# Getting started with Neo Prompt

Neo Prompt is a standalone local browser app for text prompts, image understanding and caption datasets. It does not require Neo Studio or Neo Spaces, and it does not install model weights.

## Install and run

1. Install Python 3.10+ on Windows. Extract the complete app to a folder you choose (for example `C:\Apps\Neo_Prompt\`).
2. Confirm the root folder contains `setup_neo_prompt_venv.bat`, `run_neo_prompt.bat`, `requirements.txt` and `neo_prompt/`.
3. Double-click **setup_neo_prompt_venv.bat** to prepare `.venv`, then **run_neo_prompt.bat** to launch the local server.
4. Open **http://127.0.0.1:7891** if the browser does not open automatically. Keep the console window running.
5. Start KoboldCPP or ComfyUI **separately**; under **Connections**, add its `http://127.0.0.1:PORT` URL and click **Test**.

Use the exact local port shown by the backend. **Test** verifies server reachability only, not actual text/vision inference readiness.

## Choose a workspace

- **Prompt Studio** — Select a named backend profile, choose Text → Image, Edit or Video, enter the idea, Generate, and save or reuse the result. See [Prompt Studio](prompt_studio_koboldcpp.md).
- **Caption Studio** — Select a real vision-capable model, upload/paste an image, select the correct task and Generate. Results require visual review. See [Caption Studio](caption_studio_vision.md).
- **Batch & Dataset** — Import selected images or a folder, choose a destination, use a compatible vision backend and start a small batch. Saved jobs can be resumed/retried; see [Batch](batch_dataset.md).
- **Library** — Search saved prompts/captions/presets; organize categories and open records in their relevant workspace. See [Library](library_browser.md).

For ComfyUI, choose Automatic and use **Detect installed models**. That route checks compatible node/model catalogs and builds only supported inference graphs; it is not a general ComfyUI workflow editor. See [ComfyUI setup](comfyui_automatic_setup.md), [Runtime tuning](comfyui_route_tuning.md), [Qwen PE](qwen_pe_validation.md).

## Before longer sessions

Keep a private backup of `neo_prompt_data/` before updating. The app stores its records locally and never auto-imports Neo Studio V2 data. ComfyUI queues can continue remotely if a browser/backend response times out; confirm Queue/History before retrying. Optional Windows shutdown is off unless explicitly enabled for a batch. Real Windows/GPU compatibility remains to be validated for the first public version.

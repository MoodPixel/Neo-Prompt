# First public release — installation checklist

Neo Prompt **v1.0.0** is a new independent app. There is no earlier public Neo Prompt version to upgrade from, and Neo Studio V2 is not required.

1. Download and extract the **complete** Neo Prompt source archive (do not use a changed-files patch ZIP for a fresh install).
2. Install **Python 3.10+** and run `setup_neo_prompt_venv.bat` from the extracted app folder. This installs the Python environment only; it does not download model weights.
3. Run **KoboldCPP** or **ComfyUI** independently, with a model matching the task. For supported ComfyUI text and PE output routes, copy the included `comfy_bridge/neo_prompt_text_bridge/` folder to `ComfyUI/custom_nodes/` and restart ComfyUI.
**ComfyUI custom nodes:** Install [ComfyUI-llama-cpp_vlm](https://github.com/lihaoyun6/ComfyUI-llama-cpp_vlm) **for supported llama.cpp text/vision routes** or [ComfyUI-Qwen-Image-2.1-Prompt-Enhancer](https://github.com/benjiyaya/ComfyUI-Qwen-Image-2.1-Prompt-Enhancer) **for Qwen PE rewriting**. Use only the packages relevant to your workflow, plus Neo Prompt's bundled history-output bridge where required. Neither optional package is needed when using KoboldCPP alone. PE weights and GGUF/MMProj assets are downloaded separately according to their upstream instructions. Restart ComfyUI after installing reviewed nodes.

4. Start `run_neo_prompt.bat` and open `http://127.0.0.1:7891`. Confirm the page reads `v1.0.0` with no RC suffix.
5. Open **Connections**, add a local backend URL, select **Test**, choose it in Prompt Studio or Caption Studio and make one small generation request. A successful connection alone does not establish text/vision/model compatibility.
6. For vision, verify the backend's actual multimodal model, handler and projector. For PE, verify the distinct T2I or I2I text-encoder checkpoint and its corresponding rewrite nodes.
7. Review one result before trusting outputs or starting a large Batch. Optional PC shutdown is **off by default**; leave it off for first tests.

Local settings, uploaded images and generated records go into `neo_prompt_data/` alongside the app. Keep it private and back it up before any future version changes. Neo Prompt **does not** import or delete Neo Studio V2 data.

For the full requirements, node table and troubleshooting, return to the [README](../README.md). The code is [GPLv3-licensed](../LICENSE); downloaded backends and models retain their own licenses.

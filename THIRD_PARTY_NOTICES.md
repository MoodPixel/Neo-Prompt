# Third-party software and model licenses

Neo Prompt's application source and its bundled `comfy_bridge/neo_prompt_text_bridge/` package are distributed under the project [GPLv3 license](LICENSE). The app's dependencies, external inference engines, third-party ComfyUI nodes and model weights remain subject to **their own licenses**.

## Python dependencies

The first-run installer uses `pip` to install the packages named in [`requirements.txt`](requirements.txt) in a local virtual environment. These include FastAPI, Uvicorn, HTTPX, Pillow and Pydantic, as well as their transitive dependencies. **These packages are not copied into the Neo Prompt source repository**; consult each installed package's license and notices. The project's GPLv3 license does not replace the licenses of those packages.

## External local backends

**KoboldCPP and ComfyUI** are separate applications configured and installed by the user. Neo Prompt does not redistribute their code, installers, or model weights. Review their project licensing and installation instructions separately.

## ComfyUI custom nodes and model weights

The bundled **Neo Prompt Text Bridge** is Neo Prompt application code and supplies `NeoPromptCaptionTextOutput` and `NeoPromptPEResultOutput` to a separately installed ComfyUI. Other node classes named in the README may belong to ComfyUI itself or to independently installed community node packs. Neo Prompt does not include those third-party packs.

Optional **Qwen Image 2.1 Prompt Enhancer** nodes, PE-T2I/PE-I2I checkpoints, GGUF language/vision models, projectors (MMProj) and other assets are obtained by users from their respective providers. Their licenses, use restrictions, attribution requirements and any model-specific conditions are **not replaced by GPLv3**. Check the individual download's terms before use or redistribution. Model licensing may differ from the custom-node code licensing.

This notice describes distribution boundaries for the source repository, **not a guarantee** that an arbitrary third-party model or custom-node package is free for all uses. Report missing attributions or uncertain provenance before packaging additional third-party code/assets.

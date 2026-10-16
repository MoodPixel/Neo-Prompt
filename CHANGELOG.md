# Neo Prompt — Release history

## v1.0.0 — 16 October 2026

**First public release of Neo Prompt.** This is the first independently downloadable Neo Prompt application, not an upgrade from an earlier public release. Prompt and Captioning tools previously associated with Neo Studio V2 are now available in an independently run local workspace.

### Included

- **Prompt Studio:** image, edit-instruction and video-prompt authoring; generation, targeted refinement and reusable prompt profiles.
- **Caption Studio:** image upload, paste and vision-assisted descriptions, recreation/edit/video instructions and dataset captions.
- **Batch & Dataset:** persistent sequential image jobs, review, resume/retry and export.
- **Library:** locally saved prompts, captions, categories and reusable content.
- **Local Connections:** user-configured KoboldCPP and supported ComfyUI text/vision routes, with live capability checks.
- **ComfyUI workflows:** recognized automatic General LLM, vision/MTMD and Qwen Image 2.1 prompt-enhancement routes; adjustable controls when a connected backend advertises support.
- **Independent Neo branding:** sidebar wordmark and local browser icon; separate settings and local storage, without needing Neo Studio or Neo Spaces.
- **Open source:** GNU General Public License v3; external model weights and backend software are not bundled.

### Important limitations

- A connected backend still needs a separately installed compatible model, and supported ComfyUI routes may need additional nodes, the bundled output bridge and model assets.
- Backend compatibility, actual inference, GPU capacity and optional shutdown behavior depend on the user's machine and configuration. A live Windows browser launch has been demonstrated; a clean-machine installation and the complete real-model matrix are not yet independently validated.
- No automatic Neo Studio V2 data migration or cross-Neo-app integration. Existing Studio data is not modified.

See [README.md](README.md) for installation, dependencies, supported nodes and known limitations.

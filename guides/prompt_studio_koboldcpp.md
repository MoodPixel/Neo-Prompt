# Neo Prompt — Prompt Studio with KoboldCPP
## Workspaces and supported tasks

Prompt Studio is **text-first**. It does not analyze image pixels; image-aware tasks belong to Caption Studio. Text → Image produces a generation prompt; Image Edit Instruction produces an edit instruction based on the *text* you supply (it does not inspect image pixels); Text → Video produces time-based motion and camera directions. The main source editor offers **Generate**; **Enhance**, **Rewrite** and **Negative** are contextual actions on an already-generated result.

The source idea is authoritative. Advanced profile fields are drawn from the task-specific profile manifest formerly used by Neo Studio V2, now copied into Neo Prompt and owned by this app. The `output_format` of image-edit and video tasks is task-locked; ordinary image-generation tasks allow choosing supported output formats. Negative generation uses tighter generation settings and sanitizes repetitive, unsupported or positive-context-negating terms.

## Typical workflow

1. Run KoboldCPP separately and load a supported text model. Enable the OpenAI-compatible local HTTP endpoint (e.g. port `5001`).
2. Configure the server under Connections. A successful Test proves only that the model information endpoint responded.
3. Under Prompt Studio select the **KoboldCPP profile** explicitly.
4. Enter the **source idea**, optional **Additional instructions**, task and appropriate profile dimensions.
5. Optionally adjust temperature, Top P, Top K and max tokens. Choose **Save draft & settings** to persist both text and workspace configuration. A settings preset saves *controls only*, not your source text.
6. Choose **Generate prompt**. The interface waits while KoboldCPP works, then displays the result or actionable error. Only one prompt generation may be active per Neo Prompt server instance.
7. Use **Copy output**, **Save to Library** (name it), or **Use as source** (replaces your draft only on explicit action). For follow-on work select **Enhance / Rewrite / Negative** directly beneath the output. The selected result is the *sole creative input* for that refinement; it never silently uses the earlier draft. The old result stays in history; parent/child comparison and navigation are displayed below the new output. Negative results remain paired with their selected positive result for copy and Library saving. A Needs Review output must be approved before you can refine or save it. Previous runs remain available in Recent.

## Output storage

`neo_prompt_data/drafts/prompt.json` stores the source draft. `prompt_workspace.json` holds task/profile/settings. `prompt_runs.json` holds up to 100 completed generations with their source/profile/parameters. `saved_prompts.json` holds up to 250 explicitly saved Library items. `prompt_presets.json` holds up to 100 user-named settings presets. Connection profiles continue to use `profiles.json`. These files are independently owned by Neo Prompt and never mirror Studio data.

## Errors, latency and safety

- Profile missing: choose an existing **KoboldCPP** connection; the app never substitutes another connection.
- Incorrect endpoint or port: server unreachable or unsupported chat route. No generation result is saved on failure.
- Input validation: source must contain visible content; maximum source 20,000 characters; extra instruction 4,000; numeric generation settings are bounded.
- Request timeout: a synchronous (non-streaming) KoboldCPP chat call is allowed up to 240 seconds. **No pause/stop claims** or fabricated progress are shown. Browser exit is not a reliable model cancellation method.
- Response handling: bound to 2 MB and 32,000 characters; strips matched `<think>…</think>` and obvious response wrappers; incomplete reasoning or empty output fails without saved result.
- Negative guard: capped at 32 distinct terms with conservative positive-context protection. Treat negative output as model-generated draft and review it.
- Credentials, remote model installations, remote endpoints, third-party Neo apps and network/multi-user serving are not part of the app.

## Compatible backends and limitations

Prompt Studio supports KoboldCPP and recognized Automatic ComfyUI General LLM routes, with refinement supported where the route exposes the required text history/output. Caption Studio and Batch handle image vision separately; Qwen PE supports its own specialist text-rewrite routes. **Advanced custom ComfyUI workflows** and Qwen PE do not automatically inherit General LLM refinement actions. Legacy Neo Studio V2 data migration is not bundled in the first public version. Windows model/VRAM acceptance remains outstanding.

## profile verification

Primary Purpose now explicitly changes the request contract. Visual Treatment and Output Format change the requested output style/structure. Edit Intent and Preservation apply only to Image Edit tasks; Motion Profile and Camera Behavior apply only to Text → Video tasks. Their controls are hidden when not applicable. When Custom is selected, add a custom value. The generation animation displays real elapsed wall time, not token progress. Choosing a profile option alters the instruction sent to KoboldCPP but cannot guarantee that every model obeys it; compare real generations to evaluate model behavior.

## response quality

See [Reviewing prompt and caption results](prompt_output_quality.md). For Image Edit, JSON analysis with an identifiable final edit instruction is converted to that instruction alone. Ambiguous JSON is rejected, not saved. Video replies receive review notes if selected camera direction is missing or opposite. Structured Prompt remains structured by design.

## final result review

The output inspector displays **Ready / Needs Review**. If format validation rejects an output, you see an **Invalid** error instead of a saved success record. Needs Review prompts require explicit **Approve after review** before Library saving; optional **Reformat once** uses one more KoboldCPP request and creates a separate review-required result. No model can promise every requested scene or camera detail is preserved, so check source fidelity yourself.

## Output-first workflow and quality validation

- **Generate** creates a result from the editor. **Enhance** adds detail, **Rewrite** restructures/cleans language, and **Negative** creates negative terms from the **selected positive result**. Their actions are no longer in an Operation dropdown.
- Each refinement uses the saved original KoboldCPP profile and prompt/task settings; no silently substituted backend or current draft text. If the original profile was deleted, refinement is blocked with an explanation.
- A child has `parent_run_id`, `root_run_id` and `lineage_depth` in the app-owned history. Negative children also have `positive_run_id`. Up to twelve child-generation steps per chain are allowed; no automatic retry or rewrite of parents.
- Enhance/Rewrite always require comparison and review before saving or another refinement. Negative prompting keeps the positive-context guard and 32-term cap. Library saves of negative refinements retain the exact paired positive text as a separate field for copy/reuse.
- Output hygiene now flags detected leaked `<response>` tags, format instructions about the prompt, and several common meta-text patterns. Previously marked Ready results are re-evaluated for structural issues before being displayed/reused; only classification may change, not the saved text.
- **This is structural output validation, not a guarantee of creative fidelity**. Check the parent and child manually. Real GPU/model/Windows-browser confirmation remains necessary.


## Task-specific requests and Additional Instructions

Prompt Studio sends your source and **Additional Instructions** to the selected KoboldCPP endpoint as distinct parts of a compiled task request. It uses separate wording for Text → Image, Image Edit and Text → Video, rather than including examples mentioning unrelated media tasks. This also means a user's own mention of video inside the source is preserved, even for an image task; only compiler-originated contamination was removed.

**Additional Instructions are transmitted, but model obedience is not guaranteed.** Neo checks a few explicit high-confidence constraints (e.g. a requested color absent from the answer or a clearly stated 'everything else unchanged' edit requirement with no preservation language). Such cases become **Needs Review**, and must be approved before Library saving or refinement. These checks cannot prove character identity or every nuanced creative constraint.

**Output Format matters:** Natural Prompt, SD/SDXL Tags, Hybrid Prompt, Structured Prompt, and other legacy profile formats compile to different instructions where selected. Structured Prompt requests a valid JSON object and uses JSON validation. When Custom output is selected, the format text cannot be empty. Text-only edit and video tasks keep their task-locked output formats.

**Changing models:** backend profiles refer to an endpoint rather than one permanently installed model. Neo uses the currently loaded model and records the model name if KoboldCPP reports it. The backend still controls its own chat formatting and execution. When an Enhance/Rewrite/Negative action uses a different reported model than its parent, Neo adds a model-switch review warning. It does not silently assume the two models will produce equivalent results.


## Creative expansion with preserved explicit facts

Prompt Studio is intentionally creative: when a source says *casual clothing*, the model may add plausible outfit detail, lighting, textures and composition. Details the author explicitly named remain constraints: a requested **young Asian man**, emotion, precise wardrobe, location or camera move must not be silently dropped. Enhance adds useful detail to the **exact selected result**, while Rewrite clarifies it. Neither overwrites the source or parent.

The app now uses a conservative source-identity text check for certain explicitly supplied descriptors. Missing a named descriptor may mark the result Needs Review; this heuristic cannot establish meaning or visual identity. It is intentionally not a ban on imaginative details. Approve after inspecting the output, or retry.

## Automatic ComfyUI output-first compatibility
The same **Enhance / Rewrite / Negative** result controls now work with saved **Automatic ComfyUI General LLM** outputs. This is not a fallback: the exact parent backend/model is used after live revalidation. Review and approval, source fidelity warning, linked history and positive/negative pairing are shared with KoboldCPP. Custom Comfy workflows, specialized Qwen PE routes and VLM caption results are not treated as standard General LLM prompt refinements. See `comfyui_automatic_setup.md`.

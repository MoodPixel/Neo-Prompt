# Output contracts and review

Neo Prompt validates the **format of the returned model text**, not the factual fidelity of every character, scene, action or camera motion. Profile settings affect model instructions; no LLM can be guaranteed to obey them.

## Result states

- **Ready**: the final format passed deterministic checks; review content before public reuse anyway.
- **Needs Review**: the result is usable-looking but has a detected concern (meta commentary, missing/reversed camera movement, descriptiveness instead of a direct prompt, overlong negative list, etc.). Copy is permitted, but saving to Library or including a dataset export requires **Approve after review**.
- **Invalid**: mixed prose/JSON, ambiguous competing prompt, malformed required structure, no usable output, or token-limit finish. No successful generation/history or automatic Library entry is saved. An actionable error appears in the workspace.

Older saved history without a quality state stays readable and is **not** retroactively certified.

## Conservative cleanup

The app removes common response labels, quote wrappers and code fences, and extracts a task-specific final field from JSON only when unambiguous. It removes only explicitly recognized detached formatting afterwords. It does **not** combine analysis keys into a new prompt, generate new content, invent missing camera movement, or pick between two competing answers.

- Image generation: direct descriptive/generation language; commentary about the prompt is review-only.
- Image edit: final instruction should identify the intended change and preservation. Raw source images are not accessible from Prompt Studio text-only editing.
- Video: check source action/temporal continuity and camera profile manually. An absent or reversed requested pan is review-only, not automatically inserted.
- Negative: maximum 32 deduplicated accepted terms, unwanted positive-context echoes filtered. A token-limit finish is invalid; removing terms over cap requires review.
- Structured output: when explicitly selected, a nonempty valid JSON object/array is accepted, never forcibly flattened into prose.
- Vision caption/batch: visual accuracy is always a user review responsibility; review-required captions are withheld from automatic Library save/dataset export.

## Optional one-time reformat (Prompt Studio only)

A **Needs Review** Prompt result offers **Reformat once** on supported General LLM routes. Clicking it makes one additional explicit request to the saved matching backend/model. The original run stays unchanged, including on network failure; the attempt is consumed before sending the request. The new result is independently checked and always labeled **Needs Review** pending explicit user approval, because an LLM reformat can change meaning. This is not backend cancellation, background repair, or a guarantee of fidelity. Image caption/batch do not yet have a reformat action.

## Private diagnostics and privacy

The local `neo_prompt_data/output_issues.json` file can retain recent rejected/model-review excerpts, up to 16,000 characters per entry and 25 entries. It is **not** exposed by the ordinary public API or included in successful results, but it can contain sensitive user/model data. Treat backups and diagnostic sharing appropriately. It is an app-owned file independent of other Neo apps.

## Windows checks

Repeat the user-observed scenarios: image general, person identity, pose, expression, enhance, negative, video pan-left, and edit shirt-color. Compare the original source with final content. Then run a vision description, caption edit/video and two-image batches in both destinations. Test approved/unapproved export. Automated tests exercise modeled HTTP outputs; actual KoboldCPP model adherence remains user-machine validation.

## Output-first refinement and historical quality checks

Enhance/Rewrite/Negative actions use the currently selected **generated output**, not a source idea. No hidden model request or background repair is made. One explicit user click corresponds to one bounded KoboldCPP request. The parent text remains available, and the child is linked for comparison. Enhance/Rewrite require explicit fidelity review; Negative pairs with the chosen positive result and preserves the positive-context exclusion guard.

New structural heuristics also detect more of the actual Windows failure patterns (embedded `<response>` markup, commentary promising a final prompt, format instructions leaking into the answer). Older results are conservatively reclassified when listed or reused; their text remains unchanged. This does not certify factual accuracy or semantic equivalence. Needs Review/Invalid state prevents unapproved save/refinement and cannot be bypassed by a client-supplied source string or operation field.

## ComfyUI output fidelity

Automatic General LLM generation adds task-specific instructions for directly usable output while preserving existing task/profile compilation. A significant repeated 8–12-word phrase three or more times marks a result **Needs Review**; text is never silently rewritten or rejected solely because it is creatively expanded. Meta-instructions and incompatible output formats still go through the common output contract.

ComfyUI General LLM Enhance/Rewrite create review-required child outputs; Negative creates a positive-linked child using the existing sanitation and max-32-term guard. Reformat once makes one extra inference and always produces a review-required child. All actions use the selected saved parent and revalidate its reported model in ComfyUI. A requested refinement is an extra GPU job and may continue in ComfyUI after network timeout; inspect the queue before retrying.

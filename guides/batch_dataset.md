# Batch & Dataset — the ComfyUI Batch adapter
## Source import

In **Batch & Dataset → Reference images**, choose **Select images** or **Select folder** (Chrome/Edge folder picker includes subfolders). Import is sequential and progress displays the number scanned, duplicates and failures. Press **Stop after current file** to stop an ongoing import. No fixed total-image cap exists; only PNG, JPEG and WebP files within **10 MB and 20 megapixels per image** are accepted. Only user-selected files are read. Uploaded media is normalized, with EXIF removed, and stored locally in `neo_prompt_data/images`.

The **Skip byte-identical images already imported** checkbox is enabled by default. Uncheck it when repeated identical images should intentionally form distinct dataset items. A new selection is held in the browser until you create a job; if you close/reload during import, reselect the folder. Previously imported files remain local, so deduplication avoids unnecessary duplicate copies. Directory structure is recorded as metadata, not used as a server write path. When importing a folder, Batch suggests its top-level folder name as the **category**. Choose a saved category from the shared dropdown or click **+ New category**; all three workspaces see the same categories. Review or replace the suggested folder name before starting.

## Destinations and controls

1. **Prepare Dataset:** grounded training captions with optional trigger token, plus matching image and `.txt` files in a ZIP and CSV manifest with original relative paths.
2. **Save to Library:** produce reusable captions saved to Neo Prompt’s own Library with idempotent job/image IDs. The original images are retained. You can optionally export completed pairs. Each successful Library caption gets an organized image/text/metadata copy under `neo_prompt_data/caption_library/<safe-category>/`. The category defaults to the imported folder name (or **Batch Library** when none is available), and may be overridden on the job form. Existing Library records and jobs are not forcibly migrated.

Select a saved compatible KoboldCPP or ComfyUI vision profile, analysis purpose and scope; one batch inference runs at a time. Every image has its own status, model provenance (if reported), warnings, review state and attempts. **Ready** results can be saved/exported. **Needs Review** results require individual approval. Failed and incomplete results are not automatically included.

## Durable queue and recovery

- SQLite under `neo_prompt_data/batch_index.sqlite3` stores image indexes, new batch headers and per-image queue state. Legacy JSON image metadata is *copied*, not removed. Older `batches.json` remains readable and can be promoted when restarted.
- **Pause** is cooperative: the currently running backend request finishes before the queue pauses. **Resume** continues paused or restart-interrupted jobs. **Retry failed only** appears when a completed job has errors; it retries only failed images and never touches successful results. The older Retry incomplete action for intentionally cancelled jobs remains available.
- The browser displays only a bounded page of items at a time; use **View next items** to inspect large queues. Processing queries are indexed, not whole-JSON rewrites.
- ZIP export uses Zip64 and disk-backed CSV. Exports and media require sufficient **free disk space**; download speed/time still depend on size and browser support. The exporter excludes failures and unapproved results. ZIP exports are not reorganized by category, preserving training-tool compatibility. Filenames retain the familiar `image_0001.jpg` convention, growing beyond 4 digits as needed.
- Never delete SQLite files while the app runs. To roll back an upgrade, restore the matching **application and pre-upgrade data backup** together. Newer image metadata may not be visible to an older app version.

## Limits

There is **no fixed total-image-count limit**. There is still one in-flight vision request by default, a 10 MB/20 MP per-file safety cap, user-selected browser import only, limited GPU resources, finite disk space and a real requirement for a compatible vision model/projector. Pause cannot preempt an accepted backend request. Batch imports themselves are not server-side background folder scans, and closing the tab during import requires reselecting files; saved processing jobs do persist.

## Unattended Windows shutdown
- Optional checkbox under Batch → **4 · Unattended completion**. **OFF by default**; Windows only. Saving or selecting a batch without checking it never schedules a PC shutdown. At job submission Neo displays a second, explicit confirmation about powering off Windows and unsaved files in other programs. This permission applies to **one job**, not subsequent batches.
- The queue attempts every image. A failed image records its error and does not stop later items. After all items are either completed or failed, the job becomes `completed` or `completed_with_errors`. In both terminal cases, an opted-in job enters a **60-second countdown**. Use **Cancel PC shutdown** to prevent shutdown; the stored captions, status and errors remain intact.
- **Pause**, **Stop**, **interrupt/exit**, **app restart** or starting another job disarms the power action. The timer lives in Neo Prompt's running server process, not in the Windows Task Scheduler. If Neo Prompt closes during the countdown, no previously scheduled Windows shutdown remains. The app will not auto-resume or rearm a rebooted job.
- When you next open Neo Prompt, your completed captions remain stored; jobs with errors still list those errors. Click **Retry failed only** on `completed_with_errors`. Successful items and original Library saves are not regenerated or overwritten. Retrying starts with shutdown **off**, requiring a deliberate new opt-in for a future batch.
- The app uses `shutdown.exe /s /t 0` only after its own cancellable countdown; it **does not force-close apps** using `/f`. Windows can still close programs with unsaved work. Save all other work first and do not depend on Windows preventing data loss.
- The executable never runs on unsupported operating systems. No installed Windows batch shutdown has been physically executed in the automated tests; use a short, noncritical test batch and the cancellation button before trusting overnight runs.



## ComfyUI optional backend

ComfyUI supports detected Automatic VLM routes without workflow JSON, or Advanced trusted API-format custom workflows with explicit text outputs. The Comfy graph owns its model and sampling; Neo does not auto-switch backends. See `guides/comfyui_llm_vlm_qwen.md`.


## ComfyUI Automatic VLM Batch

Choose the saved ComfyUI backend under **Batch & Dataset**, select **Automatic VLM**, an advertised compatible GGUF, its projector and an appropriate chat handler; import a small folder and run **without auto-shutdown** first. Every image uploads separately, but the job reuses one ComfyUI HTTP session and task graph/preflight. Requests remain sequential by default. **Generic MTMD Batch requests no forced offload when the installed node supports it. ComfyUI controls actual model weights/VRAM residency**; Neo does not claim or force a permanent load. Review per-image elapsed seconds, model name and ComfyUI prompt ID where available. You may observe initial loading delays that disappear on subsequent images, but this is backend-dependent.

A definite image inference/validation failure records an error and does not stop the rest of the batch. On a **history/poll/transport uncertainty**, the job becomes interrupted, no further image is submitted, and Windows shutdown is disarmed. Inspect ComfyUI's own Queue/History before clicking **Resume** and confirming that no old job is still pending. Resume continues only queued items. When all remaining items finish, choose **Retry failed only** to run failures explicitly; successes stay untouched. Do not retry while a remote prompt is still running. Restart never re-arms shutdown.

If the configured ComfyUI connection URL changes or the original model disappears, resume/retry is refused without modifying completed items. Restore the intended server/model first. Preserved historical jobs remain readable. Disk-backed exports exclude failed and unapproved captions and retain one-to-one image/text pairing. Do not power down while remote ComfyUI work is uncertain.

# Browse saved work — Neo Prompt

Open **Library** to see three separate full-width views:

- **Image Captions** shows saved descriptions and other image-to-text results, including captions saved from Batch. Select an item for its full text and reference-image preview.
- **Prompts** shows saved prompts, including negative prompts and refinements. A paired negative prompt includes the linked positive text.
- **Presets** is an independent full-width view of reusable task, sampling and backend settings. Search, sort, inspect, apply or delete a preset without mixing it into saved prompts.

## Find, inspect and reuse

Use the **Search** field to search saved text, names where available, source ideas and task metadata. Collection chips narrow the list without moving files: **Batch saved / Single image / task type** for captions, and **Positive / Negative / Original / Refinements** for prompts. The counts reflect the current search. Choose **Newest**, **Oldest** or **Name / task** sorting. Each page displays up to 20 entries; use **Previous/Next** to browse more. Select a result to read the entire text, not a truncated list excerpt.

**Copy text** copies the selected caption or prompt. Saved negative pairs also offer **Copy positive + negative**. **Use in Prompt Studio** copies the selected prompt to the source editor; **Open in Caption Studio** opens the stored caption and its image reference. Replacing unsaved Prompt Studio source requires confirmation. Deleting an entry requires confirmation and does not delete generated-run history or the original image.

## Categories, names and organized local copies

You can save a Prompt Studio result or Caption Studio result with a **category** and an optional **custom name**. Choose an existing category from the shared dropdown or click **+ New category** to create one. Categories are common to Prompt Studio, Caption Studio and Batch & Dataset. They remain available after restarting the app, even when no saved entries currently belong to the category. Case-insensitive duplicates reuse the existing category. Blank names use the category label as the display name. Categories default to **General** for individual saves. Saved prompts include negative/positive pairing metadata when available.

The Library category dropdown filters saved entries in both result tabs. It includes registered categories that may still be empty. The automatic collection chips (Batch / Describe / Video or Positive / Negative / Original) continue to work separately. Select a saved entry and click **Rename / move** to change its name or category without regenerating. Search matches user-defined names and category labels.

Organized files are **managed convenience copies** under Neo Prompt's own data directory (not Studio or Spaces):

```text
neo_prompt_data/
  caption_library/<safe-category>/<safe-name>__<id>.jpg
  caption_library/<safe-category>/<safe-name>__<id>.txt
  caption_library/<safe-category>/<safe-name>__<id>.json
  prompt_library/<safe-category>/<safe-name>__<id>.txt
  prompt_library/<safe-category>/<safe-name>__<id>.json
```

Real filenames use the original image's normalized extension and a stable internal ID to avoid collisions. Space/punctuation in category and name labels is normalized for Windows-safe folder names (for example `Fantasy Creatures` becomes `Fantasy_Creatures`); the readable label is retained in the Library. Entries in historical JSON-only storage stay readable **without a bulk migration**. Organizing an old entry creates its category copies on demand. Original uploads in `images/`, earlier generated-run history, and legacy saved records are never silently moved. Deleting an organized saved entry removes only its managed category copies, not its source image.

### Batch category inheritance

When you select a folder, Batch suggests the chosen folder's name as the category. You can select a category or create one with **+ New category** before starting. If no folder category is available, the default is **Batch Library**. New Library-mode captions are saved in that category, with the source filename included in their display names to distinguish items; retries remain idempotent. Dataset mode records category in the job metadata but keeps the widely compatible flat image/`.txt` ZIP pairing and CSV export format.

## Tips and limits

If new Batch captions were just saved while Library is open, navigate away and back to refresh the browser. The browser API returns one 20-item page rather than all captions at once. Existing history and source media remain untouched; older prompt saves retain their established 250-entry retention policy. Back up `neo_prompt_data` before any upgrade and keep the app closed while copying that folder. Neo Prompt has no runtime dependency on Neo Spaces or Neo Studio.

### Storage of shared category names

Neo Prompt records explicitly created categories in `neo_prompt_data/library_categories.json` and also discovers category names in existing saved prompts, captions and recorded Batch jobs. Creating a category does **not** move old files or create empty media folders. The actual category folder is created only when an entry is saved. The registry is owned by Neo Prompt alone; Neo Spaces and Neo Studio are not consulted.

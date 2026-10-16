"""one task authority for caption, recreation, edit, video and dataset.

Only source description can optionally produce multiple *descriptive* representations.
Creation and transformation tasks own their output contract. No silent coercion.
"""
from __future__ import annotations

TASK_FORMATS = {
    "describe": ("descriptive_caption", "alt_text", "tags_keywords", "attribute_list"),
    "recreate": ("image_generation_prompt",),
    "edit": ("edit_instruction",),
    "video": ("video_generation_prompt",),
    "dataset": ("dataset_caption",),
    "library": ("descriptive_caption", "tags_keywords", "alt_text", "attribute_list"),
}

TASK_DEFAULTS = {key: choices[0] for key, choices in TASK_FORMATS.items()}


def effective_vision_options(task: str, options: dict | None) -> dict:
    if task not in TASK_FORMATS:
        raise ValueError("Unsupported caption task")
    opts = dict(options or {})
    requested = opts.get("output_format")
    if requested and requested not in TASK_FORMATS[task]:
        raise ValueError(f"{task.title()} cannot use output format {requested}. Choose a compatible format for the selected task.")
    opts["output_format"] = requested or TASK_DEFAULTS[task]
    # Source description preserves visible facts and the source medium, but
    # the selected visual treatment may guide caption vocabulary/emphasis.
    # It must never silently become a request to restyle an existing image.
    # Only strict dataset preparation locks style and grounding.
    if task == "dataset":
        opts["visual_treatment"] = "source_accurate"
        opts.pop("custom_visual_treatment", None)
        opts["grounding"] = "strict"
    return opts

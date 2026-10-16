"""Conservative, model-neutral postgeneration instruction checks.

These are *signals*, not semantic proof. Only high-confidence requirements are
flagged; false positives are possible and the user reviews the output.
"""
from __future__ import annotations
import re

_COLOR_WORDS = ('red', 'blue', 'green', 'yellow', 'black', 'white', 'pink', 'orange', 'purple', 'brown', 'grey', 'gray', 'gold', 'silver')
_PRESERVE = re.compile(r'\b(?:preserv(?:e|ing)|keep|maintain|retain|unchanged|unmodified|do\s+not\s+alter|only\s+(?:change|modify)|nothing\s+else|everything\s+else)\b', re.I)
_PRESERVATION_INTENT = re.compile(r'\b(?:everything\s+else|nothing\s+else|all\s+other\s+(?:elements|details)|rest\s+unchanged|keep\s+(?:everything|the\s+rest)|only\s+(?:change|edit|modify))\b', re.I)
_EDIT_VERB = re.compile(r'\b(?:change|replace|modify|edit|recolor|turn|make|remove|add|keep)\b', re.I)


def check_fidelity(text: str, *, task: str, instruction: str, source: str = '', preservation_policy: str = '') -> list[str]:
    """Review-only alerts for explicit, mechanically identifiable constraints."""
    output = text.casefold()
    directive = (instruction or '').strip().casefold()
    issues: list[str] = []
    # The user explicitly names a target color. Prefer review to inserting text.
    expected_colors = [word for word in _COLOR_WORDS if re.search(r'\b'+word+r'\b', directive)]
    missing = [word for word in expected_colors if not re.search(r'\b'+word+r'\b',output)]
    if missing:
        issues.append('Additional Instructions mention color '+', '.join(missing)+'; that color is not present in the result. Verify the requested change.')
    if _PRESERVATION_INTENT.search(directive) and not _PRESERVE.search(text):
        issues.append('Additional Instructions require preserving other elements; the result does not state a clear preservation constraint.')
    if task == 'text_image_edit' and preservation_policy in ('identity_priority', 'composition_priority', 'preserve_unrequested') and not _PRESERVE.search(text):
        issues.append('The selected preservation policy is not explicit in the edit instruction. Review unchanged subject/scene details.')
    if task == 'text_image_edit' and not _EDIT_VERB.search(text):
        issues.append('The edit result may not directly instruct a change.')
    # Only check an explicitly specified identity word in the supplied text;
    # this is NOT visual identity inference. Do not forbid creative details.
    # The list is intentionally narrow to avoid misclassifying broad scene words.
    for descriptor in ("asian", "african", "european", "latino", "hispanic", "indian", "korean", "japanese", "chinese"):
        if (source and re.search(r"\b" + descriptor + r"\b", source, re.I)
                and not re.search(r"\b" + descriptor + r"\b", text, re.I)):
            issues.append("The source explicitly specifies '" + descriptor + "' but the generated result omits it. Review subject fidelity.")
    # These checks cannot certify identity, geography, or nuanced semantics.
    return issues

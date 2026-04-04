"""Persona definitions for the user emulation agent.

Each Persona describes a simulated user type. The description field is
injected verbatim into the LLM prompt.

To add a new persona: add an entry to PERSONAS. No other code changes needed.
"""

from dataclasses import dataclass


@dataclass
class Persona:
    name: str
    description: str
    technical_level: str  # "non-technical" | "moderate" | "technical"
    engagement_style: str  # "curious" | "critical" | "confused" | "enthusiastic"


DEFAULT_PERSONA = Persona(
    name="curious_explorer",
    description=(
        "A non-technical user who finds the ecosystem visually interesting "
        "and wants to watch it grow and change in surprising ways. Tends to "
        "notice when something looks odd or static, and imagines what might "
        "make the world feel more alive. Asks questions like 'what if?' rather "
        "than specifying implementations."
    ),
    technical_level="non-technical",
    engagement_style="curious",
)

PERSONAS: dict[str, Persona] = {
    "curious_explorer": DEFAULT_PERSONA,
}

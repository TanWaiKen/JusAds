"""
jusads_generation.agents
────────────────────────
The four independent Media Agents (Text Caption, Image, Audio, Video) and their
shared contract. Each agent lives in its own module and never imports another
agent (Req 5.1, 5.2).
"""

from jusads_generation.agents.base import (
    NODE_COORDS,
    AgentResult,
    load_guide,
    load_multimodal_reference,
)

__all__ = [
    "AgentResult",
    "NODE_COORDS",
    "load_guide",
    "load_multimodal_reference",
]

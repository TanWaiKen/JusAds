"""
data_model.py
─────────────
State models for the compliance pipeline.
"""

from dataclasses import dataclass, field


@dataclass
class ComplianceState:
    """State for the compliance checking pipeline."""
    session_id: str
    media_type: str  # "text" | "image" | "audio" | "video"
    input_path: str  # file path for media files
    text_input: str  # text content (for text media type)
    market: str  # "malaysia" | "singapore"
    platform: str  # "tiktok" | "meta"
    ethnicity: str  # "malay" | "chinese" | "indian" | "all"
    age_group: str  # "gen_z" | "millennial" | "gen_x" | "all_ages"
    iteration: int = 0
    result: dict = field(default_factory=dict)
    status: str = "pending"  # "pending" | "checked" | "verified" | "edit_pending" | "remediated" | "remix_failed"
    # --- Remix remediation fields ---
    remediated_path: str = ""   # path to remediated output file
    remix_iteration: int = 0    # count of remediation attempts

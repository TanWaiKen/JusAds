"""Pydantic models for cultural guideline entries.

Defines enums and validation models for ethnic-specific cultural advertising
guidelines covering Malay, Chinese, and Indian audiences in Malaysia and
Singapore markets.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


# --- Cultural Guideline Enums ---


class Ethnicity(str, Enum):
    """Target ethnic audience for cultural guidelines."""

    MALAY = "malay"
    CHINESE = "chinese"
    INDIAN = "indian"
    ALL = "all"


class AgeGroup(str, Enum):
    """Age group applicability for cultural guidelines."""

    ALL_AGES = "all_ages"
    ADULTS_ONLY = "adults_only"
    CHILDREN = "children"


class CulturalCategory(str, Enum):
    """Classification categories for cultural guidelines."""

    BODY_EXPOSURE = "body_exposure"
    SUGGESTIVE_CONTENT = "suggestive_content"
    RELIGIOUS_SENSITIVITY = "religious_sensitivity"
    FOOD_TABOOS = "food_taboos"
    SUPERSTITIONS = "superstitions"
    COLOR_SYMBOLISM = "color_symbolism"
    NUMBER_SYMBOLISM = "number_symbolism"
    GENDER_NORMS = "gender_norms"
    ANCESTRAL_RESPECT = "ancestral_respect"
    CASTE_SENSITIVITY = "caste_sensitivity"
    MODESTY = "modesty"
    HALAL_COMPLIANCE = "halal_compliance"


class Severity(str, Enum):
    """Severity level for cultural guideline violations."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Cultural Guideline Entry Model ---


class GuidelineEntry(BaseModel):
    """A single cultural guideline record with structured metadata.

    Represents one cultural advertising rule with market, ethnicity,
    age group, category, severity, and descriptive text. Used for
    ingestion validation and Qdrant payload structuring.
    """

    market: str = Field(..., pattern="^(malaysia|singapore)$")
    ethnicity: str = Field(..., pattern="^(malay|chinese|indian|all)$")
    age_group: str = Field(..., pattern="^(all_ages|adults_only|children)$")
    category: str
    severity: str = Field(..., pattern="^(high|medium|low)$")
    guideline_text: str = Field(..., max_length=1000)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate category against the defined CulturalCategory enum values."""
        valid = {e.value for e in CulturalCategory}
        if v not in valid:
            raise ValueError(
                f"Invalid category '{v}'. Must be one of: {sorted(valid)}"
            )
        return v


# --- Persona Narrative Entry Model ---


class PersonaEntry(BaseModel):
    """A cultural persona narrative for a specific market+ethnicity combination.

    Represents a rich, descriptive narrative of the target viewer's cultural
    sensitivities and expectations. Used by the single-model video compliance
    pipeline where the persona is injected directly into the video model prompt.
    """

    market: str = Field(..., pattern="^(malaysia|singapore)$")
    ethnicity: str = Field(..., pattern="^(malay|chinese|indian|all)$")
    age_group: str = Field(..., pattern="^(all_ages|adults_only|children)$")
    persona_text: str = Field(..., max_length=3000)

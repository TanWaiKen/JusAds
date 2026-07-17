"""
templates/registry.py
─────────────────────
Module-level singleton registry for prompt templates.

Loads all template definitions from the templates subpackage at import time,
indexes by template_id, and groups by ad_type for efficient retrieval.

Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4
"""

import copy
import logging
from typing import Optional

from . import AdType, PromptTemplate
from . import poster_templates, carousel_templates, video_templates

logger = logging.getLogger(__name__)

# --- Module-level Registry State ----------------------------------------------

_REGISTRY: dict[str, PromptTemplate] = {}
_BY_TYPE: dict[AdType, list[str]] = {}


def _init_registry() -> None:
    """Load all template definitions from the templates subpackage.

    Scans poster_templates, carousel_templates, and video_templates for their
    TEMPLATES lists, indexes each by template_id, and groups by ad_type.
    """
    all_templates: list[PromptTemplate] = [
        *poster_templates.TEMPLATES,
        *carousel_templates.TEMPLATES,
        *video_templates.TEMPLATES,
    ]

    for tpl in all_templates:
        tid = tpl["template_id"]
        _REGISTRY[tid] = tpl
        ad_type = tpl["ad_type"]
        if ad_type not in _BY_TYPE:
            _BY_TYPE[ad_type] = []
        _BY_TYPE[ad_type].append(tid)

    logger.info(
        "[TemplateRegistry] Loaded %d templates across %d ad types",
        len(_REGISTRY),
        len(_BY_TYPE),
    )


def get_templates_for_type(ad_type: AdType) -> list[PromptTemplate]:
    """Return all registered templates for the given ad type.

    Templates are ordered by insertion order (most-used first as future
    usage data becomes available). Returns deep copies to prevent mutation.
    """
    template_ids = _BY_TYPE.get(ad_type, [])
    return [copy.deepcopy(_REGISTRY[tid]) for tid in template_ids]


def get_all_templates() -> list[PromptTemplate]:
    """Return all registered templates across all ad types.

    Returns deep copies to prevent mutation of internal registry state.
    """
    return [copy.deepcopy(tpl) for tpl in _REGISTRY.values()]


def get_template_by_id(template_id: str) -> Optional[PromptTemplate]:
    """Return a single template by its ID, or None if not found.

    Returns a deep copy to prevent mutation of internal registry state.
    """
    tpl = _REGISTRY.get(template_id)
    if tpl is None:
        return None
    return copy.deepcopy(tpl)


# --- Initialize on import -----------------------------------------------------

_init_registry()

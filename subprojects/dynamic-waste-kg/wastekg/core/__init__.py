"""初始化当前 Python 包。"""

from .knowledge_base import DEFAULT_CATEGORY_SPECS, seed_default_categories
from .models import (
    CategorySpec,
    DetectedObject,
    DetectedRelation,
    GraphEvent,
    ObjectInstance,
    Observation,
    RelationEdge,
)
from .taxonomy import (
    CANONICAL_CATEGORY_ALIASES,
    KNOWN_VISUAL_CLASSES,
    PAPER_VISUAL_CLASSES,
    UNKNOWN_CATEGORY,
    WASTE12_CLASSES,
    canonicalize_category_name,
)

__all__ = [
    "CANONICAL_CATEGORY_ALIASES",
    "CategorySpec",
    "DEFAULT_CATEGORY_SPECS",
    "DetectedObject",
    "DetectedRelation",
    "GraphEvent",
    "KNOWN_VISUAL_CLASSES",
    "ObjectInstance",
    "Observation",
    "PAPER_VISUAL_CLASSES",
    "RelationEdge",
    "UNKNOWN_CATEGORY",
    "WASTE12_CLASSES",
    "canonicalize_category_name",
    "seed_default_categories",
]

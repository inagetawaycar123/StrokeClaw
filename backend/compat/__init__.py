"""Compatibility adapters for the optimized StrokeClaw field model.

This package is intentionally add-only. It mirrors legacy runtime/database
payloads into stable view objects without taking over the existing write path.
"""

from .adapters import (
    build_clinical_decision_bundle,
    build_cockpit_view_model,
    build_confidence_summary,
    build_skill_invocations,
)
from .skill_registry import get_skill_registry

__all__ = [
    "build_clinical_decision_bundle",
    "build_cockpit_view_model",
    "build_confidence_summary",
    "build_skill_invocations",
    "get_skill_registry",
]

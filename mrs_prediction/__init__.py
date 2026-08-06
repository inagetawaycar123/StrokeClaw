"""Patient-level 90-day mRS research training and standalone MVP inference.

The package remains independent from the StrokeClaw production DAG. Only a
validated ``MVP_RESEARCH`` bundle with ``online_loading_permitted=true`` may be
used by the standalone inference entry; CV and smoke-test artifacts stay
evaluation-only.
"""

from .schema import FEATURE_SCHEMA_VERSION, MODEL_MODES

__all__ = ["FEATURE_SCHEMA_VERSION", "MODEL_MODES"]

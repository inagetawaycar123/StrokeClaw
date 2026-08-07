"""Fixed V0 feature schema for patient-level mRS baselines."""

from __future__ import annotations

from typing import Final


FEATURE_SCHEMA_VERSION: Final[str] = "mrs-v0.2"
MODEL_MODES: Final[tuple[str, str]] = ("baseline", "update_24h")

BASELINE_FEATURES: Final[tuple[str, ...]] = (
    "sex",
    "age",
    "onset_to_ct_time",
    "baseline_nihss",
)

UPDATE_24H_FEATURES: Final[tuple[str, ...]] = BASELINE_FEATURES + (
    "nihss_24h",
    "nihss_change_24h",
)

RAW_COLUMN_BY_FEATURE: Final[dict[str, str | None]] = {
    "sex": "Gender",
    "age": "Age",
    "onset_to_ct_time": "Onset to CT time",
    "baseline_nihss": "NIHSS Baseline",
    "nihss_24h": "NIHSS 24 HOURS",
    "nihss_change_24h": None,
    # Reserved for a later schema revision. It is deliberately disabled in V0.
    "ctp_core_volume": None,
}

V0_SCHEMA: Final[dict[str, object]] = {
    "feature_schema_version": FEATURE_SCHEMA_VERSION,
    "label": {
        "source_column": "90 Day MRS",
        "binary_mapping": {"0": "mRS 0-2", "1": "mRS 3-6"},
        "positive_class": 1,
    },
    "modes": {
        "baseline": {
            "features": list(BASELINE_FEATURES),
            "prediction_time": "initial_CT",
        },
        "update_24h": {
            "features": list(UPDATE_24H_FEATURES),
            "prediction_time": "24_hours",
            "approved_post_baseline_feature": "NIHSS 24 HOURS",
        },
    },
    "raw_columns": RAW_COLUMN_BY_FEATURE,
    "derived_features": {
        "nihss_change_24h": "NIHSS 24 HOURS - NIHSS Baseline",
        "onset_to_ct_hours": (
            "((Time of Initial CT_Osirix - Time of Symptom onset) modulo 1 day) * 24"
        ),
    },
    "reserved_features": {
        "ctp_core_volume": {
            "enabled": False,
            "reason": (
                "threshold definition, sentinel value 99, and deployment source "
                "alignment are unresolved"
            ),
        }
    },
    "image": {
        "stored_array_layout": "HWC",
        "stored_shape": [256, 256, 4],
        "internal_channel_mapping": {
            "0": "NCCT",
            "1": "arterial_mCTA",
            "2": "venous_mCTA",
            "3": "delayed_mCTA",
        },
        "v0_model_channel_indices": [0],
        "v0_model_tensor_layout": "NCHW",
    },
    "time_assumptions": {
        "onset_to_ct_unit": "hours",
        "maximum_supported_interval": "less_than_24_hours",
        "raw_source_preserved": True,
    },
}


def feature_names_for_mode(model_mode: str) -> tuple[str, ...]:
    """Return the ordered feature list for a supported prediction time."""

    if model_mode == "baseline":
        return BASELINE_FEATURES
    if model_mode == "update_24h":
        return UPDATE_24H_FEATURES
    raise ValueError(f"Unsupported model_mode={model_mode!r}; expected {MODEL_MODES}")

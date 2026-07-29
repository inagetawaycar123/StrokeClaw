import pytest

from backend.three_class.result import (
    aggregate_three_class_predictions,
    predictions_from_probabilities,
    unavailable_three_class_result,
)


def _row(*, hemo, infarct, normal, stored_label="infarct"):
    return {
        "slice_file": "slice_000_ncct.png",
        "pred_label": stored_label,
        "confidence": infarct,
        "prob_hemo": hemo,
        "prob_infarct": infarct,
        "prob_normal": normal,
    }


def test_real_argmax_replaces_historical_forced_label():
    rows = predictions_from_probabilities(
        [_row(hemo=0.04, infarct=0.16, normal=0.80)]
    )
    assert rows[0]["pred_label"] == "normal"
    assert rows[0]["confidence"] == pytest.approx(0.80)


def test_any_hemorrhage_slice_activates_safety_gate():
    result = aggregate_three_class_predictions(
        [
            _row(hemo=0.10, infarct=0.75, normal=0.15),
            _row(hemo=0.61, infarct=0.20, normal=0.19),
        ]
    )
    assert result["three_class_label"] == "hemo"
    assert result["three_class_confidence"] == pytest.approx(0.61)
    assert result["class_counts"] == {"hemo": 1, "infarct": 1, "normal": 0}
    assert result["safety_gate"]["blocked"] is True
    assert (
        result["safety_gate"]["reason_code"] == "NCCT_SUSPECTED_HEMORRHAGE"
    )


def test_non_hemorrhage_majority_and_tie_break_are_deterministic():
    result = aggregate_three_class_predictions(
        [
            _row(hemo=0.05, infarct=0.70, normal=0.25),
            _row(hemo=0.05, infarct=0.20, normal=0.75),
        ]
    )
    assert result["three_class_label"] == "infarct"
    assert result["three_class_confidence"] == pytest.approx(0.70)
    assert result["safety_gate"]["blocked"] is False


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [_row(hemo=None, infarct=0.4, normal=0.6)],
        [_row(hemo=1.2, infarct=0.0, normal=0.0)],
    ],
)
def test_invalid_or_empty_probabilities_fail_closed(rows):
    with pytest.raises(ValueError):
        aggregate_three_class_predictions(rows)


def test_unavailable_result_blocks_downstream_analysis():
    result = unavailable_three_class_result(reason="test")
    assert result["status"] == "failed"
    assert result["safety_gate"]["blocked"] is True
    assert result["safety_gate"]["requires_clinician_review"] is True

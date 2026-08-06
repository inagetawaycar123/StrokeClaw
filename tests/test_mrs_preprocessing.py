import numpy as np

from mrs_prediction.preprocessing import ClinicalPreprocessor, extract_feature_values


def _records():
    return [
        {
            "Gender": "F",
            "Age": "60",
            "Onset to CT time": "0.10",
            "NIHSS Baseline": "4",
            "NIHSS 24 HOURS": "2",
        },
        {
            "Gender": "M",
            "Age": "80",
            "Onset to CT time": "0.20",
            "NIHSS Baseline": "10",
            "NIHSS 24 HOURS": "",
        },
    ]


def test_baseline_and_update_24h_have_distinct_fixed_shapes():
    baseline = ClinicalPreprocessor("baseline").fit(_records())
    update = ClinicalPreprocessor("update_24h").fit(_records())
    assert baseline.output_dim == 8
    assert update.output_dim == 12
    assert baseline.transform(_records()).shape == (2, 8)
    transformed = update.transform(_records())
    assert transformed.shape == (2, 12)
    assert transformed[1, -2] == 1.0
    assert transformed[1, -1] == 1.0


def test_nihss_change_is_computed_centrally_and_serialization_roundtrips():
    values = extract_feature_values(_records()[0], "update_24h")
    assert values["nihss_change_24h"] == -2.0
    fitted = ClinicalPreprocessor("baseline").fit(_records())
    restored = ClinicalPreprocessor.from_dict(fitted.to_dict())
    np.testing.assert_allclose(fitted.transform(_records()), restored.transform(_records()))


def test_legacy_excel_day_fraction_is_converted_to_hours():
    values = extract_feature_values(_records()[0], "baseline")
    np.testing.assert_allclose(values["onset_to_ct_time"], 2.4)


def test_audited_onset_hours_take_precedence_over_raw_excel_value():
    record = {**_records()[0], "Onset to CT time": "23.1", "onset_to_ct_hours": "3.5"}
    values = extract_feature_values(record, "baseline")
    assert values["onset_to_ct_time"] == 3.5

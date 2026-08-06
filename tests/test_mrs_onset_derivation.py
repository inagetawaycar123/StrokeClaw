import pytest

from mrs_prediction.manifest import derive_onset_to_ct


def test_onset_derivation_handles_same_day_and_midnight_crossing():
    same_day = derive_onset_to_ct(
        {
            "Time of Symptom onset": 0.875,
            "Time of Initial CT_Osirix": 0.927083333333333,
            "Onset to CT time": 24.0520833333333,
            "Stroke on awakening/Unwitnessed": 0,
            "Stroke witnessed": 1,
        }
    )
    crossing = derive_onset_to_ct(
        {
            "Time of Symptom onset": 0.947916666666667,
            "Time of Initial CT_Osirix": 0.0916666666666667,
            "Onset to CT time": 23.14375,
            "Stroke on awakening/Unwitnessed": 0,
            "Stroke witnessed": 1,
        }
    )
    assert same_day["onset_to_ct_hours"] == pytest.approx(1.25)
    assert crossing["onset_to_ct_hours"] == pytest.approx(3.45)
    assert same_day["onset_to_ct_correction_applied"] is True
    assert crossing["onset_to_ct_correction_applied"] is True


def test_missing_source_time_is_not_fabricated():
    result = derive_onset_to_ct(
        {
            "Time of Symptom onset": "na",
            "Time of Initial CT_Osirix": 0.3,
            "Onset to CT time": "#VALUE!",
            "Stroke on awakening/Unwitnessed": 1,
            "Stroke witnessed": 0,
        }
    )
    assert result["onset_to_ct_hours"] == ""
    assert result["onset_to_ct_derivation_status"] == "unavailable_missing_source_time"
    assert result["onset_to_ct_witness_status"] == "unwitnessed_or_wakeup"

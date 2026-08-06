from backend.report_generation import _ctp_values


def test_case_analysis_values_override_legacy_patient_fields():
    core, penumbra, mismatch = _ctp_values(
        {
            "core_infarct_volume": 99,
            "penumbra_volume": 1,
            "mismatch_ratio": 0.1,
        },
        {
            "analysis_result": {
                "core_volume_ml": 6.14,
                "penumbra_volume_ml": 17.21,
                "mismatch_ratio": 2.8,
            }
        },
    )

    assert core == 6.14
    assert penumbra == 17.21
    assert mismatch == 2.8

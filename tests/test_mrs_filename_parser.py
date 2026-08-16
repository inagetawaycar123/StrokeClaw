from mrs_prediction.channel_analysis import FILENAME_PATTERN


def test_real_filename_pattern_keeps_full_patient_prefix_and_slice():
    match = FILENAME_PATTERN.match("04-123_015.npy")
    assert match is not None
    assert match.groupdict() == {"group": "04", "subject": "123", "slice": "015"}


def test_invalid_filename_is_rejected():
    assert FILENAME_PATTERN.match("04_123_015.npy") is None


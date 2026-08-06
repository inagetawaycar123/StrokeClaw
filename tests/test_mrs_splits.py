from collections import Counter

from mrs_prediction.splits import assign_stratified_folds


def test_patient_level_stratified_five_fold_assignment_is_unique_and_balanced():
    records = [
        {"patient_key": f"{index:03d}", "clinical_patient_id": f"P-{index:03d}", "binary_label": index % 2}
        for index in range(30)
    ]
    assignments = assign_stratified_folds(records, n_splits=5, seed=11)
    assert len(assignments) == 30
    assert len({item["patient_key"] for item in assignments}) == 30
    for fold in range(5):
        labels = [item["binary_label"] for item in assignments if item["fold"] == fold]
        assert Counter(labels) == {0: 3, 1: 3}


def test_stratified_assignment_is_deterministic():
    records = [
        {"patient_key": str(index), "clinical_patient_id": str(index), "binary_label": index % 2}
        for index in range(20)
    ]
    assert assign_stratified_folds(records, seed=99) == assign_stratified_folds(records, seed=99)


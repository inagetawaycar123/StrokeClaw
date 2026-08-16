import json

import numpy as np
import torch

from mrs_prediction.dataset import MRSPatientDataset, mrs_patient_collate
from mrs_prediction.preprocessing import ClinicalPreprocessor


def _record(key, files, label):
    return {
        "patient_key": key,
        "clinical_patient_id": f"ProVe-IT-01-{key}",
        "binary_label": str(label),
        "npy_bundle_files": json.dumps(files),
        "Gender": "M" if label else "F",
        "Age": "70",
        "Onset to CT time": "0.1",
        "NIHSS Baseline": "8",
        "NIHSS 24 HOURS": "4",
    }


def test_dataset_selects_internal_ncct_and_collate_masks_variable_files(tmp_path):
    for index in range(5):
        array = np.zeros((16, 16, 4), dtype=np.float32)
        array[..., 0] = index / 10.0
        array[..., 1:] = 0.9
        np.save(tmp_path / f"01-10{index}_{index}.npy", array)
    records = [
        _record("101", ["01-100_0.npy", "01-101_1.npy"], 0),
        _record("102", ["01-102_2.npy", "01-103_3.npy", "01-104_4.npy"], 1),
    ]
    preprocessor = ClinicalPreprocessor("baseline").fit(records)
    dataset = MRSPatientDataset(records, tmp_path, preprocessor, image_size=(16, 16))
    batch = mrs_patient_collate([dataset[0], dataset[1]])
    assert batch["ncct_images"].shape == (2, 3, 1, 16, 16)
    assert batch["clinical"].shape == (2, 8)
    assert batch["ncct_mask"].tolist() == [[True, True, False], [True, True, True]]
    assert torch.all(batch["ncct_images"][0, 0] == 0.0)
    assert torch.all(batch["ncct_images"][0, 1] == 0.1)
    assert torch.all(batch["ncct_images"][0, 2] == 0.0)


from pathlib import Path

import numpy as np

from mrs_prediction.image_preprocessing import ImagePreprocessor, NCCTResizeCache


def test_resize_cache_and_fold_statistics_use_only_supplied_patients(tmp_path: Path):
    image_root = tmp_path / "images"
    image_root.mkdir()
    records = []
    for index, value in enumerate((10.0, 20.0, 200.0)):
        filename = f"01-{index:03d}_001.npy"
        array = np.zeros((8, 8, 4), dtype=np.float32)
        array[..., 0] = value
        np.save(image_root / filename, array)
        records.append(
            {
                "patient_key": f"p-{index}",
                "npy_bundle_files": f'["{filename}"]',
            }
        )
    cache = NCCTResizeCache.build_or_load(records, image_root, tmp_path / "cache", (4, 4))
    preprocessor = ImagePreprocessor.fit(records[:2], cache)
    assert preprocessor.fitted_patient_count == 2
    assert preprocessor.fitted_file_count == 2
    assert preprocessor.mean == 15.0
    assert np.isclose(preprocessor.std, 5.0)
    assert cache.metadata["contains_fitted_statistics"] is False

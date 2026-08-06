"""Standalone online inference for the two research MVP ensemble bundles."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from .calibration import calibrated_probability
from .dataset import ncct_bundle_files
from .image_preprocessing import ImagePreprocessor, _load_resized_ncct, resize_ncct_array
from .model import ClinicalOnlyMRSModel, NCCTClinicalMRSModel
from .preprocessing import ClinicalPreprocessor, extract_feature_values
from .schema import FEATURE_SCHEMA_VERSION, RAW_COLUMN_BY_FEATURE


REQUIRED_MVP_BUNDLE_FIELDS = {
    "ensemble_state_dicts",
    "ensemble_seeds",
    "model_config",
    "model_mode",
    "clinical_feature_names",
    "clinical_preprocessor",
    "image_preprocessing_config",
    "class_mapping",
    "temperature_scaling_parameter",
    "decision_threshold",
    "feature_schema_version",
    "onset_to_ct_schema_version",
    "cohort_schema_version",
    "model_version",
    "oof_metrics",
    "external_validation_completed",
    "release_status",
    "online_loading_permitted",
    "is_real_inference",
    "production_approved",
}


class MVPBundleError(RuntimeError):
    """Raised when an MVP bundle cannot safely be used for inference."""


def _unavailable(
    error_code: str,
    message: str,
    *,
    model_mode: str,
    missing_requirements: Sequence[str] = (),
    model_forward_executed: bool = False,
) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "error_code": error_code,
        "message": message,
        "model_mode": model_mode,
        "missing_requirements": list(missing_requirements),
        "model_forward_executed": model_forward_executed,
    }


def _instantiate_model(bundle: Mapping[str, Any]) -> torch.nn.Module:
    config = dict(bundle["model_config"])
    model_name = str(config["model_name"])
    common = {
        "embedding_dim": int(config["embedding_dim"]),
        "dropout": float(config["dropout"]),
    }
    clinical_dim = int(config["clinical_input_dim"])
    if model_name == "clinical_only":
        return ClinicalOnlyMRSModel(clinical_dim, **common)
    if model_name == "ncct_clinical":
        return NCCTClinicalMRSModel(
            clinical_dim,
            **common,
            attention_dim=int(config["attention_dim"]),
            base_channels=int(config["base_channels"]),
            fusion_dim=int(config["fusion_dim"]),
        )
    raise MVPBundleError(f"Unsupported MVP model_name={model_name!r}")


def _confidence(
    *,
    ensemble_probability_std: float,
    threshold_margin: float,
    missing_clinical_fields: Sequence[str],
    image_quality_warnings: Sequence[str],
) -> dict[str, Any]:
    reasons: list[str] = []
    if ensemble_probability_std > 0.12:
        reasons.append("high ensemble disagreement")
    elif ensemble_probability_std > 0.05:
        reasons.append("moderate ensemble disagreement")
    else:
        reasons.append("low ensemble disagreement")
    if threshold_margin < 0.05:
        reasons.append("prediction is close to the decision threshold")
    elif threshold_margin < 0.15:
        reasons.append("prediction has a moderate threshold margin")
    else:
        reasons.append("prediction is separated from the decision threshold")
    if missing_clinical_fields:
        reasons.append("missing clinical fields: " + ", ".join(missing_clinical_fields))
    if image_quality_warnings:
        reasons.append("image quality warnings are present")

    if (
        ensemble_probability_std > 0.12
        or threshold_margin < 0.05
        or len(missing_clinical_fields) >= 2
        or len(image_quality_warnings) >= 2
    ):
        level = "low"
    elif (
        ensemble_probability_std > 0.05
        or threshold_margin < 0.15
        or missing_clinical_fields
        or image_quality_warnings
    ):
        level = "medium"
    else:
        level = "high"
    return {
        "level": level,
        "reasons": reasons,
        "ensemble_probability_std": float(ensemble_probability_std),
        "threshold_margin": float(threshold_margin),
    }


class MRSMVPEnsemble:
    """Load one three-seed MVP bundle and run deterministic ensemble inference."""

    def __init__(self, bundle_path: str | Path, *, device: str = "auto") -> None:
        self.bundle_path = Path(bundle_path).resolve()
        if not self.bundle_path.exists():
            raise MVPBundleError(f"MVP bundle does not exist: {self.bundle_path}")
        self.bundle = torch.load(self.bundle_path, map_location="cpu", weights_only=False)
        missing = REQUIRED_MVP_BUNDLE_FIELDS - set(self.bundle)
        if missing:
            raise MVPBundleError(f"MVP bundle is missing fields: {sorted(missing)}")
        if self.bundle.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
            raise MVPBundleError("MVP feature schema version is incompatible")
        if self.bundle.get("release_status") != "MVP_RESEARCH":
            raise MVPBundleError("MVP bundle release_status is incompatible")
        if self.bundle.get("online_loading_permitted") is not True:
            raise MVPBundleError("MVP bundle is not permitted for online loading")
        if self.bundle.get("is_real_inference") is not True:
            raise MVPBundleError("MVP bundle is not marked for real inference")
        if self.bundle.get("production_approved") is not False:
            raise MVPBundleError("MVP bundle must remain production_approved=false")
        if self.bundle.get("external_validation_completed") is not False:
            raise MVPBundleError("Unexpected external validation flag")
        states = list(self.bundle["ensemble_state_dicts"])
        seeds = list(self.bundle["ensemble_seeds"])
        if len(states) != 3 or len(seeds) != 3 or len(set(int(seed) for seed in seeds)) != 3:
            raise MVPBundleError("MVP bundle must contain exactly three distinct ensemble members")
        requested = str(device)
        if requested == "cuda" and not torch.cuda.is_available():
            raise MVPBundleError("CUDA was requested but is unavailable")
        self.device = torch.device(
            "cuda" if requested == "cuda" or (requested == "auto" and torch.cuda.is_available()) else "cpu"
        )
        self.preprocessor = ClinicalPreprocessor.from_dict(self.bundle["clinical_preprocessor"])
        self.image_preprocessor = None
        if self.bundle["model_config"]["model_name"] != "clinical_only":
            self.image_preprocessor = ImagePreprocessor.from_dict(
                self.bundle["image_preprocessing_config"]
            )
        self.models: list[torch.nn.Module] = []
        for state in states:
            model = _instantiate_model(self.bundle)
            model.load_state_dict(state, strict=True)
            model.to(self.device)
            model.eval()
            self.models.append(model)
        self.forward_call_count = 0

    @property
    def model_mode(self) -> str:
        return str(self.bundle["model_mode"])

    def _clinical_tensor(self, record: Mapping[str, Any]) -> tuple[torch.Tensor, list[str]]:
        values = extract_feature_values(record, self.model_mode)
        missing = [name for name, value in values.items() if not np.isfinite(value)]
        transformed = self.preprocessor.transform_one(record)
        return torch.from_numpy(transformed).unsqueeze(0).to(self.device), missing

    def _image_tensor(
        self,
        record: Mapping[str, Any],
        *,
        image_root: str | Path | None,
        image_files: Sequence[str | Path] | None,
        image_arrays: Sequence[np.ndarray] | None,
        image_source_files: Sequence[str] | None,
    ) -> tuple[torch.Tensor, torch.Tensor, list[str], list[str]]:
        if self.image_preprocessor is None:
            raise MVPBundleError("Clinical-only bundle does not accept NCCT input")
        if image_arrays is not None:
            arrays = list(image_arrays)
            labels = list(image_source_files or [])
            if labels and len(labels) != len(arrays):
                raise MVPBundleError("image_source_files must match image_arrays")
            if not labels:
                labels = [f"online_ncct_slice_{index:03d}" for index in range(len(arrays))]
            maximum = self.bundle["model_config"].get("max_ncct_files")
            if maximum and len(arrays) > int(maximum):
                indices = np.linspace(0, len(arrays) - 1, int(maximum), dtype=int)
                arrays = [arrays[index] for index in indices]
                labels = [labels[index] for index in indices]
            tensors: list[torch.Tensor] = []
            used_files: list[str] = []
            warnings: list[str] = []
            for array, label in zip(arrays, labels, strict=True):
                try:
                    resized = resize_ncct_array(array, self.image_preprocessor.image_size)
                    tensor = torch.from_numpy(resized).unsqueeze(0)
                    tensors.append(self.image_preprocessor.normalize(tensor))
                    used_files.append(str(label))
                except Exception as exc:
                    warnings.append(f"{label}: {type(exc).__name__}: {exc}")
            if not tensors:
                raise MVPBundleError("No readable NCCT slices remain after image quality checks")
            images = torch.stack(tensors).unsqueeze(0).to(self.device)
            mask = torch.ones((1, len(tensors)), dtype=torch.bool, device=self.device)
            return images, mask, used_files, warnings

        files = [str(path) for path in image_files] if image_files is not None else ncct_bundle_files(record)
        if not files:
            raise MVPBundleError("No NCCT-containing .npy files were provided")
        maximum = self.bundle["model_config"].get("max_ncct_files")
        if maximum and len(files) > int(maximum):
            indices = np.linspace(0, len(files) - 1, int(maximum), dtype=int)
            files = [files[index] for index in indices]
        root = Path(image_root).resolve() if image_root is not None else None
        tensors: list[torch.Tensor] = []
        used_files: list[str] = []
        warnings: list[str] = []
        for filename in files:
            path = Path(filename)
            if not path.is_absolute():
                if root is None:
                    raise MVPBundleError("image_root is required for relative NCCT filenames")
                path = root / path
            try:
                array = _load_resized_ncct(path, self.image_preprocessor.image_size)
                tensor = torch.from_numpy(array).unsqueeze(0)
                tensors.append(self.image_preprocessor.normalize(tensor))
                used_files.append(str(path))
            except Exception as exc:  # keep usable slices but report every rejected slice
                warnings.append(f"{path.name}: {type(exc).__name__}: {exc}")
        if not tensors:
            raise MVPBundleError("No readable NCCT files remain after image quality checks")
        images = torch.stack(tensors).unsqueeze(0).to(self.device)
        mask = torch.ones((1, len(tensors)), dtype=torch.bool, device=self.device)
        return images, mask, used_files, warnings

    def predict(
        self,
        record: Mapping[str, Any],
        *,
        image_root: str | Path | None = None,
        image_files: Sequence[str | Path] | None = None,
        image_arrays: Sequence[np.ndarray] | None = None,
        image_source_files: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        patient_key = str(record.get("patient_key", ""))
        if self.model_mode == "update_24h":
            values = extract_feature_values(record, self.model_mode)
            if not np.isfinite(values["nihss_24h"]):
                return {
                    **_unavailable(
                        "MISSING_NIHSS_24H",
                        "24-hour NIHSS is required for the update_24h model",
                        model_mode=self.model_mode,
                        missing_requirements=["NIHSS 24 HOURS"],
                        model_forward_executed=False,
                    ),
                    "patient_key": patient_key,
                }

        try:
            clinical, missing_clinical = self._clinical_tensor(record)
            image_quality_warnings: list[str] = []
            used_files: list[str] = []
            arguments: dict[str, torch.Tensor] = {"clinical": clinical}
            if self.bundle["model_config"]["model_name"] != "clinical_only":
                images, mask, used_files, image_quality_warnings = self._image_tensor(
                    record,
                    image_root=image_root,
                    image_files=image_files,
                    image_arrays=image_arrays,
                    image_source_files=image_source_files,
                )
                arguments.update({"ncct_images": images, "ncct_mask": mask})
        except Exception as exc:
            return {
                **_unavailable(
                    "INPUT_PREPROCESSING_FAILED",
                    str(exc),
                    model_mode=self.model_mode,
                    model_forward_executed=False,
                ),
                "patient_key": patient_key,
            }

        logits: list[float] = []
        attention_rows: list[np.ndarray] = []
        base_model_outputs: list[Mapping[str, torch.Tensor]] = []
        try:
            with torch.no_grad():
                for model in self.models:
                    self.forward_call_count += 1
                    model_output = model(**arguments)
                    base_model_outputs.append(model_output)
                    logits.append(float(model_output["logit"].detach().cpu().item()))
                    attention = model_output.get("attention_weights")
                    if attention is not None:
                        attention_rows.append(
                            np.asarray(attention.detach().cpu()[0], dtype=np.float64)
                        )
        except Exception as exc:
            return {
                **_unavailable(
                    "MODEL_FORWARD_FAILED",
                    str(exc),
                    model_mode=self.model_mode,
                    model_forward_executed=bool(self.forward_call_count),
                ),
                "patient_key": patient_key,
            }
        mean_logit = float(np.mean(logits))
        temperature = float(self.bundle["temperature_scaling_parameter"])
        risk = float(calibrated_probability([mean_logit], temperature)[0])
        member_risks = calibrated_probability(np.asarray(logits), temperature)
        threshold = float(self.bundle["decision_threshold"])
        margin = abs(risk - threshold)
        confidence = _confidence(
            ensemble_probability_std=float(np.std(member_risks, ddof=0)),
            threshold_margin=margin,
            missing_clinical_fields=missing_clinical,
            image_quality_warnings=image_quality_warnings,
        )
        clinical_evidence: list[dict[str, Any]] = []
        feature_values = extract_feature_values(record, self.model_mode)
        try:
            with torch.no_grad():
                for feature_index, feature_name in enumerate(self.preprocessor.feature_names):
                    raw_value = feature_values.get(feature_name)
                    if raw_value is None or not np.isfinite(raw_value):
                        continue
                    occluded_arguments = dict(arguments)
                    occluded_clinical = clinical.clone()
                    # Zero is the stored training-population mean in standardized space.
                    occluded_clinical[:, feature_index] = 0.0
                    occluded_arguments["clinical"] = occluded_clinical
                    reference_logits = []
                    for model, base_output in zip(
                        self.models, base_model_outputs, strict=True
                    ):
                        if (
                            "ncct_embedding" in base_output
                            and hasattr(model, "clinical_encoder")
                            and hasattr(model, "fusion")
                            and hasattr(model, "classifier")
                        ):
                            clinical_embedding = model.clinical_encoder(
                                occluded_clinical
                            )
                            fused, _gate = model.fusion(
                                base_output["ncct_embedding"], clinical_embedding
                            )
                            reference_logit = model.classifier(fused).squeeze(-1)
                        else:
                            reference_logit = model(**occluded_arguments)["logit"]
                        reference_logits.append(
                            float(reference_logit.detach().cpu().item())
                        )
                    contribution = mean_logit - float(np.mean(reference_logits))
                    clinical_evidence.append(
                        {
                            "feature": feature_name,
                            "display_name": str(
                                RAW_COLUMN_BY_FEATURE.get(feature_name) or feature_name
                            ),
                            "value": float(raw_value),
                            "contribution": float(contribution),
                            "direction": (
                                "increase_poor_prognosis_risk"
                                if contribution > 0
                                else "decrease_poor_prognosis_risk"
                                if contribution < 0
                                else "neutral"
                            ),
                            "attribution_method": "standardized_mean_occlusion_logit_delta",
                        }
                    )
        except Exception:
            # Attribution is supplementary and must never alter model probability.
            clinical_evidence = []
        clinical_evidence.sort(key=lambda item: abs(float(item["contribution"])), reverse=True)

        imaging_evidence: list[dict[str, Any]] = []
        if attention_rows and used_files:
            mean_attention = np.mean(np.stack(attention_rows), axis=0)
            for index in np.argsort(-mean_attention)[: min(3, len(used_files))]:
                imaging_evidence.append(
                    {
                        "channel": "01_NCCT",
                        "source_file": used_files[int(index)],
                        "attention_score": float(mean_attention[int(index)]),
                        "contribution_direction": "unknown",
                        "interpretation": "模型高关注文件；attention不代表因果贡献或确定病灶",
                    }
                )
        return {
            "status": "success",
            "patient_key": patient_key,
            "model": {
                "mode": self.model_mode,
                "name": self.bundle["model_config"]["class_name"],
                "version": self.bundle["model_version"],
                "bundle_version": self.bundle.get("bundle_version"),
                "release_status": self.bundle["release_status"],
                "is_real_inference": True,
                "production_approved": False,
                "ensemble_seeds": list(self.bundle["ensemble_seeds"]),
            },
            "prediction": {
                "raw_ensemble_logits": logits,
                "mean_raw_logit": mean_logit,
                "good_prognosis_probability": float(1.0 - risk),
                "poor_prognosis_risk": risk,
                "predicted_class": int(risk >= threshold),
                "class_name": self.bundle["class_mapping"][str(int(risk >= threshold))],
                "decision_threshold": threshold,
                "probability_calibrated": True,
            },
            "confidence": confidence,
            "key_evidence": {
                "clinical": clinical_evidence[:3],
                "imaging": imaging_evidence,
                "attribution_notice": "模型归因不代表因果关系。",
            },
            "data_quality": {
                "missing_clinical_fields": missing_clinical,
                "used_ncct_files": used_files,
                "image_quality_warnings": image_quality_warnings,
            },
            "model_forward_executed": True,
        }


class MRSInferenceRouter:
    """Route baseline/update requests to their fixed MVP bundles."""

    def __init__(
        self,
        baseline_bundle: str | Path,
        update24h_bundle: str | Path,
        *,
        device: str = "auto",
    ) -> None:
        self.models = {
            "baseline": MRSMVPEnsemble(baseline_bundle, device=device),
            "update_24h": MRSMVPEnsemble(update24h_bundle, device=device),
        }
        for requested, model in self.models.items():
            if model.model_mode != requested:
                raise MVPBundleError(
                    f"Bundle routing mismatch: route={requested}, bundle={model.model_mode}"
                )

    def predict(
        self,
        model_mode: str,
        record: Mapping[str, Any],
        *,
        image_root: str | Path | None = None,
        image_files: Sequence[str | Path] | None = None,
        image_arrays: Sequence[np.ndarray] | None = None,
        image_source_files: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        if model_mode not in self.models:
            return _unavailable(
                "UNSUPPORTED_MODEL_MODE",
                f"Unsupported model_mode={model_mode!r}",
                model_mode=model_mode,
                missing_requirements=["baseline or update_24h"],
            )
        return self.models[model_mode].predict(
            record,
            image_root=image_root,
            image_files=image_files,
            image_arrays=image_arrays,
            image_source_files=image_source_files,
        )

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torchvision")
from PIL import Image
from torch import nn

from backend import dinov3_adapter as adapter


class _StrictConfig:
    """Small stand-in for torch 2.1's strict Dynamo ConfigModule."""

    def __init__(self) -> None:
        object.__setattr__(self, "_config", {})
        object.__setattr__(self, "_default", {})
        object.__setattr__(self, "_allowed_keys", set())

    def __getattr__(self, name):
        try:
            return self._config[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value) -> None:
        if name not in self._allowed_keys:
            raise AttributeError(name)
        self._config[name] = value


class _FakeBackbone(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.blocks = nn.ModuleList([nn.Linear(1, 1), nn.Linear(1, 1)])
        self.norm = nn.LayerNorm(4)

    def get_intermediate_layers(self, inputs, **_kwargs):
        return [torch.ones((inputs.shape[0], 4, 2, 2), device=inputs.device)]


@pytest.fixture(autouse=True)
def _clear_model_cache():
    adapter._MODEL_MANAGER.clear()
    yield
    adapter._MODEL_MANAGER.clear()


def _write_required_files(tmp_path: Path):
    model_path = tmp_path / "classifier.pth"
    weights_path = tmp_path / "backbone.pth"
    repo_dir = tmp_path / "repo"
    image_path = tmp_path / "slice.png"
    model_path.write_bytes(b"classifier")
    weights_path.write_bytes(b"backbone")
    (repo_dir / "dinov3" / "hub").mkdir(parents=True)
    (repo_dir / "dinov3" / "hub" / "backbones.py").write_text(
        "# test placeholder\n", encoding="utf-8"
    )
    Image.new("RGB", (32, 48), color=(100, 120, 140)).save(image_path)
    return image_path, model_path, weights_path, repo_dir


def test_registers_missing_pytorch_21_dynamo_setting():
    config = _StrictConfig()

    adapter._ensure_dynamo_config_compat(config)

    assert config.accumulated_cache_size_limit == 1024
    assert config._default["accumulated_cache_size_limit"] == 1024
    assert "accumulated_cache_size_limit" in config._allowed_keys


def test_imports_backbone_directly_without_torch_hub(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo"
    backbones_path = repo_dir / "dinov3" / "hub" / "backbones.py"
    backbones_path.parent.mkdir(parents=True)
    backbones_path.write_text("# test placeholder\n", encoding="utf-8")
    fake_factory = lambda **_kwargs: _FakeBackbone()
    imported = []

    def fake_import_module(name):
        imported.append(name)
        return SimpleNamespace(
            __file__=str(backbones_path),
            dinov3_vitb16=fake_factory,
        )

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    monkeypatch.setattr(
        torch.hub,
        "load",
        lambda *_args, **_kwargs: pytest.fail("torch.hub.load must not be used"),
    )
    monkeypatch.setattr(adapter.sys, "path", list(adapter.sys.path))

    result = adapter._import_backbone_factory(str(repo_dir))

    assert result is fake_factory
    assert imported == ["dinov3.hub.backbones"]


def test_predict_contract_and_thread_safe_cache(monkeypatch, tmp_path):
    image_path, model_path, weights_path, repo_dir = _write_required_files(
        tmp_path
    )
    factory_calls = []

    def fake_factory(*, pretrained):
        factory_calls.append(pretrained)
        return _FakeBackbone()

    monkeypatch.setattr(adapter, "_import_backbone_factory", lambda _path: fake_factory)
    monkeypatch.setattr(adapter, "_select_device", lambda: torch.device("cpu"))
    monkeypatch.setattr(torch, "load", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        adapter.CAMClassifier,
        "load_state_dict",
        lambda self, state_dict, strict=True: None,
    )

    def deterministic_forward(self, inputs):
        return torch.tensor([[0.0, 2.0, 1.0]], device=inputs.device)

    monkeypatch.setattr(adapter.CAMClassifier, "forward", deterministic_forward)

    kwargs = {
        "image_path": str(image_path),
        "model_path": str(model_path),
        "dinov3_weights": str(weights_path),
        "repo_dir": str(repo_dir),
        "verbose": False,
    }
    first = adapter.predict_single_image(**kwargs)
    second = adapter.predict_single_image(**kwargs)

    assert factory_calls == [False]
    assert first == second
    assert first["predicted_class"] == 1
    assert first["predicted_label"] == "Class_1_LVO"
    assert first["label"] == "Class_1_LVO"
    assert first["confidence"] == pytest.approx(
        first["probabilities"]["Class_1_LVO"]
    )
    assert sum(first["probabilities"].values()) == pytest.approx(1.0)
    assert set(first["probabilities"]) == set(adapter.DEFAULT_CLASS_NAMES)


def test_missing_classifier_weights_fail_before_model_construction(
    monkeypatch, tmp_path
):
    image_path, model_path, weights_path, repo_dir = _write_required_files(
        tmp_path
    )
    model_path.unlink()
    monkeypatch.setattr(adapter, "_select_device", lambda: torch.device("cpu"))
    monkeypatch.setattr(
        adapter,
        "_import_backbone_factory",
        lambda _path: pytest.fail("backbone must not be constructed"),
    )

    with pytest.raises(FileNotFoundError, match="classifier weights"):
        adapter.predict_single_image(
            image_path=str(image_path),
            model_path=str(model_path),
            dinov3_weights=str(weights_path),
            repo_dir=str(repo_dir),
        )

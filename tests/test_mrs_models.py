import torch
from torch import nn

from mrs_prediction.model import (
    ClinicalOnlyMRSModel,
    NCCTClinicalMRSModel,
    NCCTOnlyMRSModel,
    PatientNCCTEncoder,
)


def _inputs(clinical_dim=8):
    torch.manual_seed(7)
    images = torch.rand(2, 3, 1, 32, 32)
    mask = torch.tensor([[True, True, False], [True, True, True]])
    clinical = torch.rand(2, clinical_dim)
    label = torch.tensor([0.0, 1.0])
    return images, mask, clinical, label


def test_all_three_models_forward_and_single_batch_backward():
    images, mask, clinical, label = _inputs()
    models = [
        ClinicalOnlyMRSModel(8, embedding_dim=16),
        NCCTOnlyMRSModel(embedding_dim=16, attention_dim=8, base_channels=4),
        NCCTClinicalMRSModel(8, embedding_dim=16, attention_dim=8, base_channels=4, fusion_dim=16),
    ]
    criterion = nn.BCEWithLogitsLoss()
    for model in models:
        output = model(ncct_images=images, ncct_mask=mask, clinical=clinical)
        assert output["logit"].shape == (2,)
        loss = criterion(output["logit"], label)
        loss.backward()
        assert any(parameter.grad is not None for parameter in model.parameters())
        attention = output.get("attention_weights")
        if attention is not None:
            assert attention.shape == (2, 3)
            assert attention[0, 2].item() == 0.0
            torch.testing.assert_close(attention.sum(dim=1), torch.ones(2))


def test_update_24h_clinical_shape_is_supported():
    _, _, clinical, _ = _inputs(clinical_dim=12)
    output = ClinicalOnlyMRSModel(12, embedding_dim=8)(clinical=clinical)
    assert output["logit"].shape == (2,)


def test_patient_encoder_does_not_send_padding_through_batch_norm():
    model = PatientNCCTEncoder(embedding_dim=8, attention_dim=4, base_channels=2, dropout=0.0)
    model.eval()
    valid = torch.randn(1, 2, 1, 32, 32)
    padded_a = torch.cat([valid, torch.zeros(1, 1, 1, 32, 32)], dim=1)
    padded_b = padded_a.clone()
    padded_b[:, 2] = 1000.0
    mask = torch.tensor([[True, True, False]])
    with torch.no_grad():
        output_a, weights_a = model(padded_a, mask)
        output_b, weights_b = model(padded_b, mask)
    torch.testing.assert_close(output_a, output_b)
    torch.testing.assert_close(weights_a, weights_b)

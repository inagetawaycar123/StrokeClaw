---
license: other
license_name: health-ai-developer-foundations
license_link: https://developers.google.com/health-ai-developer-foundations/terms
library_name: transformers
pipeline_tag: image-text-to-text
extra_gated_heading: Access MedGemma on Hugging Face
extra_gated_prompt: >-
  To access MedGemma on Hugging Face, you're required to review and
  agree to [Health AI Developer Foundation's terms of use](https://developers.google.com/health-ai-developer-foundations/terms).
  To do this, please ensure you're logged in to Hugging Face and click below.
  Requests are processed immediately.
extra_gated_button_content: Acknowledge license
tags:
- medical
- radiology
- clinical-reasoning
- dermatology
- pathology
- ophthalmology
- chest-x-ray
---
# MedGemma 1.5 model card

Note: This card describes MedGemma 1.5, which is only available as a 4B
multimodal instruction-tuned variant. For information on MedGemma 1 variants,
refer to the [MedGemma 1 model
card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card-v1).

**Model documentation:** [MedGemma](https://developers.google.com/health-ai-developer-foundations/medgemma)

**Resources:**

*   Model on Google Cloud Model Garden: [MedGemma](https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/medgemma)
*   Models on Hugging Face: [Collection](https://huggingface.co/collections/google/medgemma-release-680aade845f90bec6a3f60c4)
*   Concept applications built using MedGemma: [Collection](https://huggingface.co/collections/google/medgemma-concept-apps-686ea036adb6d51416b0928a)
*   [GitHub repository](https://github.com/google-health/medgemma)
*   [Tutorial notebooks](https://github.com/google-health/medgemma/blob/main/notebooks)

*   License: The use of MedGemma is governed by the [Health AI Developer
    Foundations terms of
    use](https://developers.google.com/health-ai-developer-foundations/terms).
MedGemma has not been evaluated or optimized for multi-turn applications.

MedGemma's training may make it more sensitive to the specific prompt used than
Gemma 3.

When adapting MedGemma developer should consider the following:



*   License: The use of MedGemma is governed by the [Health AI Developer
    Foundations terms of
    use](https://developers.google.com/health-ai-developer-foundations/terms).

*   [Support](https://developers.google.com/health-ai-developer-foundations/medgemma/get-started.md#contact)
    channels

**Author:** Google

## Model information

This section describes the specifications and recommended use of the MedGemma
model.

### Description

MedGemma is a collection of [Gemma 3](https://ai.google.dev/gemma/docs/core)
variants that are trained for performance on medical text and image
comprehension. Developers can use MedGemma to accelerate building
healthcare-based AI applications.

MedGemma 1.5 4B is an updated version of the MedGemma 1 4B model.

MedGemma 1.5 4B expands support for several new medical imaging and data
processing applications, including:

*   **High-dimensional medical imaging:** Interpretation of three-dimensional
    volume representations of Computed Tomography (CT) and Magnetic Resonance
    Imaging (MRI).
*   **Whole-slide histopathology imaging (WSI):** Simultaneous interpretation of
    multiple patches from a whole slide histopathology image as input.
*   **Longitudinal medical imaging:** Interpretation of chest X-rays in the
    context of prior images (e.g., comparing current versus historical scans).
*   **Anatomical localization:** Bounding box‚Äìbased localization of anatomical
    features and findings in chest X-rays.
*   **Medical document understanding:** Extraction of structured data, such as
    values and units, from unstructured medical lab reports.
*   **Electronic Health Record (EHR) understanding:** Interpretation of
    text-based EHR data.

In addition to these new features, MedGemma 1.5 4B delivers improved accuracy on
medical text reasoning and modest improvement on standard 2D image
interpretation compared to MedGemma 1 4B.

MedGemma utilizes a [SigLIP](https://arxiv.org/abs/2303.15343) image encoder
that has been specifically pre-trained on a variety of de-identified medical
data, including chest X-rays, dermatology images, ophthalmology images, and
histopathology slides. The LLM component is trained on a diverse set of medical
data, including medical text, medical question-answer pairs, FHIR-based
electronic health record data, 2D and 3D radiology images, histopathology
images, ophthalmology images, dermatology images, and lab reports for document
understanding.

MedGemma 1.5 4B has been evaluated on a range of clinically relevant benchmarks
to illustrate its baseline performance. These evaluations are based on both open
benchmark datasets and internally curated datasets. Developers are expected to
fine-tune MedGemma for improved performance on their use case. Consult the
[Intended use section](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card.md#intended_use)
for more details.

MedGemma is optimized for medical applications that involve a text generation
component. For medical image-based applications that do not involve text
generation, such as data-efficient classification, zero-shot classification, or
content-based or semantic image retrieval, the [MedSigLIP image
encoder](https://developers.google.com/health-ai-developer-foundations/medsiglip/model-card)
is recommended. MedSigLIP is based on the same image encoder that powers
MedGemma 1 and MedGemma 1.5.

### How to use

The following are some example code snippets to help you quickly get started
running the model locally on GPU.

Note: If you need to use the model at scale, we recommend creating a production
version using [Model
Garden](https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/medgemma).
Model Garden provides various deployment options and tutorial notebooks,
including specialized server-side image processing options for efficiently
handling large medical images: Whole Slide Digital Pathology (WSI) or volumetric
scans (CT/MRI) stored in [Cloud DICOM
Store](https://docs.cloud.google.com/healthcare-api/docs/concepts/dicom) or
[Google Cloud Storage (GCS)](https://cloud.google.com/storage).

First, install the Transformers library. Gemma 3 is supported starting from
transformers 4.50.0.

```sh
$ pip install -U transformers
```

Next, use either the pipeline wrapper or the transformer API directly to send a
chest X-ray image and a question to the model.

Note that CT, MRI and whole-slide histopathology images require some
pre-processing; see the
[CT](https://github.com/google-health/medgemma/blob/main/notebooks/high_dimensional_ct_hugging_face.ipynb)
and
[WSI](https://github.com/google-health/medgemma/blob/main/notebooks/high_dimensional_pathology_hugging_face.ipynb)
notebook for examples.

**Run model with the pipeline API**

```python
from transformers import pipeline
from PIL import Image
import requests
import torch

pipe = pipeline(
    "image-text-to-text",
    model="google/medgemma-1.5-4b-it",
    torch_dtype=torch.bfloat16,
    device="cuda",
)

# Image attribution: Stillwaterising, CC0, via Wikimedia Commons
image_url = "https://upload.wikimedia.org/wikipedia/commons/c/c8/Chest_Xray_PA_3-8-2010.png"
image = Image.open(requests.get(image_url, headers={"User-Agent": "example"}, stream=True).raw)

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": "Describe this X-ray"}
        ]
    }
]

output = pipe(text=messages, max_new_tokens=2000)
print(output[0]["generated_text"][-1]["content"])
```

**Run the model directly**

```python
# Make sure to install the accelerate library first via `pip install accelerate`
from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import requests
import torch

model_id = "google/medgemma-1.5-4b-it"

model = AutoModelForImageTextToText.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)
processor = AutoProcessor.from_pretrained(model_id)

# Image attribution: Stillwaterising, CC0, via Wikimedia Commons
image_url = "https://upload.wikimedia.org/wikipedia/commons/c/c8/Chest_Xray_PA_3-8-2010.png"
image = Image.open(requests.get(image_url, headers={"User-Agent": "example"}, stream=True).raw)

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": "Describe this X-ray"}
        ]
    }
]

inputs = processor.apply_chat_template(
    messages, add_generation_prompt=True, tokenize=True,
    return_dict=True, return_tensors="pt"
).to(model.device, dtype=torch.bfloat16)

input_len = inputs["input_ids"].shape[-1]

with torch.inference_mode():
    generation = model.generate(**inputs, max_new_tokens=2000, do_sample=False)
    generation = generation[0][input_len:]

decoded = processor.decode(generation, skip_special_tokens=True)
print(decoded)
```

### Examples

Refer to the growing collection of [tutorial
notebooks](https://github.com/google-health/medgemma/blob/main/notebooks) to see
how to use or fine-tune MedGemma.

### Model architecture overview

The MedGemma model is built based on [Gemma 3](https://ai.google.dev/gemma/) and
uses the same decoder-only transformer architecture as Gemma 3. To read more
about the architecture, consult the Gemma 3 [model
card](https://ai.google.dev/gemma/docs/core/model_card_3).

### Technical specifications

*   **Model type**: Decoder-only Transformer architecture, see the [Gemma 3
    Technical
    Report](https://storage.googleapis.com/deepmind-media/gemma/Gemma3Report.pdf)
*   **Input modalities**: Text, vision (multimodal)
*   **Output modality**: Text only
*   **Attention mechanism**: Grouped-query attention (GQA)
*   **Context length**: Supports long context, at least 128K tokens
*   **Key publication**: [https://arxiv.org/abs/2507.05201](https://arxiv.org/abs/2507.05201)
*   **Model created**: **4B multimodal**: Jan 13, 2026
*   **Model version**: **4B multimodal**: 1.5.0

### Citation

When using this model, please cite: Sellergren et al. "MedGemma Technical
Report." *arXiv preprint arXiv:2507.05201* (2025).

```none
@article{sellergren2025medgemma,
  title={MedGemma Technical Report},
  author={Sellergren, Andrew and Kazemzadeh, Sahar and Jaroensri, Tiam and Kiraly, Atilla and Traverse, Madeleine and Kohlberger, Timo and Xu, Shawn and Jamil, Fayaz and Hughes, C√≠an and Lau, Charles and others},
  journal={arXiv preprint arXiv:2507.05201},
  year={2025}
}
```

### Inputs and outputs

**Input**:

*   Text string, such as a question or prompt
*   Images, normalized to 896 x 896 resolution and encoded to 256 tokens each
*   Total input length of 128K tokens

**Output**:

*   Generated text in response to the input, such as an answer to a question,
    analysis of image content, or a summary of a document
*   Total output length of 8192 tokens

### Performance and evaluations

MedGemma was evaluated across a range of different multimodal classification,
report generation, visual question answering, and text-based tasks.

### Key performance metrics

#### Imaging evaluations

The multimodal performance of MedGemma 1.5 4B was evaluated across a range of
benchmarks, focusing on radiology (2D, longitudinal 2D, and 3D), dermatology,
histopathology, ophthalmology, document understanding, and multimodal clinical
reasoning. See Data card for details of individual datasets.

We also list the previous results for MedGemma 1 4B and 27B (multimodal models
only), as well as for Gemma 3 4B for comparison.

| Task / Dataset | Metric | Gemma 3 4B | MedGemma 1 4B | MedGemma 1.5 4B | MedGemma 1 27B |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **3D radiology image classification** |  |  |  |  |  |
| CT Dataset 1\*(7 conditions/abnormalities) | Macro accuracy | 54.5 | 58.2 | 61.1 | 57.8 |
| CT-RATE (validation, 18 conditions/abnormalities ) | Macro F1 |  | 23.5 | 27.0 |  |
|  | Macro precision |  | 34.5 | 34.2 |  |
|  | Macro recall |  | 34.1 | 42.0 |  |
| MRI Dataset 1\*(10  conditions/abnormalities) | Macro accuracy | 51.1 | 51.3 | 64.7 | 57.4 |
| **2D image classification** |  |  |  |  |  |
| MIMIC CXR\*\* | Macro F1 (top 5 conditions) | 81.2 | 88.9 | 89.5 | 90.0 |
| CheXpert CXR | Macro F1 (top 5 conditions) | 32.6 | 48.1 | 48.2 | 49.9 |
| CXR14 | Macro F1 (3 conditions) | 32.0 | 50.1 | 48.4 | 45.3 |
| PathMCQA\* (histopathology) | Accuracy | 37.1 | 69.8 | 70.0 | 71.6 |
| WSI-Path\* (whole-slide histopathology) | ROUGE | 2.3 | 2.2 | 49.4 | 4.1 |
| US-DermMCQA\* | Accuracy | 52.5 | 71.8 | 73.5 | 71.7 |
| EyePACS\* (fundus) | Accuracy | 14.4 | 64.9 | 76.8 | 75.3 |
| **Disease Progression Classification (Longitudinal)** |  |  |  |  |  |
| MS-CXR-T | Macro Accuracy | 59.0 | 61.11 | 65.7 | 50.1 |
| **Visual question answering** |  |  |  |  |  |
| SLAKE (radiology) | Tokenized F1 | 40.2 | 72.3 | 59.7\*\*\*\* | 70.3 |
|  | Accuracy (on closed subset) | 62.0 | 87.6 | 82.8 | 85.9 |
| VQA-RAD\*\*\* (radiology)   | Tokenized F1  | 33.6 | 49.9 | 48.1 | 46.7 |
|  | Accuracy (on closed subset) | 42.1 | 69.1 | 70.2 | 67.1 |
| **Region of interest detection** |  |  |  |  |  |
| Chest ImaGenome: Anatomy bounding box detection | Intersection over union | 5.7 | 3.1 | 38.0 | 16.0 |
| **Multimodal medical knowledge and reasoning** |  |  |  |  |  |
| MedXpertQA (text \+ multimodal questions) | Accuracy | 16.4 | 18.8 | 20.9 | 26.8 |

\* Internal datasets. CT Dataset 1 and MRI Dataset 1 are described below \-- for
evaluation, perfectly balanced samples were drawn per condition. US-DermMCQA is
described in [Liu et al. (2020, Nature
medicine)](https://www.nature.com/articles/s41591-020-0842-3), presented as a
4-way MCQ per example for skin condition classification. PathMCQA is based on
multiple datasets, presented as 3-9 way MCQ per example for identification,
grading, and subtype for breast, cervical, and prostate cancer. WSI-Path is a
dataset of deidentified H\&E WSIs and associated final diagnosis text from
original pathology reports, comprising single WSI examples and previously
described in [Ahmed et al. (2024, arXiv)](https://arxiv.org/pdf/2406.19578).
EyePACS is a dataset of fundus images with classification labels based on
5-level diabetic retinopathy severity (None, Mild, Moderate, Severe,
Proliferative). A subset of these datasets are described in more detail in the
[MedGemma Technical Report](https://arxiv.org/abs/2507.05201).

\*\* Based on radiologist adjudicated labels, described in [Yang (2024,
arXiv)](https://arxiv.org/pdf/2405.03162) Section A.1.1.

\*\*\* Based on "balanced split," described in [Yang (2024,
arXiv)](https://arxiv.org/pdf/2405.03162).

\*\*\*\* While MedGemma 1.5 4B exhibits strong radiology interpretation
capabilities, it was less optimized for the SLAKE Q\&A format compared to
MedGemma 1 4B. Fine-tuning on SLAKE may improve results.

#### Chest X-ray report generation

MedGemma chest X-ray (CXR) report generation performance was evaluated on
[MIMIC-CXR](https://physionet.org/content/mimic-cxr/2.1.0/) using the [RadGraph
F1 metric](https://arxiv.org/abs/2106.14463). We compare MedGemma 1.5 4B against
a fine-tuned version of MedGemma 1 4B, and the MedGemma 1 27B base model.

| Task / Dataset | Metric | MedGemma 1 4B (tuned for CXR) | MedGemma 1.5 4B | MedGemma 1 27B |
| :---- | :---- | :---- | :---- | :---- |
| **Chest X-ray report generation** |  |  |  |  |
| MIMIC CXR \- RadGraph F1 |  | 30.3 | 27.2 | 27.0 |

#### Text evaluations

MedGemma 1.5 4B was evaluated across a range of text-only benchmarks for medical
knowledge and reasoning. Existing results for MedGemma 1 variants and Gemma 3
are shown for comparison.

| Dataset | Gemma 3 4B | MedGemma 1 4B | MedGemma 1.5 4B | MedGemma 1 27B |
| :---- | :---- | :---- | :---- | :---- |
| MedQA (4-op) | 50.7 | 64.4 | 69.1 | 85.3 |
| MedMCQA | 45.4 | 55.7{
  "<image_soft_token>": 262144
}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          ez‚>Ú¯‚>É’>‰">√Ïó=T"•=Îà¨=œ3>lmh>˘ƒ>C>>!∆x=cÖ†=ŒNö=dGö==xô=˛iô=£ëô=‰ö=ú=§:ú=¿ö=^ˇò=2ô=ªø§=ñ-∂=¨™=Äoí=™)Ç=”,Ò=≠jÉ>¥Pï>4—ù>…˝å>∆ä>vlâ>˙´É>™˜Ö>Uà>ÔÊã>„ô>¢F≤>.Àë>À¯™>K∫> &π>TΩ≠>[1©>x¡â>˛Ök>Ñ>)eï>ûÿ´>-¶´>Á¶>‰â•>q|¨>È≥>EΩ>^«>¨i¡>âG∑>{Æ>r·¶>ÃÄØ>X¡ƒ>à”>‚–>ì6π>fú>‚∆}>9òc>ƒJh>2Ñ>¯ë>Ÿû>êb¶> \¨>U‡±>“[∏>ãº>ó2“>oD⁄>œ˙Ã>0‘>úµ?∑ˇ>¨‰⁄>ê˜ï>8ΩÑ>ÇÒe>;‚>>RK&>ù&>
°>Ã7>∫®æ=}Ëƒ=ﬁ∂:>˚ûn>í¶|>D]Ç>·	Ü>*”â>dé>vYç>£:ã>^ o>≠ˆS>–;>O”E>ˇ%V>&]i>πÅ>∆sÑ> °z>Z“m>Õm>©U|>"è>ö>Ääç>ãˇÅ>ºìr>°r>◊˛_>üWj>FgÑ>πœY>+Ÿ1>◊>+>R>Ïãl>ø\o>ÏZl>h>·Üa>»™h>ﬁ	|>Áã>›Äú>o>π…:>Œô=\_ò=¥©ô=∏gô=ﬂhô=<qô=.pô=„oô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=¨oô=sô=rô=∆ó=ê·ï=asò=%Vú=Ù˜†=¯"™=’”‰=8ô6>1“o>ºª>®¢∫>≥◊ù>¥ã>ç'é>ﬂeè>Hè>£"ä>† Ö>˙"Ö>®˘å>?úó>‚íù>Î™>¨∞>Àu≥>∆‘∂>“d∑>°‡≥>\æØ>c¨>öÁ®>≥ß>ﬂ¶á>-J>.>ÆZ.>ˆWé>˛vô>â•>Ï∞>íÌ∂>]i∑>4©«>ù%†>uˇç>¡u>…ÑK>Ò9>Wº&>c¶ß=¨†=ÇR™=óàﬂ=¸˘≥>xΩ∑>Ω∞>cç>Æâ¡>ÿ"ﬂ>fÄˆ>√ ƒ>,?t?ÌÇ?rb›>|	Ã>%æ>ÉLö>ÔÑ>à§>j¯ƒ>l >2»…>!É≥>ÂÇñ>Fì>π!9>´¬D>îck>¶bq>ejÇ>'Oç>äóâ>h˚_>äEõ=è°=≥o≈>2˛Î>ÍœÍ>&[Ò>sÔ>u8€>#©”>I(ˇ>¢?£ÖL>ê∂ö=bùö=1p™=VUü>£” >ùŒ>⁄râ>ö>Mbé='Íö=üô=√lô=Úwô=g·ô=‚ûö=∑˙ô=t/î=˘¨ê=˛Bï=áò=Ò–ö=`én=†–#>ëÃ=>,w*>[Z/>√OT>Ø_> ˇs>Yπâ>â¢ç>¸LÜ>¿Ö>œOë>Nö>ó§ü>öß>§o√>Ÿæ?>íF>yBs>Y¶ç>,•ñ>…´>øáò>,ˇà>uç>Fıñ>Ïrπ>°óª>_ß≠>@Å¶>eK¶>.9¨>gˆ≥>,„ƒ>+ﬁ¿><Uß>ˇÚü>NVò>*¢>D¥>„∫>÷„Ø>©íô>ú|>OZ>ö´m>lÆ}>üÏÖ>Aêä>gë>†ﬁú>›®>"O≥>†~º>g¿>¯ë€>⁄*˜>úl?1¡?i)?Be˘>‰’>K3à>-6>ƒM>Ωä7>-.>K*>ç>EM>ØµÈ=uÁ=¯Ì;>˛"K>Uh>ÍÏz>Ñ÷É>[™á>b'ä>èºã>`ﬂÜ>cªÅ>L4d>ŸpG>zOL>:ƒW>‚lf>í[ä>Åûè>rÎé>/çÅ>>[>†‚R>qa>≠rp>’@y>ÜÄ>∏Å>A`_>˜R>%iU>„˜\>[wH>0x(>‘ü>cÂ>€eR>f√Ä>Æ{É>F>Ç> ·~>{~>ÚÇ>¸¬ç>>ç†>…ù>sΩG>*§>¢î=≥óô=T•ò=∫Äô=Ωvô=(oô=„oô=ıoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=Ôoô=Ëoô=>pô=Dkô=œ•ô=Dﬂô=cò=e0ï=z#ò=9Aî=Z2á=âú}=ŸW
>	Ñ>sÎß>$Ω•>ˆ~ê>µâ>.lÄ>‹Ñ>Åzå>&ç>—Då>Ù±é>V_ñ>æH°>¨>EË∑>Uº>¢π∫>,C∑>ÚÂÆ>øP¢>≤}ñ>™Kç>˚ÆÖ>ˆªÜ>Ïä> ”ã>‰ã>(≥è>HYó>c°>˘±Æ>{€Ω>]U¡>Ó˙ƒ>7%«> ®÷>¢ª>ﬂˇµ>uºº>äÉÆ>Q€æ=~®§=ç)Ÿ=Ç´%>ÇµÈ>~¢÷>’*€>Dπ>‡Ωﬁ>æ‘>¢+⁄>Ù¶¿>°æø>ñÿÂ>4¯¸>ıë⁄>}(…>eÄ∂>•–Ç>+n>¨jè>çª>™º >˚∆>†e¨>8÷ï>ZÜ>¨*ﬂ=‚ù…=V‘Î=∂®Ë=\	>y±%>~34>z#>∏≤=˝ç=	èz>,Ωπ>CmÏ>æÿÚ>∑Û>8ö‚>. ›>öjÍ>»∏Ú>Ly•>\Áê>–à>0`o>Ìª>U^Ã>˘ß >/ÿ‘>!®µ>O`ß=ì9ê=ÁŒñ=¡Dô=ÓÉô=Ùëï=…fã=iïê=9t˝=->;W«=bU≤=≠I€=õà˙=€Ó7>&ÕG>MN>&zI>ŸõH>fP>∆BS>¢ç>@∞ö>j÷Ö>0 Ç>ö8ò>„°>≥Oü>Ôdû>Ù±>f–â>–rÜ>Ìeé>~‹ô>Êû>˘˘ü>''•>á9®>E^†>EÎ™>¡ŒÀ>∂¡Œ>ë'¥>[∏ß>ã‚†>£Àü>¶µ®>œ~±>B8Ø>˛ô¢>y·¢>/∏§>1Ì≤>ˆÄπ>·º°>îÅ>PG®>Cà>f∞d>TÉ>fuã>hìê> ÷ñ>›!õ>¿7§>$ Æ>"À∏>∆∫¬>¸÷>â˘?Bö?Û?Ê?l$?hm¯>Î”±>í|k>G•k>◊Ê?>}®4>ÍÇ=>£%>XN>>ú>"”>>>‘é<>±·N>nfd>ú}v>%ÉÄ>∏Ä>Ø©{>Açw>õ:x>£‹n>∏&S>®U>±\s>qy{>	ÁÅ>èÎu>„ÀÄ>≠€~>Hp_>…j^> n>‡s>¥"s>œÚÅ>¥˙É>π≤~>àí>Ï∫x>ÓHt>√8u>…Jh>ÍµU>¿{Y>Äíb>Ékg>y≠j>e¶n>C∫b>ò\>ä∞p>{á>¢7π>˝µ>‚¢>Hñ>u@I>NHú=Q˛ú=G?ô==aô='pô=≠oô=pô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=Ïoô=pô=#nô=âô=QÔô=ƒ'ö=Ìãü=Æ=)·=fÛ>+Ê8>ï\_>Í]Ñ>ôbß>‡A®>B√ï>ò£Å>9Œo>Ìs>P≈ì>ƒ¶>õ9ß>!k¶>0!§>ü∞•>äF°>Ωô§>àÚ¥>â.ª>,U¥>ƒ—∞>Øá≠>⁄r©>ÿÊõ>Ræâ>Ë¡{>≠x>.€Å>÷èá>ìæç>V˜ï>(£>j+Ø>r¥Æ>;®©>>É©>,¶>”¢¶> û´>ßW¶>bÍù>≠LØ>	\Ø>œ∏
>« >„ñ>ò˝N>„BÌ>à¡>¥ˆ>WË>∫!ﬁ>≠ˇ∫>·…>T‘> ›´>8Ç«>ö≤‚>,sŸ>Wkœ>ëŒ>0É∂>=…ù>πé>ìù>ofÆ>D!∂>9s£>¯Ü>Âçd>=„Ó=≈ŸÏ=ü˘>vM	>7>&x9>∏ìX>vvc>j$M>Ñÿï=%P=¸Ô{>VoÏ>†ﬁÒ>9#Ê>Î5∆>$u¡>k”>π’›>ßt·>ê’>Cœ“>ä‘”>‡H¿>J™õ>éÔ©>{,“>nJ◊>˝Â‘=óó=£sÜ=ÃÙô=˘.ó=√€´=†«ª=.õ=+~>Åºô>v9_>K<D>é^=>S˝<> w:>{6>o6<>ÌkC>w	@>∫t@>⁄¸K>∏wv>zã>ÍrÖ>F™ê>©ß¢>‡ö>K1é>ftí>ß(§>òØ>F'≈>]çƒ>‡-…>ßø>Ç&ª>è∑>RÜ¡>{º>Ò-…>=’>ˇ.€>[¿>‚ò•>Ébõ>Óåó>¶œ≤>g >o–>$b–>°wæ>Ô«œ>6dÿ>ƒv>Ö…˚>º§“>åb∏>1≥Æ>¢|°>
sç>¥kü>±?¨>}’¢>tõß>Mr¥>“Pπ>1vª>ëÑÕ>ËÔ>Á≥?˘?õª?–`?à»?ÌÈ>”Â∂>>¢w> Z>W@I>y˜@>lt8>‚2>py	>ây>3>6Ù>>‚7>°9>>7¯>>9J>…H[>ﬂƒm>§≈u>O°s>ÛJl>ƒe>ŸF`>ÊƒU>\ÎO>8W>èlP>ü?H>+K>ß¨[>,r>Â´x>b˙Ç>≤å>yç>““Ü>ÃÉ>NÂá>ZÖ>ÀÓÉ>¯¬Ç>∞aÅ>´H{>π˝p>ë“c>¿zR>Æ6z>ƒ+é>9°Ü> `Ü>ŸVa>¨¶K>S√^>Y>Âùõ>Á◊∆>'g€>¨•‰>+˝∑>F#>(¶å=Õ^ö=î“ô=©iô=pô=Îoô=Úoô=Òoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=≈pô=`rô=á^ô=‘˙ò=™ó=ƒ7ï=Úwr=πÇ=§Ù=Y∂L>(·Ω>g≤?™˘Ù>L"€>F≤>q4ì><WÖ>ÿíy>@Øg>JVö>g™>â∞™>Ó˝©>{c•>ﬂ‘ü>Ωàò>’vô>¬¥¢>˛˚≠>∞¸¥>€Ì∑>!∑∂>Ø> N•>4qñ>MÜ>Ké}>ÃÏÖ>´÷è>?†î>À®>ú√>löŒ>_≈>_ú±>Ì©¢>Tù>§]ç>Z√m>\©k>„–Ñ>Ü∑ç>Œjñ>GÑ>ºÏê>¡=ò>úÆ>ƒ>µÜä>∑™>¯oŸ>•Ø∫>FW≥>ä9≥>¥æ>›z√>DÊƒ>øÏ‘>;Mÿ>øﬁ”>…±“>!‚>Âa◊>ê¥>≥;ï>6ã>GÇî>4Uû>r>®‘A>YF’=û¯Ÿ=*˘=î˘˛=7Œ>pAQ>∫_§>¨¯±>¢>éÒå=‰^®=,ﬂ->í˛á>7;≥>©G∫>Î·ü>%Hö>…Kπ>N…€>Y˝÷>µ‘>…◊>y≤¡>Ù<ñ>‡€ø>≤©> ‘¨>‡ Ω>tÁØ>i©û>°s>uYù=>πî=@‰L> G≠>Ãsî>C%ù>Ewì>æz|>7j>CìL>_6>P$7>s˙1>Ñ9>b[O>Ω=>ë©1>˜ó?>;ÿW>≠÷v>“è>Sk§>ÙÆ¶>˘£î>€á>â˜ä> _ñ>|}ß>^Z«>&∑—>Å2Õ>ƒ·π>ÂiØ>Z¿>;ƒº>Ü„ >ÂC◊>∫«–>/—>#◊√>π’∫>·ê±>!§¥>≥°>›¥ò>∆~∏>é‰¥>ÒÙ=Ì5>9ÊU>ùõ>w√>•í∏>∂ç>àq>%˘L>Œ;0>∞≥\>N≥î>7n>É˙=â[+>ãZY>¥~>Igü>ßÎ◊>Xe>≈?§4 ?KgÌ>0Îﬂ>à‚Ÿ>»©’>J©>ñWz>Ej>=v]>q4<>)%1>Àûˆ=ƒÚ=#I>Ï‹->[:>h“:>T3;> 6=>∑:D>/∑X>'^m>ﬁtu>Óëp>ˆHX>%W>îS>∂DQ>¬ÑM>ªL>à‡D>±K>ﬂM>)BS>'l>dä>~Úî>«‘û>l4•>⁄•>≈õ>âç>"â>‘Zå>¡ä>ÅŒ~>Téh>™-\>sÊS>bì>ûÃ´>u	ó>>tÇ>,&Y>sS>Q%â>4QÄ>'Ts>ˇr>qÀÇ>yﬁ§>ÄmŒ>t⁄√>9qÖ=Ì@ö=å,ò=õÜô=-pô=Êoô=Ùoô=oô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=ooô=ckô=Ãïô=ö=r¶ò=Â„ø=‡∑7>|jW>f=ó>&n≤>DﬁÃ>-∑Á>ôz«>q±>-åï>úòí>ÂBë>ò@ç>ÓTX>é]ñ>:Øñ>ftú>¯R¶>kJü>aEó>tNî>lÂñ>á[§>dY∞>˙π>‚æ>‰xº>ŒE¥>‘±>ÚQ£>ìäê>˜É>Gé>xö>«Äù>ÕØ´>6˝Ã>fÔÔ>nb¯>†˚>‹ﬁ>Øç»>”Dπ>˚≈¶>wÃû>ù®>‚J´>;ï>
_Ö>aÓä>ã'â>‰í> <ë>3-_>ße>iuú>ù∞º>O∂∞>;Çß>ÿ∞>óV√>ÁÊ¬>◊∆>Ï∞‘>E
◊>˙|ÿ>√ä‰>*›>ŸtŒ>û¢∑>"û>Q ê>⁄Œè>#<à>Æ[>t">∆>'>ã ">™ë>á˛!>„ÊM>Hƒì>àáó>p8>Zâ=Å·ù=“}Z=äMy<üD>£Éõ>‹ﬁñ> ì>©»¢>Ç9æ>Æ»>_Õ>˛√ >ï¶>â5õ>FP⁄> ?≥>Åèô>º∞>‘;Ã>^ÿ⁄>ÅT≤>§∏®=:*x=•c>•∞Ω>Ä∆æ>€¶¨>∆¨ì>⁄>É>s>oÉW>æ@=>&	5>îŸ1>i±->Ä∞4>÷Î->àí(>µu0>±hd>†ÖÖ>∫î>∫˘ò>êÓè>Ôä>˚XÉ>…_Ä>cià>cù>Û7Æ>Ë°¿>$≈>ê> >ÚéÃ>«g√>k±>’…ú>˘Ñò>∆å>\hù>s[©>‘8|>Uç>K™>
ª∂=Í=ﬂ¸>=«ÑÖ=àyd=Y∏;=èy1=Í=^ü%=˜NÅ=\ôÑ=¥LW=`u2=^c=Œ‚g=·«Å={øå=⁄Xp=v‚M=À?=YçC=Q-'=∫cn>Î©>#Wÿ>ùÁ>$”Â>Ïeﬂ>a+‰>h\‚>ŸŸÿ>ÜV∞>ö≤ã>‘3{>¥WÑ>ÛÇ>à¬I>…â(>Å5>j9=>#¢8>mΩ2>ùz3>,¨6> ßB>Æg>nˆÉ>l Ü>Ÿ(Ç>(wb>ÇX>Ÿ∞Y>ı\>Á^>ö˚^>%‘K>ÇgI>6W>|«a>œÉp>a7ä>©Oú>ΩŒ≠>≤à¿>ƒ«>›áπ>Yh™>%÷£>√ûú>ßâ>‰q>Î‹f>œ{_>OÜU>’ôj>rå>ÈãÉ>å)^>=-h>¿◊Ä>§Ωã>”∂ë>#Ÿã>±¨t>âZÜ>I≠>è¢÷>˜>>ø†>sü=Ê’ö=ÀIô=ïkô=qô=Ïoô=Òoô=Úoô=Úoô=Úoô=Úoô=Úoô=Úoô=%Qô=íPô=4¢ö=πô=ü-ä=xdÆ=ú¨@>Èòº>çÄ?ÔÁ?A:ı>ﬁ%›>Ç∂Ω>∑A´>[â>p—u>ˆ≤à>∆ñ>r>VÎç>`î>"pí>‘6õ>""ò>Œì>öXê>Ê·ì>r[¢>e±>«
¡>ª≈>£zø>4mª>„=¥>Ãhü>©Äê>∞3á>Fë>Ê‡ù>Ìü>øﬁ¢>ò:Ω>é˙>˝‡?±“?›»?SS˚>i‚Á>,€÷>ÿ«>>ÙŒ>È3ÿ>Óœ>¸B±>ìì>◊®á>—}>ÌÕd>øa>j>o>á>,∂¶>J æ>1Æ>o∏¶>ü¿∫>bºπ>(rª>òË—>=©’>vŸ>#⁄>UÇ”>”>´¡◊>⁄ç’>~‹û>†≥É>èÑ>upÅ>¿~x>Ùâv> Nm>ÆÙh>£òe>c;w>≠¨ñ>ﬂH>·iU>38¬=º≠ì=âü=‡£ö=Õc>¡Fc>@åô>Í"ó>G[ú>ù†>æª©>‡≥>Îs¥>‹éΩ>Zµ>H∞Ø>u®>,’´>xùª>§r≈>v&ƒ>ê∏>™Uî>£Qz>`©ö>‚œ±>OÙ™>Åg†>7Wê>Yá>12Ä>ü±V>98>]-4>∏*2>=ˇ.>õÓ(>È=(>π *>‡n:>~áj>!yÄ>´à>Eä>ù»}>>w8z>ö⁄q>Wë{>ø†ã>†7î>4◊°>h¬∞>pí∫>€≈>Æ,Æ>Úbô>q4≈=˜œ”=)®Õ=§Äı=j´>ﬂŸô=ne∂=õÊ=yT≤=úSß=%|°=d¥ô=€=£=%Qß=ç ß=>´=%•=ÆÃô=¿û=∏ì§=']ß=Å˚°=e5†= ºö=Îú=të°=_•=#¶=˛«£=6æö=¶Z™=á°^>ˇBı>>QÛ>ÿ‘˜>M&¸>Á ?ÿ¶Ù>†‰>mq¥>lœö>Ü§ì>ñ>˛°ô>	Z~>◊;>¥ë6>"´;>Ê§5>ö},>›ñ+>Ö76>eóG>◊s>ƒhå>hüç>™/â>Ñ÷>ıc>@e>úÄj>Ü∏o>ØÚn>î_>Ù®Z>X∑k>eÛm>Q#w>Ûöà>ü°>èTµ>‘∆√>“√√>iõ∫>?¿π>i¥≤>Æ ¢>WSà>ùn>ì∏b>=`>_>Y>p˝S>†5a>Qh>¬vi>Eƒs>ø;Ñ>Sã>ÉÉ>®ds>) >Vô>q!≈>}ãˆ>≈˜?†∆?R&>d†ù=Ñwô=4Öô=kô=*pô=‰oô=Úoô=Ûoô=Úoô=Úoô=Úoô=Úoô=aô=*Wò=‘Õ°=∆Ÿ®=p @> ù>∫∆é>I˝¥>µ’Ê>ãÿÂ>√è⁄>…¬Õ>%˝ƒ>/–¥>¬bó>à)d>„Mt>≤|ë>:^á>ﬁBÅ>≤vú>éËô>[–ó>Ã‡î>(ë>Ÿå>[bí>B¢>Ã∂>ëÒ«>R
»>t•¿>úiº>«uÆ>÷˝ú>zΩô>Tì>A¶Å>]—ì>Ìgü>iF£>ò=¬>•K?∂o?ãµ?ÔP?¥0Î>g^‰>á·> ‚‘>®◊>ï-÷>È÷>÷Ë>£ß >¨Ïê>;à>6PÑ>›Z>
%k>-k>z^Ä>åò§>•ã√>æ¬≤>§à∞>»>¿|–>L9…>!à’>_U›><X‚>›>êøﬁ>≥±’>»∆ >mó>ŸùÄ>îÓ{>|ˆ~>Q/z>â˚o>Ë#`>I$W>às>•{>î>„µà>\>•>Ùs>æ√?>T˘	>ºõ=√éÄ=œtΩ=“Ë>À1ù>ﬂîß>®V¶>¶˚û>f¸≤>ÃÍ∆>•t◊>º◊>ZU–>≥»>G ¬>˜Vø>J£æ>Áw≥>∞≤>õ)≤>J2≠>z{≥>àö≥>I±©>|Ãû>:Õì>ä>h≠z>lœT>‚'B>†<>ﬁ-=>!o=>3ƒ5>Ùÿ2>ZµE>"ëT>/Ë^>aÄh>kev>|>èNn>Br>»ˆq>iÅq>â´~>Ímã>Oå>ãê>à…ñ>sª†>ã∫™>´¥û>^⁄Ä>ëÄã=òï=^ï=Sâî=Oì=Âô=›5ñ=Yë=$‹ñ=ı⁄ó=¸ãò=Êñô=tDò=_–ó=´Ãó=Ôuó=/-ò=Bóô=—ò=ü)ò=r‘ó=¶wò=±ò=Émô=˜ô=|~ò=Uò=
ò=E:ò=H3ò=:Çû=,Œ#>Næ¢>dõ?¥üˇ>Äà
??µ	?ö*‰>J›ß>¯πõ>√ô>Ùô>´\ô>∆mÜ>¯7H>Gò7>öî;>èú:>©–&>–r)>Mı9>S´J>[Ãb>‰„p>ò+~>NœÉ>ˇmÑ>jÌt>¥âv>N¢~>=dÇ>UœÄ>Hx>'æy>Ω(É>gjÉ>©@Ö>æüä>Æ¿†>¶∑>{â∆>a∫√>ŒÇÆ>?§>ªú>4Ïç>»ÀÄ>[m>2Ea>∆≈f>¥Ñ]>-T>D^>(#r>≠åy>µBÖ>˙*é>òÜ>[√[>ƒóX>‘≤á>∆öµ>Q}Ì>Œº?K«?m’Ó> b>4ÕÜ=¬Qõ=+»ô=WVô=Qnô=1qô=Ëoô=Ëoô=Úoô=Úoô=Úoô=Úoô=◊Ìñ=å\ï=4>ƒ=qˇÛ=Dü‘>∑è >õ6ÿ>ÕD‰>´·÷>÷Ú >VëÕ>∫‘>*”> …«>
Ø>3,É>kñT>ÒUÅ>Õ9Ä>vÔÜ>[ò>*Gú>b¥ì>⁄jí>¨é>‚
â>Ì(ë>6Y•>≠∫>º …>e∑À>ìÒ«>swΩ>jØ>èú>ÁqÉ>¨¿u>,ÍO>’óã>È§>'âΩ>UÔ>æT?¯˝?ê–	?ä0€>JTæ>C∞ >¸±–>™uŒ>Z[–>‹§≈>\≈º>°œ⁄>,‰>˘3ë>ßt>NÊt>5GÅ>Rkv>èca>µˇk>¨»ã>Q•>•Vπ>9÷π>‹à»>@’>B—>E∫Œ>†ƒÕ>´#‚>sE‰>=‚>“≈◊>Ÿ >ÈUà>¸Ÿy>èÄ>êˆÉ>ˆã>Â∑~>
d>Ia>´Ö>E∂x>èBp>wÄÄ>â≤ã>=lò>t˝ó>/ìk>E˜b=ê>PÊ>Ÿ7Á=v¯¢>{¶>˙ö>˙Ì£>Ùü«>ı"Ÿ>£Ç◊>ÈÚ‘>ê—>˘S…>yø>œ1≥>·
±>˙ú>±;ñ>f¶ô>9P°>X≠>[¸≠>ñÕ•>Ølù>∞ûì>°øÖ>Amo>,â`>ú˜V>S‘O>"BO>°_Q>}I>ÿnO>Ùcr>◊eo>˚%`>äµj>Nbv>ª.p>õ¡W>®Çh>ã>p>"Ës>ÅxÇ>{Bå>ØYÖ>—Ö>ÑÖâ>K∆î>8+ö>oë>µŒQ>+!é=ˇïò=ªRó=∆…ó=i^ô=Ô¡ó=‚Rñ=:Yï=…8ô=◊¸ò=†îô=Âüô=›ô=¸ò=[Ïò=d“ò=‚[ô=¨ô=@.ô=8Óò=rô=€"ô=¢Sô=†ô=+1ô=1ô=—˙ò=µ˝ò=ÑCô=Ï„ô=q≤ï=›j=xp=RØ?+W?T ?^i?∑?˝Ç?¸◊>É?Ø>{™ñ>c[ò>T°ú> ˝é>&ˇi>
'K>Õ≥H>ˆ9>/”)>qV4>“ø>>±ÚC>ˇU>_∫]>8°o>€-x>ˆ√~>#óÄ>`^É>—ÌÜ>Gâ>º∞á>„ÌÖ>PöÖ>”RÜ>¶∆á>¶0ç>”œè>}†>ºDº>å;…>ˆóæ>À/®>Y€ï>4±ã>ÉØÜ>é’>sÓl>SYg>IBh>ÂX>;-L>;U>¸ˇz>=Ëà>dÙì>D±ú>f¥è>,]h>¸¿q>Ø,ö>f›>MH?S◊
?4¡“>w≈¬> ˙∑>vV©=d=ò=Pô=∏áô=‘pô=%oô=¸oô=Úoô=Úoô=Úoô=Úoô=Úoô=Å"î=ãWä=ıP>ÍÑ>ÏÓ±>Và›>	ë˘>STÂ>/dÕ>çoΩ>2ñ—>ºô◊>ƒµ–>›"Ã>ÅWø> $°>Ø‡o>œf>ˇîÇ>éøá>?ó>Bö>-Dê>ıç>y5á>’∏Ç>≠ä>‡ÿ†>?Mµ>≠æ>w#¡>QIπ>KEØ>ç]®>W7á>A><>ÃR>)è>◊L≤>Äa‚>s:?¿X?ÏÈ>…Îø> ˘Ø>˚˙≥>çÅ∏>ú8∑>*∏¡>în≈>7¬>˚y¬>RÛ€>ü_∏>∆ºZ>*JU>õX>†p>ñœÇ>b•É>£rz>ïá>Ù·ç>KÂë>\ñ¢>B±>M¿>X7◊>o⁄>Ω{Ã>÷°√>E3≈>≤"≈>w{ò>G@ê>¶O∑>˝•>ª2°>úö>⁄ßñ>èä>√ÅÄ>/2x>>ro>Ú"t>∆#w>[Å>¸Wé>‡Úç>oã>%§{>c(>°x≤>˜–>∫∂>≤Àù>B<ú>Q¶>ÒJ∂>ƒÅÀ>óÙ“>∂D…>òæƒ>Äæ>”C∆>8Œ≤>‘=ú>«¢>-cû>—áî>Xí>$fù>üF£>~}û>›éõ>˘:ñ>¶ìé>ÓÜ>«z>~•q>Ì∏l>Ÿ≠f>0d>÷Ïa>†Ë]>sq>∞{>∏ro>Öl>»îu>KbÅ>!”~>A'k>¥◊p>¿r>Õ˙j>»Èi>BTn>Gci>˙™k>æ»i>îÃt>“æÇ>bhà>kp2>ÊÖ=±õ=N5ö=Õfö=máô=ÆQö=Ω&õ=dØõ=°§ô=Oƒô=73ô=¡ô=ûdô=àô=_∏ô=~Âô= qô=7ô=Ô}ô=ï®ô=PÆô=Á°ô=HÅô=	Sô=`íô=èßô=˜∑ô=&∂ô=Vãô=¡gô=wö=º~™=Äœÿ=Yx>7§>0ú?ﬂÊ?ä™?ÿˆ?wÈ
?äπÀ>"7¶>\´>ﬁÎ™>Œˇõ>GÄ>HWg>÷e>=1Y>çy[>Ç3V>HII>Œ¡A>DÁG>{ÄW>0ôq>a˝}>√Ä>†ÈÅ>¢=Ü>!sà>VŸâ>ª"ä>ÃÊä>Y7ä>Y§ã>"√ç>Xñ>§û>3w©>Æ∑>˘∏>V.≠>ˆP†>≥ê>Åäà>ÈÉ>l?{>sˆo>8bc>à‡X>uU>öT>S.f>∂É>∆¿è>rü>	n¨>b±>ºù>Äˆñ>–ò©>>≠⁄>bL ?Í≥‚>Zº¨>°Äó>•x©>¨6>J å=¢…ô=ıXô=goô=êpô=Áoô=ıoô=Úoô=Úoô=Úoô=Úoô=dJö=[ô=S…Ã=÷Tô>oJæ>Ê∞‹>‘Ê>«$€>}˚Ω>o·µ>˘fÀ>Ã‡œ>ﬂ@Ã>wŒ>†£ö>‹>ç>„…î>Œär>±~î>7Ωì>4W£>ñªö>¨dç>€Rà>˚‰É>[5}>¢¡|>Ó î>H¥™>√õ≤>“ù≤>%e¶>ê\ñ>?Ñ>à–\>àŒH>ÀyK>úüv>¸àñ>Õªæ>àù‡>$ÿ€>Ã–ª>ªÓú>Áßï>ÀÜ£>√ƒß>´Ó£> 'Æ>&ÿ>r|÷>§ìæ>®ç¿>∂ª>Èeë>Ìµb>üÉ>õÅi>ãır>n$ï>-‹°>Î|ñ>≠)ç><Âä>Ôèá>x-á>m+å>uÏô>ÔÁÆ>c—>˝Ñ—>Ã…>èÁπ>∆Î†>¡|Ñ>ÕÏÄ>Àúö>ze®>‡¢>˜◊ç>Qü{>ñ—Å>ﬁà>∑€£>¡Fö>:å>AóÉ>Êπk>ˆãn>ﬂà>¸@ì>H–ã>C¯í>f/ù>DÆ>§¨>qÃ•> ïß>[Ç©>ØS∂>IQø>3"≥>æ§>"¢õ>ãÚë>PMù>˛Íà>9Ö>Enè>9 ò>ûö>≤Pë>Å`í>Ä‚î>d®ñ>:0î>k•á>E2É>¥¶Ö>>«Ñ>eGÇ>àTÇ>¿>ôtz>–Rq>∫4n>á‰z>dx>6Üx>•\z>$Ø~>»ÍÖ>nµâ>®áÜ>Ä°~>å˝p>û>d>◊^>√%m>ù?g>^>Ãì[>(Jj>o`Ä>AfÄ>—3>ûÀ=*;ö=©1ô=∫ô=XDô=Åô=/–ò=jÀò=úyô=Ãô=ßô=Fô=˚ô=}7ô=mgô=H6ô=dGô=‰Mô=!Hô=(Eô=…iô=Õgô=Ωiô=toô=6aô=ﬁcô=aô=Øaô=Wkô=ø_ô=?ãô=<£ñ=	£y=¿™
=g$>Û≈È>3º¯>Dø
?ïÂ?xÍ?UøÃ>qæ>}ä»>Yy∂>˘óü>ƒàñ>ŸRõ>1≠ù>c∑ü>b<ù>ElÜ>£`>âUC>#öC>i§_>èçt>û⁄É>ÎÂÉ>ÅKÇ>ÙÄÜ>C?à>Ää>_⁄ã>‘ã>úyå>RMë> ô>˚W£>M~¨>˙A≤>A≠©>2Fü>»ó>Ë$à>ª]y>±>s>ﬁÓo>hp>Ò∫k>?3Z>⁄ÇQ>>»S>ãê`>0:y>!sã>bZñ>uM§>©mÆ>HÕæ>œú¿>e%Æ>T2∑>t’>rjÿ>ö£®>æWÑ>˙[k>"ôÜ>Õ¥>Ã«ç=ªÉô=¨bô=8kô=Ωrô=‡oô=◊oô=Ùoô=Úoô=Úoô=Úoô=≤∏ò=‚5ú=ÖÜ=	<Ö>•ë>ux≠>9Dº>JÈ√>è!∑>	k≠>≠„∑>áÑ∫>\Û¡>JKƒ>=Ç>vÜ>¥+•>”‘ã>êËå>*†>`¸¨>øàß>˚Êè>°ÒÅ>:ÃÉ>¡PÅ>ªŒx>#6ã>ûK£>∫¶>Êö> ã>cΩr>lê\>xM>çNM>CÄb>˙}~>%dó>‚™∫>/Ë»>œ∂>ú‘û>ä®é>¡^é>õØú>7‘ú>ò„ö>8§ü>˙x¡>"o¡>ô¥¨>G˘¨>Wdü>Så>dô}>E^à>”Ìq>û ä>^≈´>‹T´>ªß>Ô˚ß>ÿóû>üì>ÊÜ>P\Ç>Ÿá>øûu>™+¶>´∆ƒ>Ìƒ>5y∏>y™>®í>~tt>·‘c>-Ñ>£∑Ç>©èz>ΩÉr>pÍm>=Ö>O¨ú>ãvú>©«ß>⁄πé>«ƒq>„;e>?qÑ>êç>Ì‘}>@ÇÉ>5aú>kå¨>@g≤>˘!¨>(Óñ>¬õà>“Tç>?/í>=Îê>k√ë>∆‹â>ëÉw>:s>∫õp>wc{>Ãy>?ÌÅ>Bè>ßJë>“ñí>°ã>Äã>ç>^úÄ>Óy>•ç~>_Ç>∆∏Ö>Ëà>wØÜ>˘æÇ>ú=x>&Dq>À˜u>˜~>%êÇ>y¨Ü>7·ã>ÎÔè>a˝ë>éié>rLÖ>âÚv>Åj>Õjd>ls>4˙n>N/s>KQÄ>GﬁÇ>ÍpÑ>∞s>/aa>q∫*>Åó=≤#õ=X–ö=lõ=‘ÿõ=Ò ú=Kãõ= πô=Mcú=û=Ôû=‰0ù=øΩõ=Áô=ô‘ö=‚>õ=8fõ=©õ='¿ö=;Hô=∞Yô=›îô=Iµô="¬ô=-xô=íqô=Mrô=Dpô=‚mô=ÒÑô=1≤ö='ò=^öñ=ãÅ4>UñÀ>WV€>sW‚>q˛>c˛>	'Ì>¬E÷>aÀ>“π>JjÆ>Îé∏>vºª>%¥>êc≠>Fl¶>˛xí>;o>\PQ>¬ÙM>ßl>
mÇ>ªkÜ>œ∫Ç>% Ä>•¶Ä>AπÅ>'OÉ>oÅÖ>öuá>sä>…∫î>%Nû>€ù•>Ä†≠>Í(±>°>>.à>∑†t>m÷a>“˜Y>ŒÿZ>⁄b>]j>˝ée>8¢]> œV>T>+va>8
|>ÜYê>\<ú><ù®>£C¥>x¿>/™≈>Œ]æ>myÕ>+2…>PJ©>Ö¢Ä>€¬c>ÉÓd>‘Õ|>Á!í>æÆ=øö=Cô=ooô=ﬁpô=Ôoô=Áoô=Úoô=Úoô=Úoô=Úoô=m•ó=}ìã=≠¥=så>t2y>D£É>Pì>f”¢>T°∞>b©±>®·Æ>⁄dÆ>E‹¥>ù$µ>5rå>æIñ>Hâ≠>õ¯ï>æêÇ>’wê>¯Æ>í¬>ê∂>$·Ü>îèw>â≤Ä>¿T>AàÉ>{ëì>Ç	Ö>N>dGN>‹EU>éP[> Y>vãW>a®j>mu>	®ã>W]ü>/oü>›âë>C)é>”Dã>T/ê>TÕò>5 ò>HÆó>NÁñ>ºFü>g˛§>']ü>ı§>ÿÄú>`ˆí>ÿkÜ>Ar>#x>Ó°>«ª®>|ü>wÌû>ÿˇ≥>X∫µ>	û£>Ó˝å> Ä>e-v>ää^>/Àp>|$ú>Ëü>`î>˘ä>Ï¬z>=]>7G>°K2>≠'>À«,>Ü¸o>‡æä>ÜÛÉ>!fÅ>¯~>ŒXó>Ÿ»ä>∑_n>\!b>ÑÅ>¡P>D≠~>‚¬Ü>Tì>A_™>T™>7ßö>∆ë>ñ=Ü>`∞Ñ>{	Ä>](Ç> ä>⁄CÑ>º≤w>w\p>Kπp>Úp>∏Ùh>Jk>ÇnÄ>¨xå>bë>{]ã>!âä>Fä> É>c˚>Øç}>˙<>=©Ü>+eå>1ä>‚±Ñ>Óëz>mp>M±u>Ë\É>
Øâ>Zî>õÄò>iÎó>˙Œö>…ò>HΩé>¬jÉ>Ãt>uÆh>&q>Gm>ë≥Å> ´å>$·â>Õä>q]|>£ìX>£h/>†PÆ=ıﬁê=é°è=]aè=)è=)Øè=Hî=Pïä=¬ƒÅ=ﬁ#Ä=ü◊Ñ=Èã=.,í=‰ë=©å=∏Ëé=—Aê=§Áí=˜ï=¡Tö=¡úô=Èò=¶Óó=K÷ó=ÀVô=2sô=#pô=‰oô=]oô=xsô=ÚÜô=
ƒò=™Nï=ecƒ=w#>fÉÿ>cÜ™> Áï>brï>íıÆ>ça®>M˙°>
Õ´>„w¡>¥B»>W‘∆>Ró∫>o¶±>È5§>I°í>ÓG|>ú,o>ÎXo>óÿÇ>N&â>ÇKà>MæÇ>.V~>Çˆz>uw>∑q>Ujr>∑¡É>`	ä>MOó>J`û>ÌΩ•>%™>u9¶>uYì>ËÙw>ÓÄ^>ûV>á°P>õ©M>gÊT>O˜`>íYb>e\>¶‹W>_X>ñÂk>îçÑ>y•ï>…I°>¢ñ≠>ûıª>.˛√>Pñ≈>ôä«>KáÕ>†÷¥>yMï>ﬂÙm>S∏W>¯Yg>Cü> √˙>Rﬁè=†≤ù='Qò=5jô="wô=Æoô=“oô=Ùoô=Úoô=Úoô=Úoô=Iç=Lú=¥ﬂ>ì∫ß>ìÑ>9z>fõÄ>]Gâ>Cnú>Ài±>5¥>´µÆ>ÎY®>dÀ±>Æ°>Ÿ€ò>ˇÕ¢>Ràû>é≥è>7
z>ŒDí>tpæ>^⁄>I]¶>ΩÙt>]Ùd>îc>pµO>ÆBG>≤z9>FÂA>Á˛H>∆üZ>Ù5c>G	b>¨)k>é@s>`˛q>“˙y>~ò~>÷˜~>ÿu>‹[|>ÆàÜ>_ßè>·√ñ>
xù>-‰ö>xCú>g‰û>Qú>Èmû>[Ø°>K#ù>æ≠†>∫^å>X©Å>´ç>Íö†>∆˛ñ>
\ô>81û>’ùØ>&√º>†c≥>∑Ìò>D.Ä>0f>1ZW>∫O>≠xf>ÔDÉ>éá>JÉ>˘±Å>Sq>÷`>Ç3\>_âO>LB>‚ëÄ>Rå>∏ÀÜ>yx>–Éd>£óÅ>z<`>¯ÿP>\üF>•\>b›\>œp}>@ÂÇ>AWÖ>L(ñ>}ö>6=ñ>™≤ã>Äq>[◊k>O|m>®t>û&É>eÇ>ÑdÄ>€¶x>ùYq>ﬁ‘h>@c>¡\>eo>f¶å>˜Fñ>ø?ï>q(ñ>°é>õ[á>˙Ü>ÖÑ>]ËÑ>+å>Pê>â’ä>ûàÇ>≠(v>qnp>¯o~>G‚ç>ƒÚò>HA†>îÕ¢>π:¢>ã¢>pø°>ñUò>«|á>8cn>dÄ`>nc>®Âd>éÈ~>P.á>Âv~>J◊m>ÌùX>ﬂZ3>T7>|π=âÉ=±¥ÿ='∞√=™‚¥=î“§=≥*ã=Ã(2>x
#>ŸM>(ô◊=É-Ø=Ÿÿï=ª>ÇÙ>ªa–=Êë∏=√K¶=Fsö=®˘ñ=ÒÔö=wû=∏Áü=~ü=¸∞ô=dô=ñnô=oô=Poô=Ãqô=∆uô=ô«ó=∑Âï=^∂∑=í0˜=≠†>∫tä>2ë{>êæm>π«]>"¶h>%±ã>W3¢>ñŒµ>eˇ∑>›j¡>j∫>•&©>ÖÖ£>•`ò>–¯ã>Xä>Â¬é>ùÍó>ùˇï>T#ç>BaÖ>JÇ>2Ä>Çﬂv>0îm>ìPo>∑oà>Ùìé>bDó>Úü>«	§>›Ï°>Åﬂó>ÜÚâ>rÃt>?ÈZ>%;O>,L>Ï¯E>ÄQD>sL>“/W>≠èV>Y,W>n3^>hw>Óõå>ØÛú>˝Ó®>G≥>D€¿>éÃ> ¥—>‚|Õ>Z…>z±>4î>—ºi>;VK>ÿt>]À >=ë?yˇÿ=ªäû=ÁÓó=úRô=wÖô=Voô=Eoô=˛oô=ıoô=Òoô=Úoô=ŸÕ*=â2É>b.√>Ò∏Ã>Ú¢>ñˇí>„-ç>d9ç>”rë>“û>±Æ>K$≠>fí¶>Å:•>B¶§>fî>ã¶ì>ÖÑô>≈ë>Sôp>3âe>êÓÄ>û>]¶>Ÿ~ä>{Ôm>æ?b>¬S>pÀS>¡:a>A[>èS>s¯[>¨lb>y*g> —Ä>Î^t>«;t>\≠p>∞ùn>;Ûw>[y>Û'{>'Ç>»Fç>Ì·ß>®≠>˝Y¶>Fª≠>ù)´>Ëù>
£•>ïˇ¶>3Æ¢>Dπ†>ÇÂ†> Bï>!è>aî>àjè>˘wì>)yó>¸=ú>Dy©>-·≠>2•>^Äê>•êt>
˚c>&Bb>˙>∂(á>ê©ã>‡Yç>`ã>Ry>gj>˛k>K:W>åîF>ûÖ>E é> à>åp>ì’M>q{>7•ä>Ÿ!h>^ªa>ˆ˙r>>9w>Dpt>~€Å>æ4à>Åƒé>I‹ì>ÎOë>%€á>`d>6^>DFe>´åu>≈Yà>dÑ>5HÇ>?rÄ>€£w>∑i>0Î^>NΩY>'ï~>µöê>QWë>:Nè>≠îí> .ë>g‡é>à?è>ËÊã>òåä>ñ®è>∂œé>Íœá>wçy>“v>Ey>KyÖ>õ>kÙ§>H}£>Mª£>∑®>ß–™>•öß>.]ó>˜GÄ>T£[>	M>
˝^>Kfp>ËÉ>O;é>·ä>%Mm>üVL>NJ>K∆D>]Ã#>qﬂJ>rÛF>\eG>ÂT>ùRh>p¸e> /¶>ªˆ≤>#9∏>–™°>URâ>Någ>Îóp>|*c>◊B>ÿ»6>vÄ)>‚Y>Bq≠=F%°=KÁó=n
ì=-í=π2ô=ëxô=Iqô=	pô=
pô=Ωoô=úpô=Ó€ô=ïö=ñLî=´zò=˘è=ªW>#j{>q>£¯m>zt>Óäã>˝Ïñ>ÏTù>A∂î>~›ï>Üí>+ˇÇ>O˙è>=¢é>=è>_Fô>ÎΩß>‚ï∏>ÿıπ>dÚ†>B‚é>Üä>®·Ñ>µv>î§p>◊Kz>ä>XÁç>hì>oŸõ>Gfü>4Úó>ôé>Õ9Ç>∆Œi>:9X>ÛK>îvG><¯C>Úr@>yH>FP>‰∑Q>f¶X>X∆`>¶á|>í>NÇ§>°±>\™ª> M»>.F“>§Ÿ>Üô—>îæ≈>`˚•>£√Ç>ú‡P>≥>>Äze>(rß>Ú?ÙUÄ>ídï=Réö=ºÇô=°aô=™pô=¸oô=Òoô=Ùoô=Òoô=Úoô=d[=éPa>Ëº>Râ·>3’Ã>ø∏>¸î™>	¶>∆P¢>(b£>Œ©™>Í©>XÌ¶>‘°>Nh°>—‡ì>óë>/@ï>∞Rà>]i>2Ï]>Â#S>0⁄V>ŸDx>˛È}>Ùw>Ay>_z>=9u>‚a>loJ>∑Ò@>˛hO>¥∞a>@úu>`Ωy>Ävx>∑~>B∏y>‘Òl>≠√r><y>»Ëz>å‘Ä>ë|õ>'™≤>RÕ≠>jÆ>á◊¥>m Æ>”R§>≈Ø>“’™>˝H™>ñwß>-•¢>PCò>m{å>ºtá>©	ê>t.>>¡x*>ômä>ª™ì>‘Kû>úE¶>õN£>£Âã>rˇ>˝â>)Ãé>ŸVâ>¸É>œvy>+n>˜Ic>!âd>‹Ñm>.y=><>kr>RJw>ó[>zÈ?>prK>œ-y>¡Fç>øÆà>qÎ{>ÂtÜ>‹õá>¡bÇ>Ñ>béá>?Iê>Ìê>éûé>}Åâ>]»z>•-e>i´i>~¯t>=ÃÑ>DTÇ>!Ç>Ç‘Ñ>Ä>fÅm>µäa>5a>o·É>,¡á>™Ñ>Fñá>GÔè>Ω í>I·ñ>ƒö>ÉÒó>0òë>œ?è>Ãä>‡˜Ç>O\s>9ät>—XÅ>è¨â>}Uû>»¸•>ø.£>U¡£>,q•>ÉïÆ>}Ö¢>Üå>^o>˙öR>W"G>‹Òi>ÆaÑ>º„ì>tï£>Zh¢>mIñ>»‡Ü>ÊÚÄ>+m>˜÷_>^ÒQ>|M>6ƒJ>≠YV>^;>˛óè>:í>H{ü>`∞>Éß>‰ô><Œå>|ai>ûaM>Ç?>-t9>.À7>ú;>V*>qä.>lC$>R>¥‚È=ˇô=4–ô=dpô=6nô=ñoô=Zpô=|oô=´[ô=ÆRô=wö=1¢ò=mÆí=Ú=-„>óÖo>œ„k>-ëv>Ùuá>vãâ>§Çà>f2w>3o>˝g>sc>ìÙg>Üni>åØà>ù>°Ë±>Œ<…>a¥œ>ﬂ’¬> Æ>ö!ò>XLá>9Ëv>=r>^x>%…Ä>ırÜ>M˝å>™!ê>Úúè>)çâ>„cÖ>W◊u>—†`>†Y>,kQ>ÏN>ÿM>HßH>„[>{{ bos_token }}
{%- if messages[0]['role'] == 'system' -%}
    {%- if messages[0]['content'] is string -%}
        {%- set first_user_prefix = messages[0]['content'] + '

' -%}
    {%- else -%}
        {%- set first_user_prefix = messages[0]['content'][0]['text'] + '

' -%}
    {%- endif -%}
    {%- set loop_messages = messages[1:] -%}
{%- else -%}
    {%- set first_user_prefix = "" -%}
    {%- set loop_messages = messages -%}
{%- endif -%}
{%- for message in loop_messages -%}
    {%- if (message['role'] == 'user') != (loop.index0 % 2 == 0) -%}
        {{ raise_exception("Conversation roles must alternate user/assistant/user/assistant/...") }}
    {%- endif -%}
    {%- if (message['role'] == 'assistant') -%}
        {%- set role = "model" -%}
    {%- else -%}
        {%- set role = message['role'] -%}
    {%- endif -%}
    {{ '<start_of_turn>' + role + '
' + (first_user_prefix if loop.first else "") }}
    {%- if message['content'] is string -%}
        {{ message['content'] | trim }}
    {%- elif message['content'] is iterable -%}
        {%- for item in message['content'] -%}
            {%- if item['type'] == 'image' -%}
                {{ '<start_of_image>' }}
            {%- elif item['type'] == 'text' -%}
                {{ item['text'] | trim }}
            {%- endif -%}
        {%- endfor -%}
    {%- else -%}
        {{ raise_exception("Invalid content type") }}
    {%- endif -%}
    {{ '<end_of_turn>
' }}
{%- endfor -%}
{%- if add_generation_prompt -%}
    {{'<start_of_turn>model
'}}
{%- endif -%}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰=e‰
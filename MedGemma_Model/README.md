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
*   **Anatomical localization:** Bounding box–based localization of anatomical
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
*   **Key publication**: [https://arxiv.org/abs/2604.05081](https://arxiv.org/abs/2604.05081)
*   **Model created**: **4B multimodal**: Jan 13, 2026
*   **Model version**: **4B multimodal**: 1.5.0

### Citation

When using this model, please cite: 
Sellergren et al. "MedGemma 1.5 Technical Report." *arXiv preprint arXiv:2604.05081* (2026).

```none
@article{sellergren2026medgemma,
  title={MedGemma 1.5 Technical Report},
  author={Sellergren, Andrew and Gao, Chufan and Mahvar, Fereshteh and Kohlberger, Timo and Jamil, Fayaz and Traverse, Madeleine and Tono, Alberto and Sadjad, Bashir and Yang, Lin and Lau, Charles and others},
  journal={arXiv preprint arXiv:2604.05081},
  year={2026}
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
[MedGemma 1.5 Technical Report](https://arxiv.org/abs/2604.05081).

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
| MedMCQA | 45.4 | 55.7 | 59.8 | 70.2 |
| PubMedQA | 68.4 | 73.4 | 68.2 | 77.2 |
| MMLU Med | 67.2 | 70.0 | 69.6 | 86.2 |
| MedXpertQA (text only) | 11.6 | 14.2 | 16.4 | 23.7 |
| AfriMed-QA (25 question test set) | 48.0 | 52.0 | 56.0 | 72.0 |

#### Medical record evaluations

EHR understanding and interpretation was evaluated for synthetic longitudinal
text-based EHR data and real-world de-identified discharge summaries via
question-answering benchmark datasets for MedGemma 1.5 4B, MedGemma 1 variants,
and Gemma 3 4B.

| Dataset | Metric | Gemma 3 4B | MedGemma 1 4B | MedGemma 1.5 4B | MedGemma 1 27B |
| :---- | :---- | :---- | :---- | :---- | :---- |
| EHRQA\* | Accuracy | 70.9 | 67.6 | 89.6 | 90.5 |
| EHRNoteQA | Accuracy | 78.0 | 79.4 | 80.4 | 90.7 |

\* Internal dataset

#### Document understanding evaluations

Evaluation of converting unstructured medical lab reports documents
(PDFs/images) into structured JSON data.

| Task / Dataset | Metric | Gemma 3 4B | MedGemma 1 4B | MedGemma 1.5 4B | MedGemma 1 27B  |
| :---- | :---- | :---- | :---- | :---- | :---- |
|  **PDF-to-JSON Lab Test Data Conversion** |  |  |  |  |  |
| EHR Dataset 2\* (raw PDF to JSON) | Macro F1 (average over per document  F1 scores)  | 84.0 | 78.0 | 91.0 | 76.0 |
|  | Micro F1 (F1 across all extracted data fields) | 81.0 | 75.0 | 88.0 | 70.0 |
| EHR Dataset 3\* (raw PDF to JSON) | Macro F1 | 61.0 | 50.0 | 71.0 | 66.0 |
|  | Micro F1 | 61.0 | 51.0 | 70.0 | 69.0 |
| Mendeley Clinical Laboratory Test Reports (PNG image to JSON) | Macro F1 | 83.0 | 85.0 | 85.0 | 69.0 |
|  | Micro F1 | 78.0 | 81.0 | 83.0 | 68.0 |
| EHR Dataset 4\* | Macro F1 | 41.0 | 25.0 | 64.0 |  |
|  | Micro F1 | 41.0 | 33.0 | 67.0 |  |

\* Internal datasets.

### Ethics and safety evaluation

#### Evaluation approach

Our evaluation methods include structured evaluations and internal red-teaming
testing of relevant content policies. Red-teaming was conducted by a number of
different teams, each with different goals and human evaluation metrics. These
models were evaluated against a number of different categories relevant to
ethics and safety, including:

*   **Child safety**: Evaluation of text-to-text and image-to-text prompts
    covering child safety policies, including child sexual abuse and
    exploitation.
*   **Content safety**: Evaluation of text-to-text and image-to-text prompts
    covering safety policies, including harassment, violence and gore, and hate
    speech.
*   **Representational harms**: Evaluation of text-to-text and image-to-text
    prompts covering safety policies, including bias, stereotyping, and harmful
    associations or inaccuracies.
*   **General medical harms**: Evaluation of text-to-text and image-to-text
    prompts covering safety policies, including information quality and
    potentially harmful responses or inaccuracies.

In addition to development level evaluations, we conduct "assurance evaluations"
which are our "arms-length" internal evaluations for responsibility governance
decision making. They are conducted separately from the model development team
and inform decision making about release. High-level findings are fed back to
the model team but prompt sets are held out to prevent overfitting and preserve
the results' ability to inform decision making. Notable assurance evaluation
results are reported to our Responsibility & Safety Council as part of release
review.

#### Evaluation results

For all areas of safety testing, we saw safe levels of performance across the
categories of child safety, content safety, and representational harms compared
to previous Gemma models. All testing was conducted without safety filters to
evaluate the model capabilities and behaviors. For both text-to-text and
image-to-text the model produced minimal policy violations. A limitation of our
evaluations was that they included primarily English language prompts.

## Data card

### Dataset overview

#### Training

The base Gemma models are pre-trained on a large corpus of text and code data.
MedGemma multimodal variants utilize a
[SigLIP](https://arxiv.org/abs/2303.15343) image encoder that has been
specifically pre-trained on a variety of de-identified medical data, including
radiology images, histopathology images, ophthalmology images, and dermatology
images. Their LLM component is trained on a diverse set of medical data,
including medical text, medical question-answer pairs, FHIR-based electronic
health record data (27B multimodal only), radiology images, histopathology
patches, ophthalmology images, and dermatology images.

#### Evaluation

MedGemma models have been evaluated on a comprehensive set of clinically
relevant benchmarks across multiple datasets, tasks and modalities. These
benchmarks include both open and internal datasets.

#### Source

MedGemma utilizes a combination of public and private datasets.

This model was trained on diverse public datasets including MIMIC-CXR (chest
X-rays and reports), ChestImaGenome: Set of bounding boxes linking image
findings with anatomical regions for MIMIC-CXR SLAKE (multimodal medical images
and questions), PAD-UFES-20 (skin lesion images and data), SCIN (dermatology
images), TCGA (cancer genomics data), CAMELYON (lymph node histopathology
images), PMC-OA (biomedical literature with images), and Mendeley Digital Knee
X-Ray (knee X-rays).

Additionally, multiple diverse proprietary datasets were licensed and
incorporated (described next).

### Data ownership and documentation

*   [MIMIC-CXR](https://physionet.org/content/mimic-cxr/2.1.0/): MIT Laboratory
    for Computational Physiology and Beth Israel Deaconess Medical Center
    (BIDMC).
*   [MS-CXR-T](https://physionet.org/content/ms-cxr-t/1.0.0/): Microsoft
    Research Health Futures, Microsoft Research.
*   [ChestX-ray14](https://pmc.ncbi.nlm.nih.gov/articles/PMC6476887/): National
    Institutes of Health \- Clinical Center.
*   [SLAKE](https://www.med-vqa.com/slake/): The Hong Kong Polytechnic
    University (PolyU), with collaborators including West China Hospital of
    Sichuan University and Sichuan Academy of Medical Sciences / Sichuan
    Provincial People's Hospital.
*   [PAD-UFES-20](https://pmc.ncbi.nlm.nih.gov/articles/PMC7479321/): Federal
    University of Espírito Santo (UFES), Brazil, through its Dermatological and
    Surgical Assistance Program (PAD).
*   [SCIN](https://github.com/google-research-datasets/scin): A collaboration
    between Google Health and Stanford Medicine.
*   [TCGA](https://portal.gdc.cancer.gov/) (The Cancer Genome Atlas): A joint
    effort of National Cancer Institute and National Human Genome Research
    Institute. Data from TCGA are available via the Genomic Data Commons (GDC)
*   [CAMELYON](https://camelyon17.grand-challenge.org/Data/): The data was
    collected from Radboud University Medical Center and University Medical
    Center Utrecht in the Netherlands.
*   [PMC-OA (PubMed Central Open Access
    Subset)](https://catalog.data.gov/dataset/pubmed-central-open-access-subset-pmc-oa):
    Maintained by the National Library of Medicine (NLM) and National Center for
    Biotechnology Information (NCBI), which are part of the NIH.
*   [MedQA](https://arxiv.org/pdf/2009.13081): This dataset was created by a
    team of researchers led by Di Jin, Eileen Pan, Nassim Oufattole, Wei-Hung
    Weng, Hanyi Fang, and Peter Szolovits.
*   [MedMCQA](https://arxiv.org/abs/2203.14371): This dataset was created by
    Ankit Pal, Logesh Kumar Umapathi and Malaikannan Sankarasubbu from Saama AI
    Research, Chennai, India
*   [PubMedQA](https://arxiv.org/abs/1909.06146): This dataset was created by
    Qiao Jin, Bhuwan Dhingra, Zhengping Liu, William W. Cohen, Xinghua Lu from
    the University of Pittsburg, Carnegie Mellon University and Google.
*   [LiveQA](https://trec.nist.gov/pubs/trec26/papers/Overview-QA.pdf): This
    dataset was created by Ben Abacha Asma, Eugene Agichtein Yuval Pinter and
    Dina Demner-Fushman from the U.S. National Library of Medicine, Emory
    University and Georgia Institute of Technology.
*   [Mendeley Digital Knee
    X-Ray](https://data.mendeley.com/datasets/t9ndx37v5h/1): This dataset is
    from Rani Channamma University, and is hosted on Mendeley Data.
*   [AfriMed-QA](https://afrimedqa.com/): This data was developed and led by
    multiple collaborating organizations and researchers include key
    contributors: Intron Health, SisonkeBiotik, BioRAMP, Georgia Institute of
    Technology, and MasakhaneNLP.
*   [VQA-RAD](https://www.nature.com/articles/sdata2018251): This dataset was
    created by a research team led by Jason J. Lau, Soumya Gayen, Asma Ben
    Abacha, and Dina Demner-Fushman and their affiliated institutions (the US
    National Library of Medicine and National Institutes of Health)
*   [Chest ImaGenome](https://physionet.org/content/chest-imagenome/1.0.0/): IBM
    Research.
*   [MedExpQA](https://www.sciencedirect.com/science/article/pii/S0933365724001805):
    This dataset was created by researchers at the HiTZ Center (Basque Center
    for Language Technology and Artificial Intelligence).
*   [MedXpertQA](https://huggingface.co/datasets/TsinghuaC3I/MedXpertQA): This
    dataset was developed by researchers at Tsinghua University (Beijing, China)
    and Shanghai Artificial Intelligence Laboratory (Shanghai, China).
*   [HealthSearchQA](https://huggingface.co/datasets/katielink/healthsearchqa):
    This dataset consists of consisting of 3,173 commonly searched consumer
    questions.
*   [ISIC](https://www.isic-archive.com/): International Skin Imaging
    Collaboration is a joint effort involving clinicians, researchers, and
    engineers from various institutions worldwide.
*   [Mendeley Clinical Laboratory Test
    Reports](https://data.mendeley.com/datasets/bygfmk4rx9/2): This dataset is
    hosted on Mendeley and includes 260 clinical laboratory test reports issued
    by 24 laboratories in Egypt.
*   [CT-RATE](https://huggingface.co/datasets/ibrahimhamamci/CT-RATE): Istanbul
    Medipol University Mega Hospital and University of Zurich / ETH Zurich.

In addition to the public datasets listed above, MedGemma was also trained on
de-identified, licensed datasets or datasets collected internally at Google from
consented participants.

*   **CT dataset 1:** De-identified dataset of different axial CT studies across
    body parts (head, chest, abdomen) from a US-based radiology outpatient
    diagnostic center network.
*   **MRI dataset 1:** De-identified dataset of different axial multi-parametric
    MRI studies across body parts (head, abdomen, knee) from a US-based
    radiology outpatient diagnostic center network
*   **Ophthalmology dataset 1 (EyePACS):** De-identified dataset of fundus
    images from diabetic retinopathy screening.
*   **Dermatology dataset 1:** De-identified dataset of teledermatology skin
    condition images (both clinical and dermatoscopic) from Colombia.
*   **Dermatology dataset 2:** De-identified dataset of skin cancer images (both
    clinical and dermatoscopic) from Australia.
*   **Dermatology dataset 3:** De-identified dataset of non-diseased skin images
    from an internal data collection effort.
*   **Dermatology dataset 4**: De-identified dataset featuring multiple images
    and longitudinal visits and records from Japan.
*   **Dermatology dataset 5**: Dermatology dataset featuring unlabeled images.
*   **Dermatology dataset 6**: De-identified cases from adult patients with data
    representing Fitzpatrick 5 or 6 skin types
*   **Pathology dataset 1:** De-identified dataset of histopathology H\&E whole
    slide images created in collaboration with an academic research hospital and
    biobank in Europe. Comprises de-identified colon, prostate, and lymph nodes.
*   **Pathology dataset 2:** De-identified dataset of lung histopathology H\&E
    and IHC whole slide images created by a commercial biobank in the United
    States.
*   **Pathology dataset 3:** De-identified dataset of prostate and lymph node
    H\&E and IHC histopathology whole slide images created by a contract
    research organization in the United States.
*   **Pathology dataset 4:** De-identified dataset of histopathology whole slide
    images created in collaboration with a large, tertiary teaching hospital in
    the United States. Comprises a diverse set of tissue and stain types,
    predominantly H\&E.
*   **EHR dataset 1:** Question/answer dataset drawn from synthetic FHIR records
    created by [Synthea.](https://synthetichealth.github.io/synthea/) The test
    set includes 19 unique patients with 200 questions per patient divided into
    10 different categories.
*   **EHR dataset 2**: De-identified Lab Reports across different departments in
    Pathology such as Biochemistry, Clinical Pathology, Hematology, Microbiology
    and Serology
*   **EHR dataset 3**: De-identified Lab Reports across different departments in
    Pathology such as Biochemistry, Clinical Pathology, Hematology, Microbiology
    and Serology from at least 25 different labs
*   **EHR dataset 4**: Synthetic dataset of laboratory reports
*   **EHR dataset 5**: Synthetic dataset of approximately 60,000 health-relevant
    user queries

### Data citation

*   **MIMIC-CXR:** Johnson, A., Pollard, T., Mark, R., Berkowitz, S., & Horng,
    S. (2024). MIMIC-CXR Database (version 2.1.0). PhysioNet.
    [https://physionet.org/content/mimic-cxr/2.1.0/](https://physionet.org/content/mimic-cxr/2.1.0/)
    *and* Johnson, Alistair E. W., Tom J. Pollard, Seth J. Berkowitz, Nathaniel
    R. Greenbaum, Matthew P. Lungren, Chih-Ying Deng, Roger G. Mark, and Steven
    Horng. 2019\. "MIMIC-CXR, a de-Identified Publicly Available Database of
    Chest Radiographs with Free-Text Reports." *Scientific Data 6* (1): 1–8.
*   **MS-CXR-T:** Bannur, S., Hyland, S., Liu, Q., Pérez-García, F., Ilse, M.,
    Coelho de Castro, D., Boecking, B., Sharma, H., Bouzid, K., Schwaighofer,
    A., Wetscherek, M. T., Richardson, H., Naumann, T., Alvarez Valle, J., &
    Oktay, O. (2023). MS-CXR-T: Learning to Exploit Temporal Structure for
    Biomedical Vision-Language Processing (version 1.0.0). PhysioNet.
    [https://doi.org/10.13026/pg10-j984](https://doi.org/10.13026/pg10-j984).
*   **ChestX-ray14:** Wang, Xiaosong, Yifan Peng, Le Lu, Zhiyong Lu,
    Mohammadhadi Bagheri, and Ronald M. Summers. "Chestx-ray8: Hospital-scale
    chest x-ray database and benchmarks on weakly-supervised classification and
    localization of common thorax diseases." In *Proceedings of the IEEE
    conference on computer vision and pattern recognition*, pp. 2097-2106.
    2017\.
*   **SLAKE:** Liu, Bo, Li-Ming Zhan, Li Xu, Lin Ma, Yan Yang, and Xiao-Ming Wu.
    2021.SLAKE: A Semantically-Labeled Knowledge-Enhanced Dataset for Medical
    Visual Question Answering."
    [http://arxiv.org/abs/2102.09542](http://arxiv.org/abs/2102.09542).
*   **PAD-UFES-20:** Pacheco, Andre GC, et al. "PAD-UFES-20: A skin lesion
    dataset composed of patient data and clinical images collected from
    smartphones." *Data in brief* 32 (2020): 106221\.
*   **SCIN:** Ward, Abbi, Jimmy Li, Julie Wang, Sriram Lakshminarasimhan, Ashley
    Carrick, Bilson Campana, Jay Hartford, et al. 2024\. "Creating an Empirical
    Dermatology Dataset Through Crowdsourcing With Web Search Advertisements."
    *JAMA Network Open 7* (11): e2446615–e2446615.
*   **TCGA:** The results shown here are in whole or part based upon data
    generated by the TCGA Research Network:
    [https://www.cancer.gov/tcga](https://www.cancer.gov/tcga).
*   **CAMELYON16:** Ehteshami Bejnordi, Babak, Mitko Veta, Paul Johannes van
    Diest, Bram van Ginneken, Nico Karssemeijer, Geert Litjens, Jeroen A. W. M.
    van der Laak, et al. 2017\. "Diagnostic Assessment of Deep Learning
    Algorithms for Detection of Lymph Node Metastases in Women With Breast
    Cancer." *JAMA 318* (22): 2199–2210.
*   **CAMELYON17:** Bandi, Peter, et al. "From detection of individual
    metastases to classification of lymph node status at the patient level: the
    camelyon17 challenge." *IEEE transactions on medical imaging* 38.2 (2018):
    550-560.
*   **Mendeley Digital Knee X-Ray:** Gornale, Shivanand; Patravali, Pooja
    (2020), "Digital Knee X-ray Images", Mendeley Data, V1, doi:
    10.17632/t9ndx37v5h.1
*   **VQA-RAD:** Lau, Jason J., Soumya Gayen, Asma Ben Abacha, and Dina
    Demner-Fushman. 2018\. "A Dataset of Clinically Generated Visual Questions
    and Answers about Radiology Images." *Scientific Data 5* (1): 1–10.
*   **Chest ImaGenome:** Wu, J., Agu, N., Lourentzou, I., Sharma, A., Paguio,
    J., Yao, J. S., Dee, E. C., Mitchell, W., Kashyap, S., Giovannini, A., Celi,
    L. A., Syeda-Mahmood, T., & Moradi, M. (2021). Chest ImaGenome Dataset
    (version 1.0.0). PhysioNet. RRID:SCR\_007345.
    [https://doi.org/10.13026/wv01-y230](https://doi.org/10.13026/wv01-y230)
*   **MedQA:** Jin, Di, Eileen Pan, Nassim Oufattole, Wei-Hung Weng, Hanyi Fang,
    and Peter Szolovits. 2020\. "What Disease Does This Patient Have? A
    Large-Scale Open Domain Question Answering Dataset from Medical Exams."
    [http://arxiv.org/abs/2009.13081](http://arxiv.org/abs/2009.13081).
*   **MedMCQA:** Pal, Ankit, Logesh Kumar Umapathi, and Malaikannan
    Sankarasubbu. "Medmcqa: A large-scale multi-subject multi-choice dataset for
    medical domain question answering." *Conference on health, inference, and
    learning. PMLR,* 2022\.
*   **PubMedQA:** Jin, Qiao, et al. "Pubmedqa: A dataset for biomedical research
    question answering." *Proceedings of the 2019 conference on empirical
    methods in natural language processing and the 9th international joint
    conference on natural language processing (EMNLP-IJCNLP).* 2019\.
*   **LiveQA:** Abacha, Asma Ben, et al. "Overview of the medical question
    answering task at TREC 2017 LiveQA." *TREC.* 2017\.
*   **AfriMed-QA:** Olatunji, Tobi, Charles Nimo, Abraham Owodunni, Tassallah
    Abdullahi, Emmanuel Ayodele, Mardhiyah Sanni, Chinemelu Aka, et al. 2024\.
    "AfriMed-QA: A Pan-African, Multi-Specialty, Medical Question-Answering
    Benchmark Dataset."
    [http://arxiv.org/abs/2411.15640](http://arxiv.org/abs/2411.15640).
*   **MedExpQA:** Alonso, I., Oronoz, M., & Agerri, R. (2024). MedExpQA:
    Multilingual Benchmarking of Large Language Models for Medical Question
    Answering. *arXiv preprint arXiv:2404.05590*. Retrieved from
    [https://arxiv.org/abs/2404.05590](https://arxiv.org/abs/2404.05590)
*   **MedXpertQA:** Zuo, Yuxin, Shang Qu, Yifei Li, Zhangren Chen, Xuekai Zhu,
    Ermo Hua, Kaiyan Zhang, Ning Ding, and Bowen Zhou. 2025\. "MedXpertQA:
    Benchmarking Expert-Level Medical Reasoning and Understanding."
    [http://arxiv.org/abs/2501.18362](http://arxiv.org/abs/2501.18362).
*   **HealthSearchQA:** Singhal, Karan, Shekoofeh Azizi, Tao Tu, S. Sara
    Mahdavi, Jason Wei, Hyung Won Chung, Nathan Scales et al. "Large language
    models encode clinical knowledge." *Nature* 620, no. 7972 (2023): 172-180.
*   **ISIC**: Gutman, David; Codella, Noel C. F.; Celebi, Emre; Helba, Brian;
    Marchetti, Michael; Mishra, Nabin; Halpern, Allan. "Skin Lesion Analysis
    toward Melanoma Detection: A Challenge at the International Symposium on
    Biomedical Imaging (ISBI) 2016, hosted by the International Skin Imaging
    Collaboration (ISIC)". eprint [arXiv:1605.01397.
    2016](https://arxiv.org/abs/1605.01397)
*   **Mendeley Clinical Laboratory Test Reports:** Abdelmaksoud, Esraa;
    Gadallah, Ahmed; Asad, Ahmed (2022), “Clinical Laboratory Test Reports”,
    Mendeley Data, V2, doi: 10.17632/bygfmk4rx9.2
*   **CheXpert**: Irvin, J., Rajpurkar, P., Ko, M., Yu, Y., Ciurea-Ilcus, S.,
    Chute, C., Marklund, H., Haghgoo, B., Ball, R., Shpanskaya, K., Seekins, J.,
    Mong, D. A., Halabi, S. S., Sandberg, J. K., Jones, R., Larson, D. B.,
    Langlotz, C. P., Patel, B. N., Lungren, M. P., & Ng, A. Y. (2019). CheXpert:
    A Large Chest Radiograph Dataset with Uncertainty Labels and Expert
    Comparison. arXiv:1901.07031
*   **CT-RATE:** Hamamci, I. E., Er, S., Almas, F., Simsek, A. G., Esirgun, S.
    N., Dogan, I., Dasdelen, M. F., Wittmann, B., Menze, B., et al. (2024).
    CT-RATE Dataset. Hugging Face.
    [https://huggingface.co/datasets/ibrahimhamamci/CT-RATE](https://huggingface.co/datasets/ibrahimhamamci/CT-RATE)
    and Hamamci, Ibrahim Ethem, Sezgin Er, Furkan Almas, Ayse Gulnihan Simsek,
    Sevval Nil Esirgun, Irem Dogan, Muhammed Furkan Dasdelen, Bastian Wittmann,
    et al. 2024\. "Developing Generalist Foundation Models from a Multimodal
    Dataset for 3D Computed Tomography." *arXiv preprint arXiv:2403.17834*.
    [https://arxiv.org/abs/2403.17834](https://arxiv.org/abs/2403.17834)
*   **EHRNoteQA**: Sunjun Kweon, Jiyoun Kim, Heeyoung Kwak, Dongchul Cha,
    Hangyul Yoon, Kwanghyun Kim, Jeewon Yang, Seunghyun Won, Edward Choi. (2024)
    “EHRNoteQA: An LLM Benchmark for Real-World Clinical Practice Using
    Discharge Summaries.” arXiv:2402.16040

### De-identification/anonymization:

Google and its partners utilize datasets that have been rigorously anonymized or
de-identified to ensure the protection of individual research participants and
patient privacy.

## Implementation information

Details about the model internals.

### Software

Training was done using [JAX](https://github.com/jax-ml/jax).

JAX allows researchers to take advantage of the latest generation of hardware,
including TPUs, for faster and more efficient training of large models.

## Use and limitations

### Intended use

MedGemma is an open multimodal generative AI model intended to be used as a
starting point that enables more efficient development of downstream healthcare
applications involving medical text and images. MedGemma is intended for
developers in the life sciences and healthcare space. Developers are responsible
for training, adapting, and making meaningful changes to MedGemma to accomplish
their specific intended use. MedGemma models can be fine-tuned by developers
using their own proprietary data for their specific tasks or solutions.

MedGemma is based on Gemma 3 and has been further trained on medical images and
text. MedGemma enables further development in medical contexts (image and
textual); however, the model has been trained using chest x-ray, histopathology,
dermatology, fundus images, CT, MR, medical text/documents and electronic health
records (EHR) data. Examples of tasks within MedGemma’s training include visual
question answering pertaining to medical images, such as radiographs, document
understanding, or providing answers to textual medical questions.

### Benefits

*   Provides strong baseline medical image and text comprehension for models of
    its size.
*   This strong performance makes it efficient to adapt for downstream
    healthcare-based use cases, compared to models of similar size without
    medical data pre-training.
*   This adaptation may involve prompt engineering, grounding, agentic
    orchestration or fine-tuning depending on the use case, baseline validation
    requirements, and desired performance characteristics.

### Limitations

MedGemma is not intended to be used without appropriate validation, adaptation,
and/or making meaningful modification by developers for their specific use case.
The outputs generated by MedGemma are not intended to directly inform clinical
diagnosis, patient management decisions, treatment recommendations, or any other
direct clinical practice applications. All outputs from MedGemma should be
considered preliminary and require independent verification, clinical
correlation, and further investigation through established research and
development methodologies.

MedGemma's multimodal capabilities have been primarily evaluated on single-image
tasks. MedGemma has not been evaluated in use cases that involve comprehension
of multiple images.

MedGemma has not been evaluated or optimized for multi-turn applications.

MedGemma's training may make it more sensitive to the specific prompt used than
Gemma 3.

When adapting MedGemma developer should consider the following:

*   **Bias in validation data:** As with any research, developers should ensure
    that any downstream application is validated to understand performance using
    data that is appropriately representative of the intended use setting for
    the specific application (e.g., age, sex, gender, condition, imaging device,
    etc).
*   **Data contamination concerns**: When evaluating the generalization
    capabilities of a large model like MedGemma in a medical context, there is a
    risk of data contamination, where the model might have inadvertently seen
    related medical information during its pre-training, potentially
    overestimating its true ability to generalize to novel medical concepts.
    Developers should validate MedGemma on datasets not publicly available or
    otherwise made available to non-institutional researchers to mitigate this
    risk.

### Release notes

#### MedGemma 4B IT

*   Jan 13, 2026: Release of MedGemma 1.5 with improved medical reasoning,
    medical records interpretation and medical image interpretation
*   Jan 23, 2026: Updated generation config to use greedy decoding by default.
    Sampling can still be allowed by users to achieve previous functionality.
    Please see https://huggingface.co/docs/transformers/en/generation_strategies
    for details.
   
# Third-party tools and model provenance

No model was trained or fine-tuned by this team. The code uses local pretrained OCR; it does not claim the upstream training as team work.

The installed package is `rapidocr_onnxruntime==1.4.4`. Its wheel supplies these models:

| Model | Role | Bytes |
| --- | --- | ---: |
| ch_PP-OCRv4_det_infer.onnx | Text detection | 4,745,517 |
| ch_PP-OCRv4_rec_infer.onnx | Text recognition | 10,857,958 |
| ch_ppocr_mobile_v2.0_cls_infer.onnx | Orientation classifier bundled by the package; classification disabled in this pipeline | 585,532 |

[MODEL_MANIFEST.json](MODEL_MANIFEST.json) records their actual installed SHA-256 hashes. Installing the pinned package restores these files; no sponsor-derived weights are distributed.

RapidOCR identifies its ONNX model conversion origin as PaddleOCR and licenses its project under Apache-2.0. The upstream PaddleOCR repository also supplies an Apache-2.0 license. Sources checked on 2026-10-04: [RapidOCR project](https://github.com/RapidAI/RapidOCR), [PaddleOCR license](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE). Installed package notices and a copy of the upstream license are in [third_party](third_party/).

Dependency versions are pinned in requirements-lock.txt. The dependency notices copied from the installed distributions are indexed in third_party/PACKAGES.json:

| Dependency | Purpose | Observed license metadata |
| --- | --- | --- |
| PyMuPDF | Local native extraction/rendering | AGPL-3.0 or commercial; this repository uses the free AGPL route |
| RapidOCR | Local OCR wrapper and packaged weights | Apache-2.0 |
| ONNX Runtime | CPU neural inference | MIT |
| ReportLab | PDF reports | BSD |
| Pillow | Local image handling | MIT-CMU |
| openpyxl | Local XLSX inspection support | MIT |
| jsonschema | Record validation | MIT |
| nbformat, nbclient, ipykernel | Notebook format and local execution | BSD-3-Clause |

Sources for dependency metadata are the exact installed distributions, not an assertion that the latest upstream release matches these pins. The preserved notices remain authoritative for the copied packages.

AI assistance was used to develop and review code against the public sponsor schema and deliberately synthetic examples. Confidential sponsor drawing content was not sent to an external model. No remote AI service is a runtime dependency.

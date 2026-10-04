"""Create an English notebook using the same library as the CLI."""
from pathlib import Path
import nbformat
repo=Path(__file__).resolve().parents[1]
cells=[
nbformat.v4.new_markdown_cell("""# Local plan-to-shop reconciliation

**SOTA Overfitters — Kenneth Chen and Ning Ye**

The default walkthrough creates explicitly synthetic drawings. Sponsor PDFs, notebook outputs and reports stay local. This notebook calls the same pipeline as the CLI.

For a real local run, set `L2C_INPUT` and `L2C_OUTPUT` before execution; use a fresh private output directory. A real-data executed copy must never enter the public repository. No external inference service is used."""),
nbformat.v4.new_code_cell("""from pathlib import Path
import json, os, sys
REPO = Path.cwd()
if not (REPO / "l2c_pipeline.py").exists():
    REPO = REPO.parent
assert (REPO / "l2c_pipeline.py").exists(), "Run with the repository as the working directory."
sys.path.insert(0, str(REPO))
from l2c.synthetic import generate_project
from l2c.pipeline import run_project
WORK = Path(os.environ.get("L2C_NOTEBOOK_WORK", str(REPO.parent / "private" / "notebook-run"))).resolve()
WORK.mkdir(parents=True, exist_ok=True)
synthetic = not bool(os.environ.get("L2C_INPUT"))
if synthetic:
    INPUT = WORK / "synthetic-input"
    generate_project(INPUT)
else:
    INPUT = Path(os.environ["L2C_INPUT"]).resolve()
OUTPUT = Path(os.environ.get("L2C_OUTPUT", str(WORK / "outputs"))).resolve()
print({"mode": "synthetic" if synthetic else "local private input", "pdf_files": len(list(INPUT.rglob("*.pdf")))})"""),
nbformat.v4.new_markdown_cell("""## Extract, associate, compare and report

The native reader retains annotation coordinates. The optional local OCR path is CPU only and bounded. Matching uses element identity, family and level. Unknown quantities, duplicate candidates and unresolved scope trigger review; empty extraction does not imply conformity.

The generated fixture is deliberately complete, so missing/added cases may be confirmed there. Real runs keep unmatched elements as candidates until scope is reviewed locally."""),
nbformat.v4.new_code_cell("""summary = run_project(INPUT, OUTPUT,
    ocr_mode=os.environ.get("L2C_OCR", "off"),
    ocr_max_pages=int(os.environ.get("L2C_OCR_MAX_PAGES", "8")),
    synthetic=synthetic, assert_complete_scope=synthetic)
summary"""),
nbformat.v4.new_markdown_cell("""## Structural checks and coverage

Only aggregate checks are displayed. Detailed records, provenance, rejected annotations and PDF reports are written to the local output directory. The example schema contains no drawing data."""),
nbformat.v4.new_code_cell("""records = json.loads((OUTPUT / "extractions.json").read_text(encoding="utf-8"))
coverage = json.loads((OUTPUT / "coverage.json").read_text(encoding="utf-8"))
ids = [record["id"] for record in records]
assert len(ids) == len(set(ids))
assert sum(summary["records_by_family"].values()) == len(records)
print({"unique_ids": len(ids), "input_pages_accounted_for": len(coverage),
       "reports": summary["pdf_reports"],
       "precision_recall_measured": summary["precision_recall_measured"]})
del records, coverage, ids"""),
nbformat.v4.new_markdown_cell("""## Interpretation and limits

Synthetic fixtures test behavior, not accuracy on sponsor drawings. Six possible workbook references are not an exhaustive benchmark. No precision/recall is claimed without verified labels. Unsupported notation and uncertain context remain visible for review. The engineer retains the final decision.

Open `reports/summary.pdf` and the per-sheet reports locally. Their filenames and detailed contents are deliberately not displayed here."""),
]
nb=nbformat.v4.new_notebook(cells=cells,metadata={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python","version":"3.12"}})
out=repo/"notebooks"/"l2c_pipeline.ipynb"; out.parent.mkdir(exist_ok=True)
nbformat.write(nb,out)
print("Public notebook source created with no executed outputs.")

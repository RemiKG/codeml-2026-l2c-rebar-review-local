# Local reinforcement review

SOTA Overfitters — Kenneth Chen and Ning Ye  
CodeML 2026, L2C — From plans to shop drawings

This Python prototype reads local structural-plan and reinforcement-shop PDFs, exports the sponsor's record shape, associates elements using identity/family/level, and generates explained PDF reports. The final engineering decision remains with the engineer.

**Technical acceptance is incomplete.** The preserved first real pass produced **zero confirmed real associations**: 141 PDFs / 611 drawing pages, 162 records, 187 PDF reports, with 332 OCR pages deferred. These are processing counts, not measured precision/recall. Later native-layout corrections and 61 passing synthetic tests do not establish real detection accuracy. See [validation scope](docs/VALIDATION.md).

## Install in an isolated environment

Python 3.12 was used for verification. From the repository directory on Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

The pinned RapidOCR package includes three small ONNX models. They are loaded locally for CPU inference; no external OCR/AI API is used. The program limits numeric workers to two threads and processes one page at a time. See [THIRD_PARTY.md](THIRD_PARTY.md) for attribution and model hashes.

## Run the synthetic example

Use a fresh output directory outside the repository:

```powershell
.\.venv\Scripts\python.exe -m l2c.synthetic --output ../l2c-private/synthetic-input
.\.venv\Scripts\python.exe l2c_pipeline.py --input ../l2c-private/synthetic-input --output ../l2c-private/synthetic-output-001 --synthetic --assert-complete-scope
```

The generated fixture includes five element families and intentional compliant, non-compliant, missing and added cases. `--synthetic` adds a label; it does not anonymize arbitrary files. Complete-scope assertion is appropriate for this intentionally known fixture.

For an unfamiliar real project:

```powershell
.\.venv\Scripts\python.exe l2c_pipeline.py --input ../confidential-project --output ../l2c-private/project-run-001 --ocr auto --ocr-max-pages 8
```

Real inputs and outputs must remain local in the sponsor-authorized private workflow. Do not pass them to a coding agent, cloud model, public Git repository or an unapproved upload service. Do not assume a private cloud folder is authorized.

The program prints aggregate counts only. Detailed errors go to the private output log. Existing output directories are not overwritten. Keep the original PDFs unchanged.

If unfamiliar filenames do not identify their role, supply `--roles ../l2c-private/roles.json`. The local JSON maps relative filenames to `plan` or `atelier`, for example `{"structural.pdf":"plan","fabrication.pdf":"atelier"}`. It does not require changing the original files. Unclassified files remain visible in the coverage report.

## Files produced

- `extractions.json`: the ten-key sponsor-shaped records.
- `provenance.json`: context, level, annotation boxes, extraction method and supporting text; private for real inputs.
- `matches.json` and `discrepancies.json`: matched IDs, decisions, expected/observed attributes and review reasons.
- `coverage.json` and `rejections.json`: every processed page and unsupported or ambiguous annotations.
- `candidates.json`: partly extracted annotations whose element/sheet context is unresolved; separate from schema-valid records and confirmed decisions.
- `input_manifest.json`: original input paths, sizes and SHA-256 hashes.
- `aggregate.json`: non-sensitive structural counts; no precision/recall claim.
- `reports/index.json`, per-sheet PDFs and `reports/summary.pdf`: locally reviewable reports.
- `runtime.log` and `run_status.json`: private run diagnostics.

Reports distinguish confirmed comparisons from unresolved cases. An unmatched element remains a candidate unless a local reviewer explicitly asserts complete scope; detected processing failures still disable that assertion. Empty extraction never implies conformity.

## How it works

1. Native PDF text is read with coordinates and transformed into displayed-page PDF points. The origin is the cropped/rotated page's top-left; page numbers start at 1.
2. Explicit element IDs, levels and common Canadian reinforcement notation are parsed conservatively. Examples include `C-12`, `8-25M`, `15M @200 mm`, and `L=3.6 m`.
3. Nearby label association is bounded geometrically; equally plausible candidates are rejected for review.
   Explicit positioned schedule axes are also supported when both element and level labels establish a unique cell. This narrow layout case passed synthetic tests but recovered no record in the bounded CLP probe.
4. Native-text-poor pages may use local OCR. Resolution and the total number of OCR pages are bounded. Pages exceeding the budget remain visible as unprocessed/review cases.
5. Matching requires equal family, normalized element ID and identified level. Repeated candidates need review unless explicit `PART 1/2`, `PART 2/2` declarations form a complete disjoint set.
6. Quantity is compared first. Available diameters, spacing and lengths are compared separately. Unknown quantity does not become zero. Length tolerance is zero unless explicitly set using `--length-tolerance-mm`.

Lengths and spacings accept mm, cm, m, feet and inches, including explicit prime/quote notation and simple fractions. Conversion uses exact rational factors: one inch is 25.4 mm and one foot is 304.8 mm; the original notation remains in private provenance. A genuinely unitless numeric field defaults to millimetres. Unknown units, negative dimensions and malformed fractions are rejected into the private review queue. Distinct positioned repetitions retain their individual annotation boxes and bars, and block automatic totals. Only identical callouts whose boxes coincide within one PDF point are suppressed as extraction duplicates. Two absent levels never establish the same location.

OCR pauses for that page when available RAM is below 1.5 GiB, with an additional 0.25 GiB reserve before initial model loading. Deferred pages remain explicit in coverage and require a later run; they cannot support complete-scope claims.

The example schema supplied by the sponsor is not a formal JSON Schema. The array container, source values `plan/atelier`, family names and null handling are documented implementation conventions in [schema/extractions.schema.json](schema/extractions.schema.json).

## Notebook and verification

[notebooks/l2c_pipeline.ipynb](notebooks/l2c_pipeline.ipynb) uses the same library as the CLI. It contains no executed outputs and defaults to generated synthetic data. [The executed public example](notebooks/synthetic.executed.ipynb) contains only authored synthetic results. The executed real notebook remains in the private jury package.

```powershell
.\.venv\Scripts\python.exe tools/run_tests.py --receipt ../l2c-private/SYNTHETIC_TESTS.json
.\.venv\Scripts\python.exe tools/execute_notebook.py --output ../l2c-private/synthetic.executed.ipynb --work ../l2c-private/notebook-001
.\.venv\Scripts\python.exe tools/verify_synthetic_ocr.py --work ../l2c-private/ocr-check-001
```

The notebook runner binds its kernel to 127.0.0.1, stops it explicitly, and stores the executed copy outside the public repository. For a later real run, supply `--input` and keep that executed notebook private.

Tests exercise quantities/units, missing attributes, levels, duplicates, complete and incomplete parts, uncertain absence, schema and coordinate bounds, rotated/cropped PDFs, unknown/broken inputs, page budgets, output protection, reports and aggregate-only CLI output.

## Limitations

The grammar does not interpret every construction-table layout, graphical bar symbol, bending schedule or note scope. Unidentified sheets/levels and unsupported reinforcement annotations need local review. Raster downscaling may lose small text; OCR is not evidence that an element was correctly associated.

No sponsor-project precision/recall, independent semantic review or fifth-project evaluation has been completed. Six possible spreadsheet reference rows cannot establish an exhaustive benchmark. The first WP2 run was frozen before processing and retained; subsequent development is labelled post-evaluation. All performance claims remain tied to their actual receipt and data scope.

The 10-minute jury demonstration must run on the unfamiliar evaluation project. A synthetic or precomputed fallback cannot replace that requirement.

## Code map

- `l2c_pipeline.py`: safe CLI entry point.
- `l2c/pdfio.py`, `parsing.py`: local reading, coordinates and conservative notation grammar.
- `l2c/schedules.py`: explicit positioned schedule-cell associations.
- `l2c/matching.py`: context-aware associations and explained differences.
- `l2c/pipeline.py`: shared orchestration and private artifacts.
- `l2c/reporting.py`: PDF report generation.
- `l2c/synthetic.py`, `tests/`: examples authored without sponsor drawing content.

The code is distributed under AGPL-3.0-only; see LICENSE. Sponsor documents and derived real outputs are not licensed for redistribution by this repository.

## Prepare an offline installation

On a connected machine with the same OS, architecture and Python version as the judge's machine, prefetch the pinned wheels before introducing confidential data:

```powershell
python -m pip download --only-binary=:all: -r requirements-lock.txt --dest ../l2c-offline-wheels
```

On the offline machine, create the isolated environment and install using only that local wheel directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links ../l2c-offline-wheels -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

The RapidOCR wheel includes the documented ONNX models. Prefetching is a dependency-download step, not permission to upload documents. The verified environment for this package is Windows/Python 3.12; another platform needs a compatible wheel set and its own installation check.

# Validation scope and unresolved capability

The package is a local prototype. **Zero real plan/shop associations were confirmed in the preserved first pass. Technical acceptance remains incomplete.**

The first pass processed four supplied projects: 141 PDFs and 611 drawing pages. It exported 162 schema-valid records and 187 PDF reports. Five element families were represented, but this is not evidence of comprehensive extraction. All 144 supplied files, including instructions and the workbook, remained byte-identical to the selected archive.

Eight OCR pages returned 2,060 text regions and zero accepted structured records. A further 332 pages were deferred by the initial budget or the memory reserve. No precision, recall or jury score is claimed. Eighteen source-text anchoring samples passed mechanical overlap checks; no independent semantic review is claimed. Six workbook rows remain candidate references, not exhaustive ground truth.

Baseline runtimes were 8.490 s for CLP, 126.291 s for EspCa3B with eight OCR pages, 10.250 s for LIGREP and 8.649 s for WP2. These measurements include incomplete coverage and are not guarantees for a new project. The baseline real notebook took 10.650 s; a later final-code CLP notebook took 11.670 s. The executed public synthetic notebook took 2.085 s.

WP2 was reserved until the baseline-2 code/parameters were frozen. Its initial result included 72 deferred OCR pages. That result is retained. Later changes are post-evaluation development; they do not create a new independent held-out result. The actual fifth jury project has not been received.

The final code passed 61 authored synthetic tests in 1.618 s on the verified environment. They cover units, unknown attributes/context, repeated annotations, partial scopes, explicit table axes, schema and coordinate bounds, bad inputs, output protection and memory deferral. The default synthetic fixture produces 22 records, five compliant comparisons, five quantity differences, one missing and one added case in an intentionally complete artificial scope.

The local OCR recovery test used one synthetic raster page and one native page: six records and all four expected verdict categories. This is functional evidence on a controlled fixture, not measured accuracy on sponsor drawings.

The public repository includes no sponsor PDFs, workbook values, extracted real records, crops or real reports. Detailed real artifacts and review tasks are retained locally for an authorized private jury route. Native layout coverage, verified association quality and completion of deferred OCR remain substantive work.

# support-word-file-input

## Goal

Allow Word documents to be audited when passed as the direct positional input file, not only when included inside a directory audit.

## What I Already Know

* Directory audits already scan and extract `.docx` through `find_project_files()` and `extract_text_from_file()`.
* Direct single-file audits currently enter the "single file" branch and fall back to PDF extraction when MinerU is not used.
* The optional dependency is `python-docx`, which supports `.docx`; the project does not currently include a binary `.doc` extraction dependency.

## Requirements

* A direct `.docx` input should use `extract_text_from_file()` and continue through the normal audit pipeline.
* Direct `.docx` input should produce meaningful extraction metadata, including `input_type=file`, `extraction_method`, `total_chars`, and file size.
* Direct `.docx` input should not trigger MinerU preflight.
* Direct unsupported Word legacy `.doc` input should fail clearly with hints to convert to `.docx` or PDF, rather than being processed as a PDF.
* Existing PDF behavior must remain unchanged.
* README/CLI docs should describe direct Word `.docx` file input accurately.

## Acceptance Criteria

* [x] Unit test proves direct `.docx` input uses the generic file extractor rather than PDF extraction.
* [x] Unit test proves direct `.doc` fails with a clear unsupported-input diagnostic.
* [x] Existing directory `.docx` behavior remains unchanged.
* [x] Full `tests/test_core.py` passes.
* [x] `paper_audit.py` and `veritas/legacy.py` compile.

## Out of Scope

* No new dependency for legacy binary `.doc`.
* No LibreOffice/antiword conversion pipeline.
* No changes to MinerU extraction behavior for PDF input.

## Technical Notes

* Likely code path: `run_audit()` stage 1 single-file branch in `veritas/legacy.py`.
* Reuse `extract_text_from_file()` instead of duplicating Word parsing.
* Existing README already claims file path supports Word; make `.docx` explicit where needed.

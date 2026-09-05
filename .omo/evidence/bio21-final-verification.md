# BIO-21 final verification

Date: 2026-09-05
Repository: `/Users/taeheon/dev/bio`

## Source bytes

- Existing local source archive: `/private/tmp/bioml-pancreas-bio21/scRNAseq_Benchmark_datasets.zip`
- `stat` observable: 3,671,466,589 bytes (the pinned provider size).
- `sha256sum` observable: `038d0a61ed3891c3d5f4ebd1dab5956465223e38b89859e1bf4792a9aeffbf06`.
- `md5` observable: `b799a660b8bcaf5f3580a9b6f9372e5b`.
- Verified cache: `/private/tmp/bioml-pancreas-bio21/cache/sha256/03/038d0a61ed3891c3d5f4ebd1dab5956465223e38b89859e1bf4792a9aeffbf06/`.
- `cmp -s /private/tmp/bioml-pancreas-bio21/scRNAseq_Benchmark_datasets.zip /private/tmp/bioml-pancreas-bio21/cache/sha256/03/038d0a61ed3891c3d5f4ebd1dab5956465223e38b89859e1bf4792a9aeffbf06/blob` returned `archive/cache bytes identical`.
- Cache contained only the verified `blob` and `manifest.json`; the archive is outside Git.
- Existing artifact `/private/tmp/bioml-pancreas-bio21/archive-integrity.txt` records `No errors detected in compressed data` for the ZIP.
- Provider identity and checksums are also recorded in `docs/evidence/pancreas-zenodo-3357167-metadata-v1.json`.

## Verification invocations and observables

| Criterion | Invocation | Observable |
| --- | --- | --- |
| Unit archive source/cache/inspection behavior | `uv run pytest tests/test_pancreas_archive.py tests/test_pancreas_live_metadata.py tests/test_bio33_metadata_concordance.py` | `6 passed, 1 skipped` (live test skipped without opt-in) |
| Real archive metadata concordance | `BIOML_RUN_LIVE_PANCREAS=1 BIOML_PANCREAS_DATA_DIR=/private/tmp/bioml-pancreas-bio21/cache BIOML_PANCREAS_ARCHIVE=/private/tmp/bioml-pancreas-bio21/scRNAseq_Benchmark_datasets.zip uv run pytest tests/test_pancreas_live_metadata.py` | `1 passed in 4.66s`; whole-cohort and four-label held-out test metadata matched package expectations |
| Full project regression | `uv run pytest` | `418 passed, 2 skipped in 5.72s`; skips are opt-in live Pancreas/TMS checks |
| Lint | `uv run ruff check .` | `All checks passed!` |
| Type checking | `uv run basedpyright` | `0 errors, 0 warnings, 0 notes` |
| Patch whitespace | `git diff --check` | zero output, exit status 0 |

The ZIP was inspected without extraction by `inspect_pancreas_archive()`. The
inspection opened the four fixed `Labels.csv` members and matrix headers under
`Intra-dataset/Pancreatic_data/`, normalized Muraro `pp` to `gamma`, and compared
the resulting whole-cohort and four-label held-out counts with the publication
metadata.

BIO-21 intentionally stops at provider fetch/cache, exact source verification,
raw archive schema inspection, and metadata verification. It does not register
the archive in `load_dataset()` or implement canonical materialization/splits.

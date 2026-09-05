# Protocol inspection

`inspect_protocol()` is a read-only preflight surface: it resolves a registered
dataset snapshot, task, and split protocol without downloading an artifact,
preparing data, assigning rows, fitting preprocessing, or evaluating a model.

```python
import bioml_data as bio

report = bio.inspect_protocol(
    "tms-aorta",
    task="cell-type-annotation-v1",
    protocol="animal-held-out-v1",
)
print(report.to_text())
print(report.to_json())
```

The equivalent CLI command emits a compact explanation by default and the exact
same canonical JSON with `--json`:

```console
bioml-data inspect tms-aorta \
  --task cell-type-annotation-v1 \
  --protocol animal-held-out-v1 \
  --json
```

The report always states the exact dataset snapshot, upstream source URI, task,
artifact scope, protocol, evidence basis and citations, split strategy,
grouping column, leakage unit, held-out axis, deployment target, lifecycle, and
canary usage. Its protocol-readiness field remains `unresolved`: it is not a
dataset-support decision and must not be inferred from lifecycle or a successful
canary. Use the separate typed support gate for that decision:

```python
report = bio.assess_dataset_readiness("tms-aorta")
assert report.verdict is bio.ReadinessVerdict.READY_WITH_QUALIFICATIONS
```

The report lists every source/checksum, rights, canonical-schema, task,
deterministic-preparation, split, evaluation, and metadata-concordance field as
`satisfied`, `missing`, `failing`, or cited `qualified`; no composite score is
used. A missing or failing field blocks readiness. A cited qualification remains
visible and does not change the catalog lifecycle. It also
describes the executable allocation rule rather than a
separate prose copy: for `animal-held-out-v1`, group IDs are ordered by the
SHA-256 digest of `seed + NUL + group_id`, with group ID as the deterministic
digest-collision tie-break. The requested group allocation is 80%/10%/10%
train/validation/test; the implementation allocates at least one group to each
partition, takes weighted floors, and distributes remaining groups by largest
remainder with train/validation/test index tie-break.

The report says that validation is present for this package-defined TMS split,
that each `donor_id` must occupy exactly one partition, and that feature
selection is fitted from train rows only. It does not claim that the split is a
literature reference, a universal recommendation, or a model-performance
baseline.

To render results that have already been produced, attach them explicitly. This
does not run the pipeline. Attachments are always caller-supplied. For a split
receipt, inspection replays the registered deterministic allocation from the
receipt's group IDs and seed, and checks unique observation IDs, declared
fractions, group/observation counts, one-group-one-partition, and partition
counts. It does not reopen the canonical prepared dataset, so it does not prove
the receipt's rows, grouping metadata, or lineage are authentic. The rendered
assignment is therefore receipt-reported and structurally validated, not a
trusted-producer assertion. Its JSON and human output make this boundary
machine-readable with `caller_supplied=true` and
`validation_scope=protocol-contract-and-internal-consistency-only`.

Every concordance attachment must include its matching assignment receipt.
Inspection checks its assignment identity and structural partition metadata
(coverage, group IDs, held-out IDs, and cross-partition groups). Its
`MATCH`, `MISMATCH`, and `NOT_REPORTED` outcomes, observed values, and
publication evidence remain `caller-supplied-unverified`: inspection does not
recompute them without the canonical prepared dataset and registered
expectations. BIO-29's execution/generation path is the scientific verification
boundary. Concordance output likewise states `caller_supplied=true` and
`validation_scope=structural-receipt-binding-only; outcomes-not-recomputed`.

```python
report = bio.inspect_protocol(
    "tms-aorta",
    task="cell-type-annotation-v1",
    protocol="animal-held-out-v1",
    request=bio.ProtocolInspectionRequest(
        assignment=split_receipt,
        concordance=concordance_report,
    ),
)
```

No plan-time report invents a held-out animal, fold, validation partition, or
metadata-concordance outcome. Those fields remain absent until a caller supplies
an attachment that passes this bounded structural validation.

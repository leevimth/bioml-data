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
canary usage. It separately states readiness: the current TMS value is
`unresolved`, because BIO-31 owns the support-readiness evaluation and the
package must not infer support from lifecycle or a successful canary. It also
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
does not run the pipeline; it validates the receipt identity and contract before
showing actual held-out group IDs, partition observation/group counts, and any
cross-partition groups. When both are supplied, their assignment identities must
be exactly equal. A supplied concordance report contributes its canonical hash
of the complete scoped report and exact `MATCH`, `MISMATCH`, and `NOT_REPORTED`
counts.

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
metadata-concordance outcome. Those fields remain absent until a verified
realized receipt is supplied.

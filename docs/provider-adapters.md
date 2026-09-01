# Provider adapter boundary

Provider adapters answer where and how bytes were acquired. Dataset snapshots
and scientific transform protocols answer what data and preparation contract an
experiment used. These identities stay separate so an equivalent canonical
artifact can move between providers without changing its scientific settings.

Each adapter is passed explicitly to `acquire_provider_artifact` together with
the expected `ScientificArtifactIdentity`; the package does not discover plugins
at runtime. The boundary requires the adapter to declare the same dataset,
content address, and transform protocol, then verifies the returned receipt
against that target. An adapter exposes a static `ProviderDescriptor` and
returns its own native receipt type. Native fields such as a Figshare article ID
or a provider object key remain available on that receipt rather than being
collapsed into a lowest-common-denominator mapping.

The resolved result carries both layers:

- `ScientificArtifactIdentity`: dataset snapshot, content-addressed artifact,
  and canonical transform protocol, independent of storage provider;
- the provider-native receipt: provider descriptor, verified local artifact,
  and provider-specific acquisition metadata.

Two providers resolve to the same scientific artifact identity only after they
produce the same verified canonical bytes under the same transform protocol.
Different raw packaging therefore remains distinct until a deterministic
canonical transform proves equivalence.

Provider SDK dependencies belong to provider-specific optional dependency
groups. The core boundary imports only standard-library and internal contract
types. It does not implement a generic hosting, mirroring, or cache framework;
adapters should reuse the provider's established acquisition facilities.

The existing TMS Aorta compatibility download uses the Figshare descriptor
`figshare / verified-http-v1`. `DatasetDownloadReceipt` retains the exact
`DatasetDownloadPin` alongside the content-addressed artifact and download
outcome, so its provider-native provenance remains inspectable without changing
the existing `download_dataset()` call. Receipts manually constructed through
the older two-field `(artifact, outcome)` API remain valid, but provider access
raises an explicit provenance-unavailable error rather than inventing a pin.

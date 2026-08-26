# Scanning and Result Semantics

## Repository Discovery and Tag Processing

Repository discovery and image scanning are separate operations:

1. a registry import or JFrog discovery creates `Repository` records;
2. a repository scan lists and selects tags;
3. tag processing resolves an artifact and queues its scan pipeline;
4. Syft and Grype results are parsed and stored.

`Periodic Repository Scan` performs step 2 for every active repository. JFrog discovery does not list tags and does not scan images.

## Docker Scan Flow

For a selected Docker tag, HITrack:

1. resolves the image reference and available manifest metadata;
2. reuses an already completed matching image when possible;
3. otherwise creates or resumes an `Image` and `ScanRun`;
4. checks for the exact reference in the Docker daemon visible to the worker;
5. pulls the image when it is not available locally;
6. runs Syft and stores the raw SBOM;
7. stores components, versions, image-specific contexts, and locations;
8. runs Grype and stores its raw result;
9. maps findings, fix metadata, and image summaries into the database;
10. immediately queues enrichment for newly persisted CVE/GHSA identifiers;
11. updates image, tag, and repository states.

The local-image check is exact. A locally built `local/app:1.0` does not satisfy a scan for `registry.example/local/app:1.0` unless that second reference is also tagged in the same Docker daemon.

## Helm Scan Flow

For a Helm tag, HITrack resolves the chart and extracts child image references. Each child image uses the normal Docker scan flow.

Image resolution attempts the original chart reference and normalized same-registry candidates before trying registry-level fallback entries. A completed parent Helm task means its child image work was queued or resolved; inspect the child tasks and tag state for the final result.

## Scan States

The main scan states are:

| State | Meaning |
| --- | --- |
| `pending` | Work is queued or waiting to start. |
| `in_process` | A worker currently owns active work. |
| `success` | The required processing for that record completed. |
| `error` | Processing failed; inspect the task result and worker logs. |

Celery orchestration tasks often finish immediately after queueing child tasks. Their successful result is not proof that the child scan succeeded. Follow the returned child task IDs and the final `RepositoryTag`/`Image` state.

`ScanRun` also stores an idempotency key, attempt count, lease, task ID, and scanner/policy versions so retried or repeated work can be distinguished from a new logical scan.

## Findings and Unique Vulnerabilities

The image page deliberately exposes two counting modes:

- **Findings** count affected component-version occurrences. The same vulnerability can appear more than once when it affects multiple packages or package versions in the image.
- **Unique vulnerabilities** count distinct non-empty vulnerability IDs, such as one CVE ID, across the selected findings.

Therefore the findings total can be greater than the unique-vulnerability total. Neither number is inherently a duplicate count.

Severity totals use these buckets:

```text
CRITICAL, HIGH, MEDIUM, LOW, NEGLIGIBLE, UNKNOWN
```

Any unrecognized or missing severity is included under `UNKNOWN`. For the selected counting mode, the displayed total must equal the sum of all six severity buckets. Switching to unique mode changes both the total and the severity series to the unique-ID calculation.

When the same unique vulnerability occurs with different severities, the current summary assigns it the severity from its first stored finding. Occurrence-level mode retains the severity of every finding.

## Ecosystem Breakdown

The image summary groups findings by the Syft/Grype artifact type:

- `deb`, `rpm`, `apk`, and `alpm` are grouped as **OS packages**;
- Python/pip, Java, Node.js/npm, Go, Ruby, .NET, Rust, PHP, and other known types use their ecosystem labels;
- missing types are grouped as **Unknown / other**;
- unrecognized non-empty types remain visible under a generated label.

Every finding belongs to exactly one breakdown row. Its finding totals therefore add up to the overall occurrence-level total.

## Fix Availability

HITrack treats a finding as immediately fixable only when Grype supplies at least one non-empty fixed version for that exact component/vulnerability match. A textual fix state without a usable version is not counted as fixable now.

The image summary distinguishes:

- **Fixable findings**: individual findings with at least one fixed version;
- **Fully fixable components**: affected component identities for which every stored finding in the image has at least one fixed version;
- **Fully fixable findings**: findings belonging to those fully fixable components.

At vulnerability level, one vulnerability can have these aggregate states:

| State | Meaning |
| --- | --- |
| `available_all` | Every occurrence has a fixed version. |
| `available_partial` | Only some occurrences have a fixed version. |
| `not_fixed` | Grype reports no fix for the occurrences. |
| `wont_fix` | All reported fix states are `wont-fix`. |
| `version_unknown` | A fixed state is reported without a usable version. |
| `unknown` / `unavailable_mixed` | The available scanner data is insufficient or mixed. |

Other analytics views use normalized component-level states such as `available`, `not_in_repo`, `not_fixed`, `wont_fix`, `version_unknown`, and `unknown`. Read the label and denominator shown by the specific page; a package-manager candidate check and a raw Grype fixed-version result answer related but different questions.

## Stored and Derived Data

HITrack keeps raw SBOM and Grype payloads as well as normalized database records. Image summary fields are derived from image-scoped component/finding relationships and may be persisted to keep the detail page fast.

After upgrading code that changes summary or fix semantics, run the documented backfill or recalculation command once for historical images. New scans calculate the current schema during normal processing.

Useful maintenance operations are listed in [Periodic Tasks](periodic-tasks.md) and [Operations and Deployment](operations.md).

## Rescan Versus Recalculation

- A **rescan** runs scanner work again and can use newer scanner databases or image contents.
- `Recalculate Vulnerability Fix Availability` reparses stored Grype matches and does not contact a registry or rescan an image.
- image summary backfill rebuilds persisted summary fields from stored relationships/raw results.
- vulnerability enrichment updates advisory intelligence; it does not change which packages Grype found in an image.

## Troubleshooting a Scan

Check current task and worker output:

```bash
docker compose logs --since=30m worker-light worker-scan worker-enrichment
```

For a failed or unexpectedly short repository action, verify:

1. the repository is active and linked to a registry;
2. the tag-selection policy actually selected a tag;
3. the parent result contains child task IDs;
4. the final tag and image states, not only the parent task state;
5. registry read permissions and the exact image reference;
6. Syft/Grype output and available disk/memory;
7. whether a matching scan was reused by idempotency/deduplication.

For a historical counter mismatch, rebuild image vulnerability summaries using the command in [Operations and Deployment](operations.md), then reload the image page.

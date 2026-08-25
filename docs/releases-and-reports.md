# Releases and reports

A `Release` groups repository tags through explicit assignments. This lets analysts inspect exposure for a business release even when it contains several repositories or image tags.

## Recommended workflow

1. Create a release with a stable organization-wide name.
2. Assign repository tags only after tag discovery.
3. Queue scans for missing or stale images.
4. Wait for child scan tasks to complete.
5. Validate coverage on **Prioritization**.
6. Generate the report.

Reports are based on stored data at generation time. Pending, failed or missing scans can make a report incomplete; a successfully queued parent task is not proof that every child scan succeeded.

Release counts in prioritization represent how many release assignments are reached through affected image tags. They help distinguish a widespread dependency from a finding isolated to one non-release image.

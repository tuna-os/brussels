# Auto-QA tuning policy

`.github/auto-qa-tuning.json` defines the initial Auto-QA policy for ACMM
`acmm:auto-qa-tuning`. It is a declarative policy only: no workflow currently
consumes it or changes CI settings automatically. A future tuner can use it to
propose timeout updates for the plain and LUKS install jobs.

Use successful, first-attempt runs on `main` from the last 30 days, separating
samples by workflow, job and runner. Exclude pull requests, reruns, failed,
cancelled and skipped jobs so untrusted or incomplete runs cannot lower the
budget. Keep the current value when fewer than 20 eligible samples exist.

For each target, compute the nearest-rank 95th percentile of job duration
(excluding queue time), multiply by 1.5, and round up to five minutes. Clamp
the result to 60–180 minutes, then limit movement to 10% of the current timeout
per proposal. Apply the change limit last; if rounding or the absolute bounds
would require a larger change, keep the current value for maintainer review.
Read the current timeout from the target workflow rather than duplicating it
in this policy. Both jobs currently allow 120 minutes.

Any proposed change must include the source run IDs, sample count, percentile,
current timeout and proposed timeout in a reviewed PR. Maintainers should check
for runner or workload changes before accepting it. Required checks, test
assertions, security scans and workflow permissions are outside the tuning
scope. Timeout or failure spikes require investigation rather than automatic
relaxation of quality gates. Revert the workflow timeout change to roll back;
this policy itself does not grant write permissions or enable a scheduled job.

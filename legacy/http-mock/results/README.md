# Synthetic workflow results

These are selected historical results for the synthetic-score HTTP prototype. They do not measure real image inference.

| File | Scope |
|---|---|
| [engine-tests.json](engine-tests.json) | 15 engine unit checks |
| [workflow-unit.json](workflow-unit.json) | 98 offline workflow checks, including simulated timeout behavior |
| [python-workflow-http.json](python-workflow-http.json) | 93 checks through actual Python HTTP |
| [python-ramp-v2.json](python-ramp-v2.json) | Bounded 10,000-record synthetic load |
| [build-validation.json](build-validation.json) | Generated-flow validation |
| [verification-summary.json](verification-summary.json) | Summary and evidence qualifications |

Browser HTTP v2 was reported as 94 passing checks in a user-provided screenshot; no corresponding exported browser-v2 JSON is included here. Python and browser assertion grouping differs. The Python unit suite had four passing tests.

## Load-test interpretation

| Target records/s | Records | Duration, s | Observed records/s | Median / p95 ms per request |
|---|---:|---:|---:|---:|
| 100 | 1,000 | 9.01 | 111.03 | 4.87 / 14.75 |
| 500 | 3,000 | 5.80 | 516.88 | 4.43 / 6.08 |
| 1,000 | 6,000 | 5.91 | 1,015.88 | 4.23 / 5.53 |

The recorded load used batches of 100, concurrency one and ten synthetic sources on one machine. All 10,000 records were accepted without unexpected errors. Latency is per request, not per record. The immediate first batch explains observed rates slightly above the configured targets.

These numbers do not establish maximum capacity, long-duration stability or AI image throughput.

## Your own results

Follow the [walkthrough](../README.md) and save new traffic outputs under a distinct filename such as `my-ramp.json`. Some test scripts overwrite fixed result filenames; back up baseline files before comparing runs.

A blocked socket or unavailable endpoint is not a passing test. Deliberate malformed data is a passing case only if its expected error is asserted. Some historical descriptive labels remain in Vietnamese to preserve the original record; numerical evidence is not reclassified by this documentation update.

[Current model evidence](../../../reports/evidence/README.md)

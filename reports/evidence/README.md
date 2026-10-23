# Experimental evidence

These files describe selected recorded experiments. They are review material, not application configuration to copy blindly into a new run.

## Model evidence

| File | What it records |
|---|---|
| [results.json](results.json) | Aggregate confusion counts, metrics, timing scope and environment |
| [threshold.json](threshold.json) | Raw decision threshold and calibration rule |
| [manifest.json](manifest.json) | Fit/calibration/test membership and official split hash |
| [calibration.json](calibration.json) | Normal calibration scores |
| [test-predictions.json](test-predictions.json) | Per-image scores, labels and decisions |
| [verification-summary.json](verification-summary.json) | Selected verification details and artifact identification |
| [source-manifest.json](source-manifest.json) | Source/evidence hashes from the earlier repository-reorganization snapshot |
| [reorganization-checks.json](reorganization-checks.json) | Checks recorded for that folder reorganization |

The original training result's `node_red_connected: false` describes training-time status; later integration is recorded separately. Do not edit old measurements just to match a later system state.

The source manifest is historical. Updated README files need not match its earlier hashes; it is not a current whole-repository integrity guarantee.

## Integration evidence lives with the demo

- [Local checkpoint verification](../../demo/local-verification.json): selected scores and invalid-image handling; no HTTP claim.
- [Python HTTP verification](../../demo/http-verification.json): real-model integration checks.
- [UI deployment verification](../../demo/ui-deployment.json): source matching and preserved alerts; not full browser interaction coverage.
- [Verification summary v2](../../demo/verification-v2.json): recorded scope and outstanding checks.

[Synthetic HTTP results](../../legacy/http-mock/results/README.md) belong to a different test path.

## Interpreting results

AUROC measures ranking across thresholds. Recall/F1/confusion counts depend on the chosen threshold. Precision of 100% on this finite set does not guarantee future performance. GPU inference time, browser end-to-end time and synthetic HTTP batch throughput have different measurement scopes.

No pixel-level model metrics are reported. Database reopening is not a full process-restart recovery test. Expected validation errors in a test are not unexpected production failures.

When running again, retain your own output directory and identify hardware, versions, split, threshold and test scope. Do not overwrite published baseline evidence and continue labeling it as the original experiment.

[Report index](../README.md) · [Implementation report](../IMPLEMENTATION_REPORT.md)

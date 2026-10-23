# Reports

Start with [PCB4 Anomaly Monitoring: Implementation and Evaluation](IMPLEMENTATION_REPORT.md), the English individual report for Tran Long Giang's implementation.

The report covers:

- The locally fitted VisA PCB4 baseline and its evaluation protocol.
- Model-to-Node-RED integration and the HTTP contract.
- Persistent alerts, duplicate detection and acknowledgment.
- The Inspect interface and deployment safeguards.
- Completed checks, evidence limitations and remaining milestones.

Related group model code is acknowledged in the report's references. External benchmark numbers are not claimed as reproduced results.

## How to read the evidence

Read the [evidence guide](evidence/README.md) before interpreting JSON files. Model accuracy, HTTP workflow correctness and UI/recovery checks are separate kinds of evidence. A 10,000-record synthetic load is not an image-inference benchmark.

The recorded model has 94.11% image AUROC but 31% recall at its selected threshold. Use the confusion counts and threshold context, not AUROC alone, when describing effectiveness.

## Reproduce instead of assuming

Follow [model setup](../model/README.md) and [demo setup](../demo/README.md) to run your own experiment. Save your run's checkpoint, threshold, split manifest, predictions, metrics and environment together. A changed checkpoint or threshold is a new experiment, not automatically the same result.

Published JSON files describe the recorded experiments. Documentation updates do not rerun those experiments or certify a clean-machine installation.

## Separate academic deliverables

The academic PDF and editable LaTeX source are delivered separately and are not stored in this repository. They can link to the source and evidence here. When citing a stable version, use GitHub's commit-specific file link rather than relying only on the changing main branch.

[Project overview](../README.md) · [Evidence files](evidence/README.md)

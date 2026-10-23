# PCB4 Anomaly Monitoring: Implementation and Evaluation

**Author:** Tran Long Giang · Computer Engineering · Group 1  
**Project:** Industrial AI Monitoring Framework  
**Experimental evidence cutoff:** 22 October 2026  
**Report revision:** 23 October 2026  
**Scope:** Individual implementation report; research prototype, not industrial acceptance certification.

## Abstract

This work implements a local image-to-alert pipeline for printed circuit board anomaly monitoring. It connects a Python inference service, Node-RED routing and threshold rules, transactional SQLite storage and the Inspect web interface. A separately fitted VisA PCB4 baseline replaces the earlier synthetic inputs with real image scores. Image AUROC is 94.11%, but the selected operating threshold detects only 31 of 100 anomalous test images. The workflow supports duplicate detection, conflict errors, persistent alerts and idempotent acknowledgment. These results demonstrate integration feasibility while leaving detection-quality and operational-validation work open.

## 1. Objectives and individual contribution

The immediate objective was to implement the supervisor's proposed sequence: sample image, reusable model block, threshold rule, event and local web interface.

Giang's implementation covers:

- The HTTP input/output contract and adapter between model inference and Node-RED.
- Local preparation and execution of the PCB4 baseline.
- Validation, threshold decisions, duplicate handling and record-conflict detection.
- Alert creation, acknowledgment and transactional SQLite persistence.
- The Inspect interface, source-generated Node-RED flow and deployment safeguards.
- Unit checks, controlled HTTP tests and selected experimental evidence.

The evaluated checkpoint was fitted locally for this implementation. No trained checkpoint was supplied by a teammate. External benchmark numbers are not presented as reproduced results. Related model-code attribution is consolidated in the references.

## 2. Dataset and evaluation protocol

The experiment uses **VisA, category pcb4**, from Amazon Science. This is distinct from the Peking University PCB Defect Dataset. Preparation follows the official `split_csv/1cls.csv`. Validation read 1,105 images and 100 masks without detecting corrupt images or empty masks. Original mask values 0-7 were retained; pixel-level performance has not been evaluated.

| Partition | Images | Purpose |
|---|---:|---|
| Fit, normal | 804 | Feature extraction and memory-bank construction |
| Calibration, normal | 100 | Threshold selection |
| Test, normal | 101 | False-alarm evaluation |
| Test, anomaly | 100 | Detection and missed-defect evaluation |

Seed 42 splits the official 904-image normal training partition into fit and calibration subsets. The original test partition is retained. Test labels did not determine the initial threshold. Since the test results have now been inspected, subsequent model selection must use a separate validation protocol or clearly identify results as exploratory.

Evidence: [split manifest](evidence/manifest.json), [calibration scores](evidence/calibration.json), [test predictions](evidence/test-predictions.json).

## 3. Model and environment

The model is a PatchCore-style ResNet18 baseline using pretrained `layer2` and `layer3` features, nine neighbors, 256 x 256 resizing and one ImageNet normalization step. Fitting constructs a memory bank; it does not update backbone weights through backpropagation.

Seeded random-priority sampling retains at most 2,000 patch vectors, with fit batch size 8. This bounded random bank is **not canonical greedy coreset selection**. Original 1358 x 1104 images are resized to a square; possible detail loss and aspect-ratio effects have not been isolated experimentally.

The tested environment is Windows, Python 3.11.9, PyTorch 2.6.0+cu124, torchvision 0.21.0+cu124, anomalib 2.2.0 and NVIDIA GeForce RTX 4060. The custom `model.pt` stores model state and configuration; it is not a Lightning checkpoint compatible with an unrelated loader.

The raw threshold is **14.64073657989502**, the 99th percentile with `higher` interpolation over 100 normal calibration scores. This rule does not guarantee a 1% operational false-alarm rate.

## 4. Results and error analysis

Run identifier: `visa-pcb4-20261022-213717`. Source: [results.json](evidence/results.json).

| Measure | Observed value |
|---|---:|
| Image AUROC | 94.11% |
| Precision at the selected threshold | 100.00% |
| Recall at the selected threshold | 31.00% |
| F1 | 47.33% |
| Fit time | 17.17 s |
| Inference median / p95 | 25.03 / 27.39 ms per image |
| Image loading + preprocessing + inference median | 42.39 ms per image |

| Ground truth | Below threshold | Alert | Total |
|---|---:|---:|---:|
| Normal | 101 TN | 0 FP | 101 |
| Anomaly | 69 FN | 31 TP | 100 |

AUROC measures ranking across thresholds, not the proportion of anomalies detected at one threshold. Operational recall is only 31%. A below-threshold result therefore must not be interpreted as a defect-free PCB. Precision of 100% describes this finite test set, not future deployment performance.

| Example under pcb4/Data/Images | Raw score | Observed decision |
|---|---:|---|
| Normal/0011.JPG | 12.4063 | Correctly below threshold |
| Anomaly/009.JPG | 14.8036 | Correct alert |
| Anomaly/000.JPG | 12.5620 | Missed anomaly |

Checkpoint reload checks reproduced these baseline scores. Including a missed anomaly avoids presenting only successful examples.

Threshold selection, resizing and bank representativeness are hypotheses for investigation, not established causes. **No model-improvement experiment has been completed.** The warmed batch-one inference benchmark includes GPU completion. Web-request timing additionally includes image-map generation, HTTP and storage and is not equivalent to inference-only timing.

## 5. Architecture and data contract

The browser submits an image to Node-RED, which calls the loopback Python model service, validates the returned score and applies the threshold. Node-RED forwards the decision to transactional storage and responds only after a successful commit. Processing failures remain explicit errors and are never converted into normal decisions.

| Boundary | Contract or responsibility |
|---|---|
| Browser to Node-RED | JPEG/PNG base64, record_id and UTC timestamp; up to 5 MB |
| Model output | Raw score/threshold, model version, image SHA256, processing time, heatmap and overlay |
| Decision | alert when raw score is greater than or equal to threshold; otherwise normal |
| Persistence | Canonical payload fingerprint, result, alerts and source watermark |
| Interface | Decision, raw score, threshold, timing, image comparison and alert lifecycle |

The demo prefix is `/giang-pcb4/v1`, with `/demo`, `/infer`, `/health`, `/alerts` and `/ack`. Python binds to `127.0.0.1:1891`; Node-RED checks loopback clients. The timestamp is submission time, not a verified camera capture timestamp. Inference is serialized; this prototype is intended for one user and small requests.

The adapter transforms raw distance s and positive threshold t into `s/(s+t)`. Threshold 0.5 preserves the raw decision `s >= t`. Neither score is a defect probability. Heatmaps are normalized per image for visualization and are not validated segmentation masks.

## 6. Alert lifecycle and persistence

| Condition | Behavior |
|---|---|
| Valid normal record | Store result without an alert |
| Score meets/exceeds threshold | Create one pending alert |
| Identical record retry | Return duplicate without another alert |
| Reused ID with different content | Return conflict |
| First acknowledgment | Mark acknowledged and record its time |
| Repeated/concurrent acknowledgment | Preserve the first acknowledgment time; no additional change |
| Unknown alert ID | Return an explicit not-found error |
| Invalid input, model or storage failure | Return error; never infer normality |
| Storage capacity reached | Reject without silently evicting pending alerts |

SQLite stores records, fingerprints, alerts and source watermark. Limits are 20,000 alerts and 100,000 records, without automatic TTL or archiving. Acknowledgment does not free capacity. Stale and out-of-order records are rejected; identical retries are checked before staleness.

RAM-v1 migration preserves exported alerts and acknowledgment state. Legacy records lacking a complete image fingerprint reserve their IDs and return a dedicated retry error. The previous normal-record deduplication cache is not migrated. Startup refuses to silently create an empty database when an existing persistent flow indicates missing storage.

Database reopening, backups and transaction rollback have been tested. A full process stop/start recovery exercise remains outstanding. Database tests alone do not prove recovery of the entire running system after a crash.

## 7. Interface and deployment

Inspect separates image inspection, alert management and model information. It includes drag-and-drop input, original/heatmap comparison, overlay, zoom, decision labels, counters, filters, search, pagination, acknowledgment and JSON export. Text and icons accompany colors. Result guidance and model information explain the baseline limitations.

Source generators keep the importable flow synchronized with HTML and processing code. Deployment scripts back up flows, check IDs and route collisions, use revision-aware updates and preserve unrelated flows. The UI-only updater changes the HTML-serving function without restarting inference.

English localization is being applied to documentation and presentation text while retaining API identifiers and decision semantics. Historical verification files describe their original runs; translating labels does not constitute a new HTTP test. See the [localization status](LOCALIZATION_STATUS.md) for the exact published/local distinction.

## 8. Verification and evidence levels

| Layer | Recorded result | Evidence or limitation |
|---|---|---|
| Real checkpoint | Three scores reproduced; invalid image rejected | [Local verification](../demo/local-verification.json) |
| SQLite unit checks | Seven groups passed | [Storage tests](../demo/test_storage.py): concurrent retry/ACK, capacity, migration, backup, reopen and rollback |
| Real-model Python HTTP | Passed | [HTTP verification](../demo/http-verification.json): health, decisions, duplicate, ACK and intentional errors |
| Prior UI deployment | Source matched; alerts preserved; model ready | [UI deployment](../demo/ui-deployment.json); not full browser interaction coverage |
| Synthetic engine / offline workflow | 15 / 98 checks passed | [Legacy results](../legacy/http-mock/results/) |
| Synthetic Python unit / HTTP | 4 / 93 checks passed | Separate from image inference |
| Synthetic browser HTTP | 94 checks reported in user screenshot | No exported browser-v2 JSON in shared evidence |
| Full service restart | Not completed | Must be exercised explicitly |

During English-localization work, the seven SQLite groups, 15 engine checks, 98 offline workflow checks and four Python unit tests passed again. Python and inline JavaScript syntax checks passed, both flow files were rebuilt, and no broken local Markdown links were found in the staged English version. These checks do not establish a new successful HTTP deployment.

Intentional invalid inputs count as passes only when the expected error occurs. Successful historical HTTP runs came from the user's Windows terminal and browser. The assistant environment's WinError 10013 socket restriction is recorded as blocked testing, not a pass.

The earlier synthetic load used 10,000 valid records, batch size 100 and concurrency one:

| Target records/s | Records | Duration, s | Observed records/s | Median / p95 ms per request |
|---|---:|---:|---:|---:|
| 100 | 1,000 | 9.01 | 111.03 | 4.87 / 14.75 |
| 500 | 3,000 | 5.80 | 516.88 | 4.43 / 6.08 |
| 1,000 | 6,000 | 5.91 | 1,015.88 | 4.23 / 5.53 |

No unexpected errors occurred in that recorded run. These are synthetic-score HTTP measurements, **not AI image throughput**.

## 9. Remaining milestones

| Milestone | Status | Next evidence needed |
|---|---|---|
| Dataset and baseline | Completed for VisA PCB4 | Validation-driven recall improvement |
| Image-to-event-to-web integration | Demonstrated locally | Full redesigned-UI and recovery tests |
| Reusable model block | HTTP adapter implemented | Externalized paths/configuration and timeout coverage |
| Threshold configuration and workflow reload | File-based threshold and generated flow available | Controlled configuration-change and clean-import tests |
| Two workflow tools on identical inputs | Not completed | Same model/images through another feasible tool |
| Offline package | Local checkpoint loading implemented | Package dependencies/assets and test without Internet |
| Sensor extension | Synthetic HTTP groundwork only | Sensor contract, MQTT and a real device after model-block validation |

Define validation data and acceptance objectives before tuning bank construction, resolution or threshold policy. Do not tune on the inspected test set and call the result independent evaluation. A working upload demo does not establish camera or sensor performance.

## 10. Conclusion

The implementation demonstrates a local connection between real anomaly inference, Node-RED decisions, persistent alert state and a web interface. Its strongest current evidence concerns integration and alert behavior. Detection quality at the chosen threshold is insufficient for automatic product acceptance. Recovery, tool comparison, complete offline packaging and hardware integration remain open.

## References and attribution

1. [Implementation repository](https://github.com/Cowaiiz/AIOT_Monitoring_workflow): Giang's source and evidence; pre-localization snapshot `6baf757690170470f15470d0ab7c2af5117e4a5b`.
2. [Amazon Science VisA / spot-diff](https://github.com/amazon-science/spot-diff): dataset source and official split. Dataset images are not redistributed here; consult accompanying terms.
3. [Related group baseline by Bao](https://github.com/RoyalB26/AIoT_H261/tree/dbb9e89f3b6feef215f82732cf91407103948510): model-code reference at a pinned commit. Its benchmark numbers are external results, not this implementation's measurements. The evaluated checkpoint was fitted locally by Giang.
4. Supervisor's project brief supplied to Group 1: integration, workflow comparison and sensor-extension requirements. No public URL was supplied.

See [demo instructions](../demo/README.md), [training instructions](../model/TRAINING_README.md) and the [evidence summary](evidence/verification-summary.json). The academic PDF and editable LaTeX deliverables are intended for separate delivery and are not committed here.

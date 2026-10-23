# Inspect: real-image anomaly monitoring

Inspect accepts a PCB4 image, runs a local model and displays its score, heatmap and workflow decision. Alerts are stored in SQLite and can be acknowledged.

**Run commands from the repository root.** This guide assumes you completed [model setup](../model/README.md) and have a compatible completed run. To try only workflow behavior without a model, use the [synthetic demo](../legacy/http-mock/README.md).

## 1. Check prerequisites

You need:

- Node.js and Node-RED installed, with the local Admin API reachable on port 1880.
- The repository's `.venv` with compatible ML dependencies.
- A trusted run folder containing `model.pt`, `threshold.json` and `test-predictions.json`.
- The same dataset images used to generate those predictions.
- A writable checkout for `demo/data`, `demo/backups` and verification files.

The published scripts currently assume the unauthenticated local Node-RED Admin API. If your existing installation requires authentication, the scripts do not yet accept credentials; use an appropriate separate local development setup or implement authentication support. Do not disable security on an existing shared installation.

## 2. Configure your model and dataset paths

The code still has original-machine defaults. Edit these **three locations** before starting on another machine:

| File | Setting to change | Example |
|---|---|---|
| [model_service.py](model_service.py) | `RUN = Path(...)` | `Path('C:/aiot-data/runs/visa-pcb4-YYYYMMDD-HHMMSS')` |
| [start_demo.py](start_demo.py) | `Path('D:/Project/aiot-model/datasets/visa')` in startup verification | `Path('C:/aiot-data/datasets/visa')` |
| [check_local.py](check_local.py) | Dataset `Path(...)` used to open images | `Path('C:/aiot-data/datasets/visa')` |

Replace the timestamp placeholder with the **actual completed run directory**. Do not rename the run to match the example. There is currently no `--run` option or environment-variable override in the service.

Both startup and local checks import RUN from model_service.py. Keep weights, threshold and predictions from one run together. SQLite is independent of the data root: its path is `demo/data/workflow.sqlite3`, relative to the storage module.

## 3. Run offline checks first

```powershell
& ".\.venv\Scripts\python.exe" .\demo\test_storage.py
& ".\.venv\Scripts\python.exe" .\demo\check_local.py
```

Expected:

- Storage tests finish with `OK` for seven test groups.
- The checkpoint check prints `"real_checkpoint_passed": true` and `"invalid_image_rejected": true`.

The checkpoint check reads three examples from your predictions, including a detected and a missed anomaly. If your new model has no such example, the current check can fail during example selection; adapt the test explicitly rather than borrowing unrelated baseline predictions. Cross-device differences can also exceed the strict score tolerance. Investigate before calling the run equivalent.

These checks do not open HTTP sockets. They do not establish successful Node-RED integration.

## 4. Start Node-RED and the model workflow

In terminal A:

```powershell
node-red.cmd
```

Keep it open. If Node-RED is already running on port 1880, reuse that instance rather than starting a second one.

In terminal B, from the repository root:

```powershell
& ".\.venv\Scripts\python.exe" .\demo\start_demo.py
```

This command:

1. Reads existing flows and checks revision, IDs and route collisions.
2. Backs up flows and the workflow database.
3. Loads your local checkpoint and starts Python on 127.0.0.1:1891.
4. Deploys only the PCB4 tab and checks that unrelated flows are unchanged.
5. Exercises health, normal/alert decisions, retry, acknowledgment and intentional errors.

Require `"http_passed": true` before calling startup verification successful. The script can print the page URL even after a failed check, so the URL alone is not a passing result. Inspect `demo/http-verification.json` when a check fails.

Open **http://localhost:1880/giang-pcb4/v1/demo**. Keep both terminals open. Startup creates `verify_` test records and acknowledges its test alert; those records are visible in the alert list.

## 5. Inspect an image

1. Choose or drop one JPEG/PNG from your PCB4 image directory (up to 5 MB).
2. Select the analysis button to create a new inspection record.
3. Compare the original image with its heatmap/overlay and read the raw score against the threshold.
4. Open the alerts view to review or acknowledge a pending alert.
5. Use the retry action to resend the same record without creating another alert.
6. Export JSON if you need the current result and retrieved alert snapshot.

Some currently published interface text may be Vietnamese. For navigation: **Phân tích ảnh** means Analyze image; **Gửi lại cùng bản ghi** means Retry same record; **Xác nhận** means Acknowledge; **Xuất dữ liệu** means Export data. English documentation does not imply that the translated UI has already been deployed.

An alert means the score meets or exceeds the configured threshold. A below-threshold result is not proof of a defect-free board. Acknowledgment means reviewed, not repaired. Heatmaps show relative anomaly intensity and are not validated segmentation masks.

## 6. Update or inspect the flow

After changing `index.html`, while Node-RED and Python are still running:

```powershell
& ".\.venv\Scripts\python.exe" .\demo\update_ui.py
```

Expected: `UI UPDATED`, matching HTML, preserved alerts and a ready model. Refresh the browser. The updater changes only the HTML-serving function and rejects incompatible flow drift.

To generate the import file without deploying:

```powershell
& ".\.venv\Scripts\python.exe" .\demo\build_flow.py
```

Importing `flow.json` alone does not start Python. Avoid importing a second copy over existing HTTP routes. Prefer the startup script for a first deployment and keep the source generator as the source of truth.

## API overview

Prefix: `/giang-pcb4/v1`.

| Method | Route | Purpose |
|---|---|---|
| GET | /demo | Inspect interface |
| GET | /health | Model readiness/version/device |
| POST | /infer | Image base64, record_id and UTC timestamp |
| GET | /alerts | Alert list and counts |
| POST | /ack | Acknowledge an alert_id |

Use a new ID for a new inspection; retain the identical ID, timestamp and content for a retry. Changed content with an existing ID is a conflict. The normalized score `s/(s+t)` has a decision boundary of 0.5; it is not a probability.

## Storage and restart behavior

`demo/data/workflow.sqlite3` stores records, fingerprints, alerts and acknowledgment timestamps. Limits are 20,000 alerts and 100,000 records, with no automatic eviction/TTL. A full store returns an error; acknowledging alerts does not free capacity.

Keep the database and backups. Database reopening was tested, but full service stop/start recovery is still an outstanding acceptance test. Do not synchronize a live SQLite database between machines or overwrite it with a new empty database.

If moving from an earlier `pcb4-demo` checkout, stop activity and the old service before moving storage. Back up and preserve the database and any sidecar files, then compare counts and acknowledgment states after migration. Do not run old and new copies simultaneously. Startup intentionally stops if an existing persistent flow has no database at the new path.

## Troubleshooting

| Symptom | Action |
|---|---|
| Node-RED Admin API unavailable | Check terminal A, port 1880 and authentication compatibility |
| Port 1891 already in use | Find the existing model instance; do not launch another |
| model.pt not found | Correct RUN; complete model fitting first |
| Dataset image not found | Correct both dataset paths in section 2 |
| Persistent flow exists but SQLite is missing | Restore/migrate the correct database; do not bypass the guard |
| Route collision or revision conflict | Inspect current flows and retry after resolving the conflict; do not force overwrite |
| INVALID_IMAGE / model error | Check image format/size and model terminal; never treat the error as normal |
| WinError 10013 | Execution environment blocked the socket; run from a permitted local terminal and report that test separately |
| Capacity error | Preserve the database and plan explicit archival; no automatic cleanup is implemented |

## File guide and evidence

`model_service.py` runs inference; `storage.py` implements transactions; `index.html` is the UI; `build_flow.py` creates the flow; `start_demo.py` deploys and verifies; `update_ui.py` updates HTML.

The included verification JSON files record earlier runs. Your new test commands overwrite some local result files; retain copies if comparing runs. Published measurements and uncompleted checks are explained in the [implementation report](../reports/IMPLEMENTATION_REPORT.md).

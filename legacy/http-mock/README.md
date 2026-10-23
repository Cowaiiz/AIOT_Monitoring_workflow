# Synthetic HTTP workflow demo

Use this demo to try record validation, source status, threshold alerts and acknowledgment **without a dataset, checkpoint or GPU**. Scores are simulated. This is not an image classifier.

[Project overview](../../README.md) · [Real-image demo](../../demo/README.md) · [Saved results](results/README.md)

## 1. Prerequisites and working directory

Install Python 3.11, Node.js and Node-RED using the [root setup instructions](../../README.md#1-get-the-source). The Python/JavaScript scripts in this directory use standard libraries; you do not need the model's ML environment.

From the repository root:

```powershell
cd legacy\http-mock
```

Run all commands below from this directory. Use `py -3.11` explicitly so commands do not depend on the author's interpreter path.

## 2. Verify the source without running Node-RED

```powershell
node test_engine.js
node test_workflow.js
py -3.11 -m unittest test_client -v
py -3.11 build_flow.py
node verify_build.js
```

Expected: 15 engine checks, 98 offline workflow checks and four Python unit tests pass; flow validation reports eight unique routes. An expected invalid-input error is a passing case when the asserted error matches.

These are offline checks. They do not establish that an HTTP service is reachable. Some test descriptions in historical files and the current browser UI may still be Vietnamese.

## 3. Start Node-RED and deploy

In a separate terminal:

```powershell
node-red.cmd
```

If Node-RED is already running on port 1880, reuse it. In the terminal at `legacy/http-mock`:

```powershell
py -3.11 deploy_demo.py
```

The script uses the local Node-RED Admin API, checks revision/route collisions, creates backups and preserves unrelated flows. It does not currently supply credentials for an authenticated Admin API. Do not disable security on an existing shared installation to run the demo.

**Redeploying this legacy engine resets its RAM alerts and acknowledgments.** Export state first if needed; export is not a restore feature.

Open **http://localhost:1880/giang-aiot/v1/demo**.

## 4. Send a small first batch

```powershell
py -3.11 client.py send --count 10 --batch 10 --rate 10 --output results/my-first-run.json
```

The command sends ten synthetic records with fresh IDs/timestamps. Expected: `completed` is true, ten records are accepted and no unexpected request errors occur. Open/refresh the page to see alert counts and source status.

A valid score at or above its source's configured threshold creates a pending alert. A lower score creates no alert. Reusing the identical record returns duplicate; changed content with the same source/ID returns conflict.

## 5. Run the mixed HTTP tests

Stop other traffic while these tests run; assertions check alert deltas and source inactivity.

```powershell
py -3.11 test_workflow_http.py
```

Expected: 93 Python HTTP checks pass. The suite takes about 33 seconds because it waits for source inactivity. It covers 80 seeded mixed cases plus retry, concurrency, acknowledgment and source recovery. Timestamps/IDs are refreshed for each run. Deliberate invalid JSON, bad records and unknown IDs must return their expected errors.

The browser test button runs a separate suite with 94 checks. Python combines two acknowledgment assertions that the browser separates. Browser success does not prove that Python HTTP succeeded in a different execution environment.

Keep copies of result files if comparing runs: scripts can overwrite their default outputs.

## 6. Optional bounded load test

After the small batch and mixed checks succeed:

```powershell
py -3.11 client.py ramp --output results/my-ramp.json
```

This sends 10,000 valid records from ten sources in batches of 100, concurrency one, across target rates of 100, 500 and 1,000 records/s. Each stage has a 60-second deadline; requests default to a three-second timeout. Unexpected errors stop the ramp.

The supplied `sample-10000.json` is a synthetic fixture. The client materializes fresh timestamps when sending records; do not reuse an old timestamped HTTP payload as a fresh load run.

This measures HTTP processing of synthetic scores, not AI image throughput, camera capacity or maximum sustained load.

## Record contract and API

Record identity is the pair `(source_id, record_id)`. Each record contains:

| Field | Meaning |
|---|---|
| record_id | Stable identifier for retry; new identifier for a new observation |
| source_id | Configured source, such as src01 |
| timestamp | UTC timestamp |
| anomaly_score | Synthetic numeric score in [0,1] |

Prefix: `/giang-aiot/v1`.

| Method | Route | Purpose |
|---|---|---|
| POST | /records | One record |
| POST | /batch | Up to 200 records |
| GET | /alerts | Alerts and counts |
| POST | /ack | JSON containing alert_id |
| GET | /sources | Source activity status |
| GET | /metrics | Error and processing counters |
| GET | /events | Bounded event history |
| GET | /demo | Browser UI |

An initial ACK changes pending to acknowledged. Repeated/concurrent ACK preserves the original acknowledgment time; unknown IDs return `404 ALERT_NOT_FOUND`. Data/processing errors remain distinct from normal results and AI alerts.

## Configuration and storage

Edit `config.json` for source thresholds and limits, then regenerate `flow.json` with `build_flow.py` and redeploy. Editing the configuration alone does not update a running flow.

- Alerts/ACK are stored only in RAM; restart or engine redeployment loses them.
- Capacity is 20,000 alerts. Full capacity returns an error without silently deleting pending alerts. ACK does not release space.
- Normal-record deduplication has a ten-minute TTL and 20,000-entry limit; retained alerts separately protect their IDs.
- The event ring retains 1,000 entries independently of the alert store.
- Silent means no valid sample for over 30 seconds, not proven disconnection. Duplicate traffic does not refresh activity.
- The UI shows at most the latest 200 matching alerts; JSON export includes all retained alerts.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Connection refused | Node-RED is running on the same computer, port 1880 |
| HTTP 404 | Deploy completed; correct legacy prefix, not /giang-pcb4/v1 |
| Revision/route conflict | Resolve the current flow conflict instead of forcing an overwrite |
| Unexpected source/alert counts | Stop concurrent clients; rerun one suite at a time |
| STALE_RECORD | Use the client to generate fresh records; keep original payload only for retries |
| WinError 10013 | Socket access was blocked; it is not a passing HTTP test |
| Capacity error | Export the state and choose a deliberate reset; no automatic eviction/restore exists |

## File guide

`engine.js` implements rules; `config.json` holds settings; `build_flow.py` embeds source into `flow.json`; `demo.html` and browser runners provide the UI/tests; `client.py` generates traffic; `mixed_cases.json` declares independent expected cases; `deploy_demo.py` handles deployment.

[Results documentation](results/README.md) explains the historical evidence and timing units. `MANIFEST.json` is a historical package manifest, not a checksum of these updated instructions. There is no MQTT, real hardware, model inference or external notification delivery in this prototype.

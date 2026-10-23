# Industrial AI Monitoring Framework

A local research prototype connecting **PCB images, real anomaly inference, Node-RED, persistent alerts and the Inspect web interface**.

Implementation and evaluation by **Tran Long Giang**, Computer Engineering, Group 1.

## Start here

| Purpose | Link |
|---|---|
| Read Giang's individual implementation report in English | [Implementation report](reports/IMPLEMENTATION_REPORT.md) |
| Check translation and deliverable progress | [Localization status](reports/LOCALIZATION_STATUS.md) |
| Run the real-image application | [Demo instructions](demo/README.md) |
| Prepare VisA PCB4 and fit the baseline | [Model instructions](model/TRAINING_README.md) |
| Inspect measured evidence | [Evidence summary](reports/evidence/verification-summary.json) |
| Review the earlier synthetic HTTP workflow | [Legacy demo](legacy/http-mock/README.md) |

## Repository layout

- `demo/`: interface, inference service, SQLite store, Node-RED flow, deployment and checks.
- `model/`: data preparation and baseline fitting.
- `reports/`: implementation report and selected experimental evidence.
- `legacy/http-mock/`: synthetic-data workflow and bounded HTTP tests.

## Running the demo

The scripts currently use paths from the tested Windows setup. Dataset images, checkpoint weights, virtual environments and operating databases are excluded from Git. Read the component instructions before using another machine.

Keep Node-RED running on port 1880. From the repository root:

```powershell
& "D:\Project\aiot-model\.venv\Scripts\python.exe" .\demo\start_demo.py
```

After startup verification succeeds, open http://localhost:1880/giang-pcb4/v1/demo and keep the model terminal open.

To update only the interface while both services are running:

```powershell
& "D:\Project\aiot-model\.venv\Scripts\python.exe" .\demo\update_ui.py
```

Do not launch a second service if the existing installation is still running from the earlier `pcb4-demo` directory. Preserve its SQLite database and follow the migration notes before switching directories.

## Current measured status

- Real VisA PCB4 inference, HTTP integration, alert acknowledgment and SQLite persistence have been implemented and tested locally.
- Baseline image AUROC is **94.11%**, but recall at the selected threshold is **31%**: 69 of 100 anomalous test images were missed.
- No subsequent model-improvement run has been completed.
- Complete process restart recovery and full interaction coverage of the redesigned interface remain outstanding.
- No real camera, MQTT sensor, second workflow-tool comparison or fully validated offline package has been completed.

Below threshold does not establish that a PCB is defect-free. Synthetic HTTP throughput is not AI image throughput.

Attribution is consolidated in the report's [references](reports/IMPLEMENTATION_REPORT.md#references-and-attribution). The academic PDF and LaTeX source are being prepared for separate delivery, not GitHub publication. Publishing source code does not expose local services.

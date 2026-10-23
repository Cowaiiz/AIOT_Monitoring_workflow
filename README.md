# Industrial AI Monitoring Framework

A local research prototype for inspecting PCB images and managing anomaly alerts. The real-image path connects a Python model service, Node-RED, SQLite and the Inspect web interface.

**New here? Choose a starting point:**

| Goal | Start here | What you need |
|---|---|---|
| Try the workflow without training a model | [Synthetic HTTP demo](legacy/http-mock/README.md) | Python, Node.js and Node-RED |
| Inspect real PCB4 images | [Model setup](model/README.md), then [Inspect setup](demo/README.md) | VisA PCB4 images, Python ML environment and a locally fitted checkpoint |
| Review the implementation and measured results | [Report index](reports/README.md) | No installation |
| Understand saved result files | [Evidence guide](reports/evidence/README.md) | No installation |

This is a source-based Windows/PowerShell walkthrough. A checkpoint, dataset, operating database and Python environment are **not** included. CPU fallback exists in the model code, but the published model measurements used an NVIDIA RTX 4060. A clean-machine installation has not yet been verified.

## 1. Get the source

Install Git, Python 3.11 and Node.js using their official installers if they are not already available. For Node-RED, follow its [Windows setup guide](https://nodered.org/docs/getting-started/windows).

From a directory where you keep projects:

```powershell
git clone https://github.com/Cowaiiz/AIOT_Monitoring_workflow.git
cd AIOT_Monitoring_workflow
py -3.11 --version
node --version
npm.cmd --version
```

You can also use GitHub's **Code > Download ZIP**, extract it and open PowerShell in the extracted repository root. No command below requires your folder to match the author's directory.

If Node-RED is not installed:

```powershell
npm.cmd install -g node-red
```

Install dependencies only for the path you choose. The synthetic demo does not require PyTorch, a GPU or model weights.

## 2. Follow one complete walkthrough

- **Synthetic workflow:** open [legacy/http-mock](legacy/http-mock/README.md). Run offline tests first, then deploy and send a small bounded batch.
- **Real images:** complete [model preparation](model/README.md), record the generated run directory, then follow [demo setup](demo/README.md). The demo guide lists every currently hard-coded path that must match your machine.

The code still contains original-machine defaults. The documentation shows how to replace them; it does not claim that environment variables or a universal installer already exist.

## 3. Know what you are running

| Directory | Purpose |
|---|---|
| [demo/](demo/README.md) | Real-image interface, model HTTP adapter, persistent alerts and deployment |
| [model/](model/README.md) | Dataset extraction and bounded-memory PatchCore-style baseline |
| [reports/](reports/README.md) | Individual implementation report and evidence |
| [legacy/](legacy/README.md) | Earlier synthetic-score prototype |

Two local pages are available **after their corresponding flow is deployed**:

- Real images: http://localhost:1880/giang-pcb4/v1/demo
- Synthetic scores: http://localhost:1880/giang-aiot/v1/demo

`localhost` means the computer running your browser. This repository does not host a shared live dashboard. The Python service and workflow are intended for loopback-only local use.

## Current results and limits

The recorded PCB4 baseline achieved image AUROC **94.11%**, but recall at its selected threshold was **31%**: 69 of 100 anomalous test images were missed. Below threshold does not establish that a PCB is defect-free.

SQLite persistence, duplicate handling and acknowledgment were tested. Full process stop/start recovery and complete interaction testing of the redesigned UI remain outstanding. There is no completed improvement experiment, real camera/MQTT integration, second workflow-tool comparison or fully validated offline package.

README instructions are now in English. Some published UI strings and historical test descriptions may still be Vietnamese; this documentation update does not imply a new UI deployment.

Implementation and evaluation: **Tran Long Giang, Group 1**. See the [individual report](reports/IMPLEMENTATION_REPORT.md) for contributions, evidence and consolidated attribution. The academic PDF and LaTeX source are kept outside this repository.

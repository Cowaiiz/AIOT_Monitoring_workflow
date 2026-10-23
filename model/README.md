# Model: prepare VisA PCB4 and fit a baseline

This directory turns the official VisA PCB4 image split into a local checkpoint and evaluation files that the [Inspect demo](../demo/README.md) can load.

**Inputs:** official VisA archive, Python 3.11 ML environment, network access for initial dependency/backbone downloads.  
**Outputs:** a new run directory containing `model.pt`, its threshold, predictions and metrics.  
**Run commands from:** the repository root, unless stated otherwise.

The repository does not provide a downloadable checkpoint. Fit one with the procedure below, or obtain a trusted compatible run bundle containing all the required files. An arbitrary Lightning `.ckpt` is not compatible with this custom loader.

## 1. Create an isolated environment

From the repository root:

```powershell
py -3.11 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
```

Use the explicit interpreter path in this guide; activating the environment or changing PowerShell execution policy is unnecessary.

The recorded environment used Python 3.11.9, torch 2.6.0+cu124, torchvision 0.21.0+cu124, anomalib 2.2.0, lightning 2.5.5 and torchmetrics 1.8.2. No complete dependency lock file is supplied. The commands below are a setup recipe based on those versions, not a newly validated clean-machine installation.

Choose **one** PyTorch option from the [official previous-version instructions](https://pytorch.org/get-started/previous-versions/#v260).

For a compatible NVIDIA GPU/driver using the recorded CUDA 12.4 wheel:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
```

For CPU-only use instead:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
```

Then install the model packages and check the environment:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install anomalib==2.2.0 lightning==2.5.5 torchmetrics==1.8.2 timm einops pillow numpy
& ".\.venv\Scripts\python.exe" -m pip check
& ".\.venv\Scripts\python.exe" -c "import torch, torchvision; from anomalib.models.image.patchcore.torch_model import PatchcoreModel; print('torch:', torch.__version__, 'torchvision:', torchvision.__version__, 'cuda:', torch.cuda.is_available())"
& ".\.venv\Scripts\python.exe" .\model\train_visa_pcb4.py --smoke
```

Expected: imports succeed, pip reports no broken requirements, and the smoke check prints `"smoke_passed": true` and `"reload_matches": true`. The smoke check uses synthetic tensors; it does not fit the dataset or prove model quality.

CPU operation is supported by the device-selection code, but its speed and exact scores are not established by the published GPU run. If package resolution fails, retain the error output; do not silently change library versions and assume baseline equivalence.

## 2. Choose your data directory and download VisA

Keep large datasets/runs outside the Git checkout. This guide uses:

```text
C:/aiot-data
```

You may use any writable directory, including another drive. Use the same root consistently in the extraction, training and demo steps.

Download `VisA_20220922.tar` using the instructions in [Amazon Science's official VisA repository](https://github.com/amazon-science/spot-diff). This experiment uses **VisA pcb4**, not the separate PCB Defect Dataset. Consult the dataset's accompanying license and attribution terms before redistributing images.

## 3. Configure and run extraction

Edit the two constants near the top of [prepare_visa_pcb4.py](prepare_visa_pcb4.py). Replace the archive path with your actual downloaded file:

```python
ARCHIVE = Path('C:/Users/YOUR_USERNAME/Downloads/VisA_20220922.tar')
DEST = Path('C:/aiot-data/datasets/visa')
```

`YOUR_USERNAME` is a placeholder; do not leave it literally in the file. Forward slashes work in Windows Python paths.

Then:

```powershell
& ".\.venv\Scripts\python.exe" .\model\prepare_visa_pcb4.py
```

Expected: `PREPARE COMPLETE. No training performed.`, and official counts of 904 train/normal, 101 test/normal and 100 test/anomaly.

The script extracts only `pcb4/` and `split_csv/1cls.csv`. It checks archive paths and refuses to overwrite different existing content. If it reports a conflicting file, investigate the archive/destination instead of deleting your dataset.

Expected locations under your chosen root:

| Path | Contents |
|---|---|
| `datasets/visa/split_csv/1cls.csv` | Official split definitions |
| `datasets/visa/pcb4/Data/Images/` | Normal and anomalous images |
| `datasets/visa/pcb4/Data/Masks/` | Original anomaly masks |
| `logs/visa-pcb4-preparation.json` | Extraction summary |

## 4. Fit and evaluate

```powershell
& ".\.venv\Scripts\python.exe" .\model\train_visa_pcb4.py --root "C:\aiot-data"
```

Use your chosen root, not the dataset subdirectory. The script adds `datasets/visa` itself.

The first run may download pretrained ResNet18 weights. Normal training images are split with seed 42 into **804 fit** and **100 calibration** images. Test contains **201 images**. Fitting creates a bounded memory bank; adding epochs is not the training mechanism used here.

Wait for `COMPLETE. Results: ...`. Save the exact printed run path. Each run gets its own timestamped directory.

| Output | Purpose |
|---|---|
| `model.pt` | Custom model state, configuration and memory bank |
| `threshold.json` | Raw threshold and selection rule |
| `manifest.json` | Fit/calibration/test membership and split hash |
| `calibration.json` | Calibration scores |
| `test-predictions.json` | Per-image test scores and decisions |
| `results.json` | Metrics, confusion counts and timing scope |

Keep these files together. The demo's startup checks require the predictions as well as weights/threshold. Training output `"node_red_connected": false` is expected: this script does not deploy Node-RED.

## 5. Connect your run

Continue with [Inspect setup](../demo/README.md#2-configure-your-model-and-dataset-paths). Point its loader to the exact run you just created, and update both dataset references used by verification.

Do not copy the report's threshold into a different model run. A rerun may produce different scores, particularly on different hardware. A fixed seed does not guarantee bit-identical results everywhere.

## Method and interpretation

The baseline uses ResNet18 layer2/layer3 features, nine neighbors, 256 x 256 images, one ImageNet normalization and up to 2,000 patches selected by seeded random-priority sampling. It is **not canonical greedy coreset PatchCore**.

The threshold is the 99th percentile (`higher`) of normal calibration scores. Test data did not select the initial threshold. Once test results have been reviewed, further tuning needs a separate validation protocol.

The recorded run produced TP/TN/FP/FN = 31/101/0/69, AUROC 94.11%, recall 31% and F1 47.33%. These are historical results, not promised outputs on your machine. No pixel metrics are reported. Original masks retain values 0-7; any binary evaluation needs an explicit, validated foreground conversion.

## Troubleshooting

| Symptom | Check |
|---|---|
| Missing archive or split CSV | ARCHIVE and DEST; use the official archive layout |
| Unexpected split counts | Correct archive/category; do not edit assertions to accept unrelated data |
| Import error or incompatible checkpoint | Interpreter, pinned versions and smoke check; use this script's run format |
| Pretrained download fails | Network/cache availability; first fit is not an offline operation |
| CUDA unavailable | GPU driver and selected wheel; CPU fallback does not use published GPU timings |
| No COMPLETE message | Inspect the terminal error; a partial run directory is not a completed checkpoint bundle |

For experiment details and attribution, read the [implementation report](../reports/IMPLEMENTATION_REPORT.md). Dataset images, caches, environments and model weights stay outside Git.

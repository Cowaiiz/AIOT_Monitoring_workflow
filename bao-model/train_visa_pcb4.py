"""Bounded PatchCore random-bank baseline. Run with the prepared D: environment."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='D:/Project/aiot-model')
    parser.add_argument('--smoke', action='store_true', help='Synthetic API check only; no download or dataset training')
    args = parser.parse_args()
    root = Path(args.root)
    if not args.smoke:
        for env, folder in [('TORCH_HOME', 'torch-cache'), ('HF_HOME', 'hf-cache'), ('TMP', 'tmp'), ('TEMP', 'tmp')]:
            (root / folder).mkdir(parents=True, exist_ok=True)
            os.environ[env] = str(root / folder)
    import numpy as np
    import torch
    from PIL import Image
    from torchvision import transforms
    from anomalib.models.image.patchcore.torch_model import PatchcoreModel
    from torchmetrics.functional.classification import binary_auroc

    seed = 42
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    config = dict(backbone='resnet18', layers=['layer2', 'layer3'], num_neighbors=9)
    model = PatchcoreModel(**config, pre_trained=not args.smoke).to(device)
    transform = transforms.Compose([transforms.Resize((256, 256)), transforms.ToTensor(),
                                    transforms.Normalize([.485, .456, .406], [.229, .224, .225])])
    rng = torch.Generator(device='cpu').manual_seed(seed)
    bank = None
    priorities = torch.empty(0)

    def fit_batch(batch):
        nonlocal bank, priorities
        model.train()
        model.feature_extractor.eval()
        with torch.inference_mode():
            features = model(batch).detach().cpu()
        model.embedding_store.clear()
        # Independent priorities give a uniform bounded sample over ALL patches.
        keys = torch.rand(features.shape[0], generator=rng, dtype=torch.float64)
        candidates = features if bank is None else torch.cat([bank, features])
        priorities = torch.cat([priorities, keys])
        keep = torch.topk(priorities, min(2000, len(priorities))).indices
        bank, priorities = candidates[keep], priorities[keep]

    if args.smoke:
        batch = torch.rand(2, 3, 256, 256, device=device)
        fit_batch(batch)
        model.memory_bank = bank.to(device)
        model.eval()
        with torch.inference_mode():
            before = model(batch).pred_score
            restored = PatchcoreModel(**config, pre_trained=False).to(device)
            restored.load_state_dict(model.state_dict())
            restored.eval()
            after = restored(batch).pred_score
        assert torch.isfinite(before).all() and torch.allclose(before, after)
        print(json.dumps({'smoke_passed': True, 'device': str(device), 'bank_shape': list(bank.shape),
                          'reload_matches': True, 'dataset_trained': False}))
        return

    dataset = root / 'datasets/visa'
    split = dataset / 'split_csv/1cls.csv'
    with split.open(encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['object'] == 'pcb4']
    train = sorted([r for r in rows if r['split'] == 'train' and r['label'] == 'normal'], key=lambda r: r['image'])
    test = sorted([r for r in rows if r['split'] == 'test'], key=lambda r: r['image'])
    assert len(train) == 904 and len(test) == 201
    assert sum(r['label'] == 'anomaly' for r in test) == 100
    random.Random(seed).shuffle(train)
    calibration, fit = train[:100], train[100:]
    paths = [r['image'] for r in fit + calibration + test]
    assert len(set(paths)) == len(paths), 'Split overlap'
    for path in paths:
        resolved = (dataset / path).resolve()
        if not resolved.is_relative_to(dataset.resolve()) or not resolved.is_file():
            raise ValueError(f'Invalid dataset path: {path}')
    output = root / 'runs' / ('visa-pcb4-' + time.strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    def save(name, data):
        (output / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    save('manifest.json', {'seed': seed, 'fit': [r['image'] for r in fit],
                          'calibration': [r['image'] for r in calibration], 'test': test,
                          'split_sha256': hashlib.sha256(split.read_bytes()).hexdigest()})
    def image_tensor(row):
        with Image.open(dataset / row['image']) as image:
            return transform(image.convert('RGB'))
    print(f'Device={device}; fit=804; calibration=100; test=201; output={output}', flush=True)
    started = time.perf_counter()
    for start in range(0, len(fit), 8):
        fit_batch(torch.stack([image_tensor(r) for r in fit[start:start+8]]).to(device))
        if start % 80 == 0:
            print(f'Fit {min(start+8, len(fit))}/{len(fit)}', flush=True)
    model.memory_bank = bank.to(device)
    model.eval()
    fit_seconds = time.perf_counter() - started
    checkpoint = {'state_dict': {k: v.cpu() for k, v in model.state_dict().items()}, 'config': config,
                  'image_size': 256, 'seed': seed, 'sampling': 'uniform random priority, max 2000 patches'}
    torch.save(checkpoint, output / 'model.pt')
    def evaluate(items, phase):
        results = []
        for idx, row in enumerate(items):
            started = time.perf_counter()
            tensor = image_tensor(row).unsqueeze(0).to(device)
            if device.type == 'cuda':
                torch.cuda.synchronize()
            inference_start = time.perf_counter()
            with torch.inference_mode():
                score = float(model(tensor).pred_score.item())
            if not np.isfinite(score):
                raise ValueError(f'Nonfinite score: {row["image"]}')
            results.append({'image': row['image'], 'label': row['label'], 'score': score,
                            'inference_ms': (time.perf_counter()-inference_start)*1000,
                            'image_to_score_ms': (time.perf_counter()-started)*1000})
            if (idx+1) % 25 == 0:
                print(f'{phase} {idx+1}/{len(items)}', flush=True)
        return results
    # Warm-up excluded from timings; no test image used.
    with torch.inference_mode():
        model(image_tensor(calibration[0]).unsqueeze(0).to(device))
    calibrated = evaluate(calibration, 'Calibration')
    threshold = float(np.quantile([r['score'] for r in calibrated], .99, method='higher'))
    save('threshold.json', {'threshold': threshold, 'rule': 'raw_score >= threshold',
                            'selection': '99th percentile (higher) of 100 held-out training normal images',
                            'score_is_probability': False})
    save('calibration.json', calibrated)
    measured = evaluate(test, 'Test')
    for row in measured:
        row['predicted_anomaly'] = row['score'] >= threshold
    truth = np.array([r['label'] == 'anomaly' for r in measured])
    pred = np.array([r['predicted_anomaly'] for r in measured])
    tp, tn = int((truth & pred).sum()), int((~truth & ~pred).sum())
    fp, fn = int((~truth & pred).sum()), int((truth & ~pred).sum())
    result = {'dataset': 'VisA', 'category': 'pcb4', 'trained': True, 'device': str(device),
              'variant': 'PatchCore ResNet18, bounded random memory bank; not canonical greedy coreset',
              'fit_images': 804, 'calibration_images': 100, 'test_images': 201,
              'threshold': threshold, 'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
              'image_auroc': float(binary_auroc(torch.tensor([r['score'] for r in measured]), torch.tensor(truth.astype(int)))),
              'precision': tp/max(tp+fp, 1), 'recall': tp/max(tp+fn, 1), 'f1': 2*tp/max(2*tp+fp+fn, 1),
              'fit_seconds': fit_seconds, 'pixel_metrics': None,
              'latency_scope': 'batch=1, warmed, inference includes GPU transfer completion; total includes image loading and preprocessing',
              'inference_ms_median': float(np.median([r['inference_ms'] for r in measured])),
              'inference_ms_p95': float(np.quantile([r['inference_ms'] for r in measured], .95)),
              'image_to_score_ms_median': float(np.median([r['image_to_score_ms'] for r in measured])),
              'torch': torch.__version__, 'node_red_connected': False}
    save('test-predictions.json', measured)
    save('results.json', result)
    print(json.dumps(result, indent=2))
    print(f'COMPLETE. Results: {output}', flush=True)


if __name__ == '__main__':
    main()

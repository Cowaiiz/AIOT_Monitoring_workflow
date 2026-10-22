"""Extract only pcb4 and official 1-class split; preserve existing different files."""
import csv
import hashlib
import io
import json
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath

ARCHIVE = Path('D:/Downloads/VisA_20220922.tar')
DEST = Path('D:/Project/aiot-model/datasets/visa')

def main():
    with tarfile.open(ARCHIVE, 'r:') as archive:
        members = [m for m in archive.getmembers()
                   if m.name.startswith('pcb4/') or m.name == 'split_csv/1cls.csv']
        entries = {}
        for m in members:
            path = PurePosixPath(m.name)
            if path.is_absolute() or '..' in path.parts or any(':' in s or '\\' in s for s in path.parts):
                raise ValueError(f'Unsafe member: {m.name}')
            if m.isdir():
                continue
            if not m.isfile() or m.name in entries:
                raise ValueError(f'Unexpected or duplicate member: {m.name}')
            entries[m.name] = m
        rows = list(csv.DictReader(io.StringIO(archive.extractfile(entries['split_csv/1cls.csv']).read().decode('utf-8-sig'))))
        rows = [r for r in rows if r['object'] == 'pcb4']
        counts = dict(Counter(r['split']+'/'+r['label'] for r in rows))
        if counts != {'train/normal':904, 'test/normal':101, 'test/anomaly':100}:
            raise ValueError(f'Unexpected official split: {counts}')
        for row in rows:
            for key in ('image', 'mask'):
                if row[key] and row[key] not in entries:
                    raise ValueError(f'Missing {key}: {row[key]}')
        # Check all existing files before writing anything.
        for name, m in entries.items():
            target = DEST.joinpath(*PurePosixPath(name).parts)
            if not target.resolve().is_relative_to(DEST.resolve()):
                raise ValueError(f'Path escapes destination: {target}')
            if target.exists():
                source_hash = hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                if hashlib.sha256(target.read_bytes()).hexdigest() != source_hash:
                    raise ValueError(f'Existing different file retained: {target}')
        written = 0
        for name, m in entries.items():
            target = DEST.joinpath(*PurePosixPath(name).parts)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                output.write(archive.extractfile(m).read())
            written += 1
        for row in rows:
            for key in ('image', 'mask'):
                if row[key] and not (DEST/row[key]).is_file():
                    raise ValueError(f'Missing extracted file: {row[key]}')
        report = {'dataset':'VisA', 'category':'pcb4', 'archive':str(ARCHIVE),
                  'destination':str(DEST), 'official_split':counts,
                  'selected_files':len(entries), 'new_files':written,
                  'masks':'Original values preserved; validate and convert before pixel evaluation',
                  'trained':False}
        log = DEST.parent.parent/'logs/visa-pcb4-preparation.json'
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        print('PREPARE COMPLETE. No training performed.')

if __name__ == '__main__':
    main()

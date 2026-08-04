import os
import json
import datetime
import re
from pathlib import Path


def infer_page_count(folder: Path) -> int:
    page_numbers = []

    for name in os.listdir(folder):
        m = re.fullmatch(r'output_pages_(\d+)', name)
        if m:
            page_numbers.append(int(m.group(1)))
            continue
        m = re.fullmatch(r'page_(\d+)\.(png|jpg|jpeg|tif|tiff)', name)
        if m:
            page_numbers.append(int(m.group(1)))

    if page_numbers:
        return max(page_numbers)

    manifest_path = folder / 'manifest.json'
    if manifest_path.exists():
        try:
            text = manifest_path.read_text(encoding='utf-8')
            matches = re.findall(r'page_(\d+)\.', text)
            if matches:
                return max(int(m) for m in matches)
        except Exception:
            pass

    return 1


def infer_filename(folder: Path) -> str:
    for name in sorted(os.listdir(folder)):
        if name == 'info.json':
            continue
        if name.lower().endswith('.pdf'):
            return name
    for name in sorted(os.listdir(folder)):
        if name == 'info.json':
            continue
        if name.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')):
            return name
    return next((name for name in sorted(os.listdir(folder)) if name != 'info.json'), f'{folder.name}.bin')


base = Path.cwd() / 'uploads' / 'main'
created = []
for doc_dir in sorted(base.iterdir()):
    if not doc_dir.is_dir():
        continue
    info_path = doc_dir / 'info.json'

    filename = infer_filename(doc_dir)
    nbr_pages = infer_page_count(doc_dir)

    payload = {
        'project_id': 'main',
        'document_id': doc_dir.name,
        'filename': filename,
        'upload_date': datetime.datetime.now().isoformat(),
        'nbr_pages': nbr_pages,
        'current_page': 0,
        'category': 'bilan_lipidique_1',
        'v1': False,
        'v2': False,
    }

    with open(info_path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    created.append(doc_dir.name)

print('created', len(created))
for item in created:
    print(item)

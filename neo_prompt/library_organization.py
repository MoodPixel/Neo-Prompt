"""app-owned, copy-first Library categories and managed assets.

Legacy saved JSON records and source images remain the authority. Organized files
are convenience copies; never move a source or read another Neo app's data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata

MAX_CATEGORY = 64
MAX_NAME = 120
INVALID_WINDOWS = set('<>:"/\\|?*')


def label(value: str | None, *, fallback: str, limit: int) -> str:
    name = str(value or '').strip()
    if not name:
        return fallback
    if len(name) > limit or any(ord(c) < 32 or c in INVALID_WINDOWS for c in name) or name.endswith(('.', ' ')):
        raise ValueError('Use a shorter name without path separators or Windows-reserved characters.')
    if name in ('.', '..'):
        raise ValueError('Invalid category/name.')
    return name


def category_label(value: str | None, fallback: str = 'General') -> str:
    return label(value, fallback=fallback, limit=MAX_CATEGORY)


def entry_name(value: str | None, category: str) -> str:
    return label(value, fallback=category, limit=MAX_NAME)


def folder_slug(value: str) -> str:
    clean = unicodedata.normalize('NFKC', value).strip()
    clean = re.sub(r'[^\w. -]+', '_', clean, flags=re.UNICODE)
    clean = re.sub(r'[ .]+', '_', clean).strip('._')[:80]
    if not clean or clean.casefold().split('.')[0] in {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1,10)), *(f'lpt{i}' for i in range(1,10))}:
        clean = 'Collection_' + __import__('hashlib').sha256(value.encode('utf-8')).hexdigest()[:10]  # only for filename fallback
    return clean


def relative_assets(kind: str, record: dict) -> list[str]:
    """Paths are derived, never trusted from client-supplied asset names."""
    folder = 'caption_library' if kind == 'captions' else 'prompt_library'
    group = folder_slug(record['category'])
    stem = folder_slug(record['name'])[:65] + '__' + re.sub('[^a-zA-Z0-9-]', '', record['id'])[:50]
    base = f'{folder}/{group}/{stem}'
    result = [base + '.txt', base + '.json']
    if kind == 'captions' and record.get('asset_image_ext'):
        result.append(base + record['asset_image_ext'])
    return result


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.np-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def materialize(root: Path, kind: str, record: dict, source_image: Path | None = None) -> list[str]:
    if kind == 'captions':
        if not source_image or not source_image.is_file():
            raise ValueError('The original image must be available to organize a caption.')
        suffix = source_image.suffix.lower()
        if suffix not in ('.png', '.jpg', '.jpeg', '.webp'):
            raise ValueError('Unsupported caption image type')
        record['asset_image_ext'] = suffix
    paths = relative_assets(kind, record)
    made = []
    try:
        _write_atomic(root / paths[0], record['text'].encode('utf-8'))
        made.append(paths[0])
        manifest = {k: record.get(k) for k in ('id', 'name', 'category', 'task', 'operation', 'image_id', 'origin', 'origin_run_id', 'batch_id', 'when') if k in record}
        _write_atomic(root / paths[1], (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        made.append(paths[1])
        if len(paths) == 3:
            destination = root / paths[2]
            with source_image.open('rb') as inp:
                destination.parent.mkdir(parents=True, exist_ok=True)
                fd, temp = tempfile.mkstemp(prefix='.np-', dir=destination.parent)
                try:
                    with os.fdopen(fd, 'wb') as output:
                        shutil.copyfileobj(inp, output, 1024 * 1024)
                        output.flush()
                        os.fsync(output.fileno())
                    os.replace(temp, destination)
                finally:
                    if os.path.exists(temp):
                        os.unlink(temp)
            made.append(paths[2])
        return paths
    except Exception:
        clear_assets(root, made)
        raise


def clear_assets(root: Path, paths: list[str]) -> None:
    for name in paths:
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()):
            continue
        target.unlink(missing_ok=True)
        parent = target.parent
        try:
            if parent != root.resolve():
                parent.rmdir()  # only remove empty, owned category directories
        except OSError:
            pass

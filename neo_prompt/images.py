"""Private, EXIF-stripped, bounded images for captioning. No user-defined paths."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from .storage import timestamp

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageError(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def save_image(store, data: bytes, *, source_name: str = "", relative_path: str = "", deduplicate: bool = False) -> dict:
    if not data:
        raise ImageError('Image is empty.')
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageError('Maximum image upload is 10 MB.', 413)
    try:
        with Image.open(BytesIO(data)) as original:
            if original.format not in ('PNG', 'JPEG', 'WEBP') or getattr(original, 'is_animated', False):
                raise ImageError('Upload a static PNG, JPEG or WebP image.')
            if original.width * original.height > MAX_PIXELS or original.width <= 0 or original.height <= 0:
                raise ImageError('Image dimensions are too large (20 megapixel limit).')
            image = ImageOps.exif_transpose(original)
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
            # Normalize content and strip EXIF, ICC, untrusted chunks/metadata.
            output = BytesIO()
            if image.mode == 'RGBA':
                fmt, mime, ext = 'PNG', 'image/png', '.png'
                image.save(output, format=fmt, optimize=True)
            else:
                fmt, mime, ext = 'JPEG', 'image/jpeg', '.jpg'
                image.save(output, format=fmt, quality=90, optimize=True)
            content = output.getvalue()
            width, height = image.size
    except ImageError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageError('Invalid, truncated or unsafe image file.') from exc
    if len(content) > MAX_IMAGE_BYTES:
        raise ImageError('Normalized image exceeds the 10 MB storage limit.', 413)
    digest = hashlib.sha256(content).hexdigest()
    if deduplicate:
        existing = store.image_by_hash(digest)
        if existing: return {**existing, 'duplicate': True}
    image_id = uuid4().hex
    folder = store.root / 'images'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (image_id + ext)
    path.write_bytes(content)
    record = {'id': image_id, 'name': 'image_' + image_id[:10] + ext, 'mime': mime, 'ext': ext, 'size': len(content), 'width': width, 'height': height, 'sha256': digest, 'source_name': source_name[:220], 'relative_path': relative_path[:500], 'created_at': timestamp()}
    try:
        store.add_image(record)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return record


def image_path(store, image_id: str) -> tuple[Path, dict]:
    record = store.image(image_id)
    if not record or record.get('ext') not in ('.jpg','.png'):
        raise ImageError('Image not found.', 404)
    path = store.root / 'images' / (record['id'] + record['ext'])
    if not path.is_file():
        raise ImageError('Image file missing. Upload it again.', 404)
    return path, record

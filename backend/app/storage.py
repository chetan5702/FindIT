from __future__ import annotations

import hashlib
import io
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError

from app.errors import APIError


ALLOWED_SIGNATURES = {
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
}
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes
    mime_type: str
    byte_size: int
    sha256: str


class StorageBackend(Protocol):
    def save(self, namespace: str, content: bytes, suffix: str) -> str: ...

    def path_for(self, storage_key: str) -> Path: ...

    def delete(self, storage_key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, namespace: str, content: bytes, suffix: str) -> str:
        safe_namespace = "".join(c for c in namespace if c.isalnum() or c in {"-", "_"})
        if not safe_namespace:
            raise ValueError("Invalid storage namespace")
        relative = Path(safe_namespace) / f"{uuid.uuid4().hex}{suffix}"
        target = (self.root / relative).resolve()
        if self.root not in target.parents:
            raise ValueError("Unsafe storage path")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(content)
        os.replace(temporary, target)
        return relative.as_posix()

    def path_for(self, storage_key: str) -> Path:
        target = (self.root / storage_key).resolve()
        if self.root not in target.parents:
            raise APIError(404, "file_not_found", "File not found")
        return target

    def delete(self, storage_key: str) -> None:
        target = self.path_for(storage_key)
        try:
            target.unlink()
        except FileNotFoundError:
            pass


def validate_image(content: bytes, declared_type: str | None, max_bytes: int) -> ValidatedImage:
    if not content:
        raise APIError(422, "empty_file", "The uploaded image is empty")
    if len(content) > max_bytes:
        raise APIError(413, "file_too_large", f"Image exceeds the {max_bytes} byte limit")
    detected_type = next(
        (mime for mime, validator in ALLOWED_SIGNATURES.items() if validator(content)), None
    )
    if detected_type is None:
        raise APIError(422, "invalid_image", "Only valid JPEG, PNG, and WebP images are allowed")
    if declared_type and declared_type.lower() not in {detected_type, "application/octet-stream"}:
        raise APIError(422, "mime_mismatch", "The image content does not match its MIME type")
    try:
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > 40_000_000:
                raise APIError(422, "invalid_image_dimensions", "Image dimensions are not allowed")
            image.verify()
        # Reopen after verify(). Normalize orientation and discard EXIF/GPS and
        # unrelated ancillary metadata before persisting untrusted user images.
        with Image.open(io.BytesIO(content)) as image:
            image = ImageOps.exif_transpose(image)
            output = io.BytesIO()
            if detected_type == "image/jpeg":
                image.convert("RGB").save(output, format="JPEG", quality=90)
            elif detected_type == "image/png":
                image.convert("RGBA" if "A" in image.getbands() else "RGB").save(
                    output, format="PNG"
                )
            else:
                image.convert("RGBA" if "A" in image.getbands() else "RGB").save(
                    output, format="WEBP", quality=90
                )
            sanitized = output.getvalue()
    except APIError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise APIError(422, "invalid_image", "The uploaded image is corrupt or unsafe") from None
    if len(sanitized) > max_bytes:
        raise APIError(413, "file_too_large", "The sanitized image exceeds the upload size limit")

    return ValidatedImage(
        content=sanitized,
        mime_type=detected_type,
        byte_size=len(sanitized),
        sha256=hashlib.sha256(sanitized).hexdigest(),
    )


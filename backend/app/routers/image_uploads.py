"""Shared bounded upload decoding for prediction endpoints."""
from __future__ import annotations

from io import BytesIO
import warnings
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


async def save_validated_image(file: UploadFile, target: Path) -> None:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(400, "The uploaded image is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Images must be smaller than 8 MB.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format not in ALLOWED_FORMATS:
                    raise HTTPException(415, "Please upload a JPG, PNG, or WEBP image.")
                width, height = image.size
                if width < 32 or height < 32:
                    raise HTTPException(400, "The image dimensions are too small to inspect.")
                if width * height > MAX_IMAGE_PIXELS:
                    raise HTTPException(413, "The image dimensions are too large to process.")
                image.verify()
            with Image.open(BytesIO(content)) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                target.parent.mkdir(parents=True, exist_ok=True)
                image.save(target, format="JPEG", quality=95)
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(400, "That file is not a readable image.") from exc

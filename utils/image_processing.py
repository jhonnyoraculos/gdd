"""Safe image normalization for database-backed uploads."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_WIDTH = 854
MAX_IMAGE_HEIGHT = 480
WEBP_QUALITY = 72


class ImageProcessingError(ValueError):
    """Raised when an uploaded image is unsafe or unsupported."""


@dataclass(frozen=True, slots=True)
class ProcessedImage:
    data: bytes
    mime_type: str
    width: int
    height: int


def process_image_480p(raw: bytes) -> ProcessedImage:
    """Validate, orient and convert an image to a metadata-free 480p WebP."""

    if not raw:
        raise ImageProcessingError("Selecione uma imagem válida.")
    if len(raw) > MAX_IMAGE_UPLOAD_BYTES:
        raise ImageProcessingError("A imagem original deve ter no máximo 10 MB.")

    try:
        with Image.open(BytesIO(raw)) as source:
            source.load()
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ImageProcessingError("A imagem possui resolução alta demais.")
            image = ImageOps.exif_transpose(source)
            image.thumbnail(
                (MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT),
                Image.Resampling.LANCZOS,
            )
            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            normalized = image.convert("RGBA" if has_alpha else "RGB")
            output = BytesIO()
            normalized.save(
                output,
                format="WEBP",
                quality=WEBP_QUALITY,
                method=6,
                optimize=True,
            )
    except ImageProcessingError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageProcessingError("Envie uma imagem PNG, JPG ou WebP válida.") from exc

    return ProcessedImage(
        data=output.getvalue(),
        mime_type="image/webp",
        width=normalized.width,
        height=normalized.height,
    )

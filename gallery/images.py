from io import BytesIO
import warnings

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError


def validate_image(upload):
    """Inspect each file before saving any member of an upload batch."""
    if upload.size > settings.MAX_PHOTO_BYTES:
        raise ValidationError("Chaque photo doit peser au maximum 20 Mo.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            upload.seek(0)
            with Image.open(upload) as source:
                if source.width * source.height > settings.MAX_PHOTO_PIXELS:
                    raise ValidationError("Cette photo dépasse la limite de 40 mégapixels.")
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Choisissez une photo JPEG, PNG ou WebP.")
                if getattr(source, "is_animated", False):
                    raise ValidationError("Choisissez une image fixe, sans animation.")
                source.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as error:
        raise ValidationError("Impossible de lire cette photo. Choisissez un JPEG, PNG ou WebP valide.") from error


def prepare_image(upload):
    """Keep only resized pixels, never EXIF/GPS metadata; convert once per file."""
    try:
        upload.seek(0)
        with Image.open(upload) as source:
            source = ImageOps.exif_transpose(source)
            mode = "RGBA" if "A" in source.getbands() or "transparency" in source.info else "RGB"
            source = source.convert(mode)
            source.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
            clean = Image.frombytes(mode, source.size, source.tobytes())
        full = BytesIO()
        clean.save(full, "WEBP", quality=82, method=4)
        dimensions = clean.size
        clean.thumbnail((600, 600), Image.Resampling.LANCZOS)
        thumbnail = BytesIO()
        clean.save(thumbnail, "WEBP", quality=75, method=4)
        return full.getvalue(), thumbnail.getvalue(), dimensions
    except (OSError, ValueError) as error:
        raise ValidationError("Impossible de préparer cette photo. Le fichier est peut-être incomplet.") from error

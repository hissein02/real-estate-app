import os

from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 MB
MAX_DIMENSIONS = (3000, 3000)


def validate_logo(file):
    """Validate an uploaded logo file (format, size, dimensions)."""

    # 1. Check file size
    if file.size > MAX_LOGO_SIZE:
        raise ValidationError("Logo file too large. Maximum size is 2 MB.")

    # 2. Check extension
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 3. For raster images, validate with Pillow
    if ext != ".svg":
        from PIL import Image

        try:
            img = Image.open(file)
            img.verify()
            file.seek(0)
            img = Image.open(file)
            w, h = img.size
            if w > MAX_DIMENSIONS[0] or h > MAX_DIMENSIONS[1]:
                raise ValidationError(
                    f"Image dimensions {w}x{h} exceed maximum "
                    f"{MAX_DIMENSIONS[0]}x{MAX_DIMENSIONS[1]}."
                )
            file.seek(0)
        except ValidationError:
            raise
        except Exception:
            raise ValidationError("Invalid or corrupt image file.")
    else:
        # For SVG, basic content-type sniffing
        content_start = file.read(512)
        file.seek(0)
        if b"<svg" not in content_start.lower():
            raise ValidationError("Invalid SVG file.")

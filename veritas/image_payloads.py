"""Local image payload preparation helpers."""

import base64
import io
import mimetypes
from pathlib import Path

__all__ = ["_image_to_data_url", "_prepare_detector_upload_file"]


def _image_to_data_url(image_path: str):
    path = Path(image_path)
    try:
        from PIL import Image
        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((1400, 1400))
            side = max(512, img.width, img.height)
            side = min(side, 1600)
            canvas = Image.new("RGB", (side, side), "white")
            x = max(0, (side - img.width) // 2)
            y = max(0, (side - img.height) // 2)
            canvas.paste(img, (x, y))
            buf = io.BytesIO()
            canvas.save(buf, format="JPEG", quality=88, optimize=True)
            data = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{data}"
    except Exception:
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"


def _prepare_detector_upload_file(image_path: str):
    path = Path(image_path)
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    if mime in {"image/jpeg", "image/png", "image/webp"}:
        return path.name, mime, path.read_bytes()
    try:
        from PIL import Image
        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((1600, 1600))
            buf = io.BytesIO()
            buf_name = f"{path.stem}.jpg"
            img.save(buf, format="JPEG", quality=90, optimize=True)
            return buf_name, "image/jpeg", buf.getvalue()
    except Exception:
        return path.name, mime, path.read_bytes()

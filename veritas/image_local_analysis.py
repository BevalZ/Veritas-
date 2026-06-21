"""Local image sanity checks before provider review."""

from pathlib import Path

DEFAULT_MIN_IMAGE_BYTES = 5000

__all__ = [
    "DEFAULT_MIN_IMAGE_BYTES",
    "analyze_image_reasonability",
    "analyze_image_reasonability_from_namespace",
]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def analyze_image_reasonability(image_path: str, min_image_bytes=DEFAULT_MIN_IMAGE_BYTES):
    """Run lightweight local image sanity checks before external AI-image review."""
    result = {
        "path": str(image_path),
        "file": Path(image_path).name,
        "size_bytes": 0,
        "width": None,
        "height": None,
        "format": "",
        "risk": "needs_online_check",
        "issues": [],
    }
    try:
        path = Path(image_path)
        result["size_bytes"] = path.stat().st_size
        if result["size_bytes"] < min_image_bytes:
            result["issues"].append("too_small")
        try:
            from PIL import Image, ImageStat
            with Image.open(path) as img:
                result["width"], result["height"] = img.size
                result["format"] = img.format or path.suffix.lstrip(".")
                if result["width"] < 120 or result["height"] < 120:
                    result["issues"].append("low_resolution")
                ratio = max(result["width"], result["height"]) / max(1, min(result["width"], result["height"]))
                if ratio > 8:
                    result["issues"].append("extreme_aspect_ratio")
                stat = ImageStat.Stat(img.convert("L").resize((128, 128)))
                if stat.stddev and stat.stddev[0] < 3:
                    result["issues"].append("near_blank_or_flat")
                if stat.stddev and stat.stddev[0] > 85:
                    result["issues"].append("very_high_noise_or_contrast")
        except ImportError:
            result["issues"].append("pillow_not_installed")
        except Exception as e:
            result["issues"].append(f"image_parse_error:{type(e).__name__}")
    except Exception as e:
        result["issues"].append(f"file_error:{type(e).__name__}")

    severe = {"low_resolution", "near_blank_or_flat", "image_parse_error:UnidentifiedImageError"}
    if any(issue in severe or issue.startswith("file_error") for issue in result["issues"]):
        result["risk"] = "local_warning"
    elif not result["issues"]:
        result["risk"] = "local_ok"
    return result


def analyze_image_reasonability_from_namespace(namespace, image_path: str):
    return analyze_image_reasonability(
        image_path,
        min_image_bytes=_namespace_value(namespace, "MIN_IMAGE_BYTES", DEFAULT_MIN_IMAGE_BYTES),
    )

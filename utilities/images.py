import os
import warnings
from uuid import uuid4

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename


def _profile_pic_upload_dir_abs() -> str:
    configured = (
        current_app.config.get("UPLOAD_FOLDER_PROFILE_PICS")
        or current_app.config.get("PROFILE_PIC_UPLOAD_DIR")
        or os.path.join("static", "uploads", "profile_pics")
    )
    if os.path.isabs(configured):
        upload_dir = configured
    else:
        upload_dir = os.path.join(current_app.root_path, configured)
    os.makedirs(upload_dir, exist_ok=True)
    return os.path.abspath(upload_dir)


def save_profile_picture(file_storage) -> str:
    if not file_storage or not (file_storage.filename or "").strip():
        raise ValueError("Invalid image file.")

    sanitized = secure_filename(file_storage.filename)
    if not sanitized or sanitized != os.path.basename(sanitized) or sanitized.count(".") != 1:
        raise ValueError("Only PNG/JPG/JPEG/WEBP allowed.")

    stem, ext = sanitized.rsplit(".", 1)
    if not stem:
        raise ValueError("Only PNG/JPG/JPEG/WEBP allowed.")
    ext = ext.lower()

    allowed_exts = {str(item).lower() for item in current_app.config["PROFILE_PIC_ALLOWED_EXTS"]}
    if ext not in allowed_exts:
        raise ValueError("Only PNG/JPG/JPEG/WEBP allowed.")

    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    file_size = stream.tell()
    stream.seek(0)

    max_bytes = int(current_app.config.get("MAX_CONTENT_LENGTH") or 0)
    if file_size <= 0:
        raise ValueError("Invalid image file.")
    if max_bytes and file_size > max_bytes:
        raise ValueError("Image too large. Maximum upload size is 2MB.")

    max_w = int(current_app.config["PROFILE_PIC_MAX_W"])
    max_h = int(current_app.config["PROFILE_PIC_MAX_H"])
    max_pixels = int(current_app.config["PROFILE_PIC_MAX_PIXELS"])

    old_max_pixels = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                probe = Image.open(stream)
                probe.verify()
            except (
                UnidentifiedImageError,
                OSError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
                ValueError,
            ) as exc:
                raise ValueError("Invalid image file.") from exc

        stream.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                img = Image.open(stream)
                img = ImageOps.exif_transpose(img)
            except (
                UnidentifiedImageError,
                OSError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
                ValueError,
            ) as exc:
                raise ValueError("Invalid image file.") from exc

        width, height = img.size
        if width > max_w or height > max_h or (width * height) > max_pixels:
            raise ValueError(f"Image too large. Please upload an image under {max_w} by {max_h}.")

        out_w, out_h = current_app.config["PROFILE_PIC_OUTPUT_SIZE"]
        output_format = str(current_app.config["PROFILE_PIC_OUTPUT_FORMAT"]).upper()
        output_quality = int(current_app.config["PROFILE_PIC_OUTPUT_QUALITY"])

        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        right = left + side
        bottom = top + side
        img = img.crop((left, top, right, bottom))
        img = img.resize((int(out_w), int(out_h)), Image.Resampling.LANCZOS)

        if output_format == "WEBP":
            has_alpha = "A" in img.getbands()
            img = img.convert("RGBA" if has_alpha else "RGB")
            output_ext = "webp"
        else:
            img = img.convert("RGB")
            output_ext = output_format.lower()

        filename = f"{uuid4().hex}.{output_ext}"
        upload_dir = _profile_pic_upload_dir_abs()
        output_path = os.path.abspath(os.path.join(upload_dir, filename))
        if os.path.commonpath([upload_dir, output_path]) != upload_dir:
            raise ValueError("Invalid image file.")

        save_kwargs = {"format": output_format, "optimize": True}
        if output_format == "WEBP":
            save_kwargs.update({"quality": output_quality, "method": 6})
        img.save(output_path, **save_kwargs)
        return filename
    finally:
        Image.MAX_IMAGE_PIXELS = old_max_pixels
        stream.seek(0)


def delete_profile_picture(filename: str) -> None:
    candidate = (filename or "").strip()
    default_name = current_app.config.get("DEFAULT_PROFILE_IMAGE", "default.png")
    if not candidate or candidate == default_name:
        return
    if candidate != os.path.basename(candidate):
        return

    upload_dir = _profile_pic_upload_dir_abs()
    target_path = os.path.abspath(os.path.join(upload_dir, candidate))
    if os.path.commonpath([upload_dir, target_path]) != upload_dir:
        return

    try:
        os.remove(target_path)
    except FileNotFoundError:
        return
    except OSError:
        return

import random
import numpy as np
from PIL import Image, ImageFilter, ImageDraw


def scan_params_from_slider(value: int) -> dict:
    v = max(0, min(100, value))
    if v >= 80:
        t = (v - 80) / 20
        return {
            "dpi": 300,
            "tint_strength": 0.05 * (1 - t),
            "noise_amount": 3 * (1 - t),
            "tilt_max": 0.3 * (1 - t),
            "blur_radius": 0,
            "vignette_strength": 0,
        }
    elif v >= 40:
        t = (v - 40) / 40
        return {
            "dpi": int(200 + 100 * t),
            "tint_strength": 0.15 - 0.1 * t,
            "noise_amount": 8 - 5 * t,
            "tilt_max": 0.8 - 0.5 * t,
            "blur_radius": 0.5 * (1 - t),
            "vignette_strength": 0.3 * (1 - t),
        }
    else:
        t = v / 40
        return {
            "dpi": int(150 + 50 * t),
            "tint_strength": 0.25 - 0.1 * t,
            "noise_amount": 15 - 7 * t,
            "tilt_max": 1.5 - 0.7 * t,
            "blur_radius": 1.0 - 0.5 * t,
            "vignette_strength": 0.6 - 0.3 * t,
        }


def _apply_paper_tint(img, strength):
    tint = Image.new("RGB", img.size, (245, 235, 210))
    return Image.blend(img, tint, strength)


def _apply_noise(img, amount):
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, amount, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _apply_tilt(img, max_degrees):
    if max_degrees <= 0:
        return img
    angle = random.uniform(-max_degrees, max_degrees)
    return img.rotate(angle, expand=False, fillcolor=(245, 240, 230))


def _apply_vignette(img, strength):
    if strength <= 0:
        return img
    w, h = img.size
    vignette = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(vignette)
    border = int(min(w, h) * 0.1)
    for i in range(border):
        alpha = int(255 * (1 - strength * (1 - i / border)))
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=alpha)
    result = img.copy()
    result.putalpha(255)
    vignette_rgba = Image.merge("RGBA", (*img.split(), vignette))
    bg = Image.new("RGB", (w, h), (220, 215, 200))
    bg.paste(vignette_rgba, mask=vignette_rgba.split()[3])
    return bg


def apply_scan_to_image(img, params):
    result = img.convert("RGB")
    result = _apply_paper_tint(result, params["tint_strength"])
    result = _apply_noise(result, params["noise_amount"])
    result = _apply_tilt(result, params["tilt_max"])
    if params["blur_radius"] > 0:
        result = result.filter(ImageFilter.GaussianBlur(radius=params["blur_radius"]))
    result = _apply_vignette(result, params["vignette_strength"])
    return result

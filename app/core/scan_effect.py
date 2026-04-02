import random
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance


def scan_params_from_slider(value: int) -> dict:
    """Map slider value (0-100) to realistic scan parameters.

    Higher value = higher quality scan (cleaner).
    Lower value = lower quality scan (more artifacts).
    """
    v = max(0, min(100, value))

    if v >= 80:
        # High quality flatbed scan
        t = (v - 80) / 20  # 0..1
        return {
            "dpi": 300,
            "brightness_shift": 0.02 * (1 - t),
            "noise_amount": 1.5 * (1 - t),
            "tilt_max": 0.8 * (1 - t),
            "blur_radius": 0.3 * (1 - t),
            "edge_shadow": 0.1 * (1 - t),
            "corner_shadow": 0.15 * (1 - t),
            "brightness_nonuniform": 0.01 * (1 - t),
            "text_soften": 0.2 * (1 - t),
            "jpeg_quality": 95,
        }
    elif v >= 40:
        # Medium quality scan / decent phone scan
        t = (v - 40) / 40  # 0..1
        return {
            "dpi": int(200 + 100 * t),
            "brightness_shift": 0.05 - 0.03 * t,
            "noise_amount": 4 - 2.5 * t,
            "tilt_max": 1.5 - 0.7 * t,
            "blur_radius": 0.6 - 0.3 * t,
            "edge_shadow": 0.25 - 0.15 * t,
            "corner_shadow": 0.35 - 0.2 * t,
            "brightness_nonuniform": 0.03 - 0.02 * t,
            "text_soften": 0.5 - 0.3 * t,
            "jpeg_quality": int(85 + 10 * t),
        }
    else:
        # Low quality / old scanner / bad phone scan
        t = v / 40  # 0..1
        return {
            "dpi": int(150 + 50 * t),
            "brightness_shift": 0.08 - 0.03 * t,
            "noise_amount": 7 - 3 * t,
            "tilt_max": 2.5 - 1.0 * t,
            "blur_radius": 0.9 - 0.3 * t,
            "edge_shadow": 0.4 - 0.15 * t,
            "corner_shadow": 0.5 - 0.15 * t,
            "brightness_nonuniform": 0.05 - 0.02 * t,
            "text_soften": 0.8 - 0.3 * t,
            "jpeg_quality": int(75 + 10 * t),
        }


def _apply_brightness_shift(img: Image.Image, shift: float) -> Image.Image:
    """Slightly increase brightness to simulate scanner light wash-out."""
    if shift <= 0:
        return img
    enhancer = ImageEnhance.Brightness(img)
    return enhancer.enhance(1.0 + shift)


def _apply_noise(img: Image.Image, amount: float) -> Image.Image:
    """Add subtle, realistic sensor noise (not colored, grayscale-leaning)."""
    if amount <= 0:
        return img
    arr = np.array(img, dtype=np.float32)
    # Luminance-weighted noise (more realistic than per-channel)
    luma_noise = np.random.normal(0, amount, (arr.shape[0], arr.shape[1], 1))
    noise = np.repeat(luma_noise, 3, axis=2)
    # Add slight per-channel variation
    noise += np.random.normal(0, amount * 0.2, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _apply_tilt(img: Image.Image, max_degrees: float) -> Image.Image:
    """Slight page misalignment."""
    if max_degrees <= 0:
        return img
    angle = random.uniform(-max_degrees, max_degrees)
    # Use white fill (scanner background)
    return img.rotate(angle, expand=False, fillcolor=(252, 252, 250))


def _apply_text_soften(img: Image.Image, strength: float) -> Image.Image:
    """Soften text edges slightly to simulate optical capture."""
    if strength <= 0:
        return img
    radius = strength * 0.4
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    # Blend: keep most of original, mix in slight blur
    return Image.blend(img, blurred, min(strength * 0.3, 0.25))


def _apply_brightness_nonuniform(img: Image.Image, strength: float) -> Image.Image:
    """Simulate non-uniform lighting from scanner CCD/CIS sensor movement.

    Creates subtle brightness gradient (slightly darker at edges,
    with very subtle horizontal banding from sensor movement).
    """
    if strength <= 0:
        return img
    w, h = img.size
    arr = np.array(img, dtype=np.float32)

    # Radial falloff (center brighter, edges slightly darker)
    y_coords, x_coords = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    dist = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    falloff = 1.0 - strength * (dist / max_dist) * 0.5
    falloff = falloff[:, :, np.newaxis]

    # Subtle horizontal banding (scanner head movement artifact)
    band_freq = random.uniform(0.002, 0.005)
    band_phase = random.uniform(0, 2 * np.pi)
    banding = 1.0 + strength * 0.15 * np.sin(
        np.linspace(band_phase, band_phase + 2 * np.pi * h * band_freq, h)
    )
    banding = banding[:, np.newaxis, np.newaxis]

    arr = arr * falloff * banding
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _apply_edge_shadow(img: Image.Image, strength: float) -> Image.Image:
    """Simulate page edge shadow on scanner glass.

    More realistic than generic vignette - applies mainly to
    the bottom and right edges (as if page is slightly lifted).
    """
    if strength <= 0:
        return img
    w, h = img.size
    shadow = np.ones((h, w), dtype=np.float32)

    border = int(min(w, h) * 0.04)
    if border < 2:
        return img

    for i in range(border):
        factor = 1.0 - strength * 0.4 * ((border - i) / border) ** 2
        # Bottom edge (strongest)
        shadow[h - 1 - i, :] = min(shadow[h - 1 - i, 0], factor)
        # Right edge
        shadow[:, w - 1 - i] = np.minimum(shadow[:, w - 1 - i], factor * 1.05)
        # Top edge (weaker)
        shadow[i, :] = min(shadow[i, 0], factor * 1.15)
        # Left edge (weakest)
        shadow[:, i] = np.minimum(shadow[:, i], factor * 1.2)

    arr = np.array(img, dtype=np.float32)
    shadow = shadow[:, :, np.newaxis]
    arr = np.clip(arr * shadow, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _apply_corner_shadow(img: Image.Image, strength: float) -> Image.Image:
    """Add darkening at all four corners, simulating scanner lid shadow
    or phone camera vignetting. Uses smooth radial gradients from each corner.
    """
    if strength <= 0:
        return img
    w, h = img.size
    arr = np.array(img, dtype=np.float32)

    # Create shadow mask starting at 1.0 (no shadow)
    shadow = np.ones((h, w), dtype=np.float32)

    # Corner radius as fraction of the smaller dimension
    radius = min(w, h) * 0.35

    # Four corners with slightly different intensities for realism
    corners = [
        (0, 0, strength),                          # top-left
        (w, 0, strength * 0.85),                    # top-right
        (0, h, strength * 0.9),                     # bottom-left
        (w, h, strength * 1.1),                     # bottom-right (strongest)
    ]

    y_coords, x_coords = np.mgrid[0:h, 0:w]

    for cx, cy, s in corners:
        dist = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
        # Smooth falloff: darken when close to corner
        corner_mask = np.clip(dist / radius, 0, 1)
        # Invert: 0 at corner, 1 far away -> darken factor
        darken = 1.0 - s * 0.4 * (1.0 - corner_mask) ** 2
        shadow = np.minimum(shadow, darken)

    arr *= shadow[:, :, np.newaxis]
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def apply_scan_to_image(img: Image.Image, params: dict) -> Image.Image:
    """Apply realistic scan effects to a single page image.

    Pipeline order matters:
    1. Brightness shift (scanner light wash)
    2. Non-uniform brightness (sensor characteristics)
    3. Text softening (optical capture)
    4. Noise (sensor noise)
    5. Tilt (page misalignment)
    6. Edge shadow (page lift)
    7. Corner shadow (four-corner darkening)
    """
    result = img.convert("RGB")
    result = _apply_brightness_shift(result, params["brightness_shift"])
    result = _apply_brightness_nonuniform(result, params["brightness_nonuniform"])
    result = _apply_text_soften(result, params["text_soften"])
    result = _apply_noise(result, params["noise_amount"])
    result = _apply_tilt(result, params["tilt_max"])
    result = _apply_edge_shadow(result, params["edge_shadow"])
    result = _apply_corner_shadow(result, params.get("corner_shadow", 0))
    return result

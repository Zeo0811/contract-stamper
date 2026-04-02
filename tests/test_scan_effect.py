import os
from PIL import Image
from app.core.scan_effect import apply_scan_to_image, scan_params_from_slider


def test_scan_params_light():
    params = scan_params_from_slider(90)
    assert params["dpi"] == 300
    assert params["tilt_max"] <= 0.3


def test_scan_params_heavy():
    params = scan_params_from_slider(10)
    assert params["dpi"] <= 175
    assert params["tilt_max"] >= 0.8


def test_apply_scan_to_image():
    img = Image.new("RGB", (600, 800), (255, 255, 255))
    params = scan_params_from_slider(50)
    result = apply_scan_to_image(img, params)
    assert isinstance(result, Image.Image)
    assert result.size[0] > 0
    assert result.size[1] > 0


def test_scan_effect_changes_pixels():
    img = Image.new("RGB", (100, 100), (255, 255, 255))
    params = scan_params_from_slider(30)
    result = apply_scan_to_image(img, params)
    original_pixels = list(img.getdata())
    result_pixels = list(result.getdata())
    assert original_pixels != result_pixels

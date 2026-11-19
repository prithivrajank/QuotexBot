import pytest

from visual_engine.visual_config import validate_region


def test_valid_region():
    region = {"left": 100, "top": 120, "width": 800, "height": 500}
    assert validate_region(region, 1920, 1080) == region


def test_rejects_region_outside_monitor():
    with pytest.raises(ValueError):
        validate_region({"left": 1800, "top": 10, "width": 200, "height": 300}, 1920, 1080)


def test_rejects_tiny_region():
    with pytest.raises(ValueError):
        validate_region({"left": 0, "top": 0, "width": 50, "height": 50}, 1920, 1080)

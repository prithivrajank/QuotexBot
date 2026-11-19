"""Configuration helpers for the local chart-region capture tool."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent / "region_config.json"


def validate_region(region: dict[str, int], screen_width: int, screen_height: int) -> dict[str, int]:
    required = ("left", "top", "width", "height")
    if any(key not in region for key in required):
        raise ValueError("Region must contain left, top, width and height")
    result = {key: int(region[key]) for key in required}
    if result["left"] < 0 or result["top"] < 0:
        raise ValueError("Region coordinates cannot be negative")
    if result["width"] < 80 or result["height"] < 80:
        raise ValueError("Selected region is too small; choose a chart area at least 80x80 pixels")
    if result["left"] + result["width"] > screen_width or result["top"] + result["height"] > screen_height:
        raise ValueError("Selected region extends beyond the captured monitor")
    return result


def save_region(region: dict[str, int], path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(region, indent=2), encoding="utf-8")


def load_region(path: Path = CONFIG_PATH) -> dict[str, int] | None:
    if not path.exists():
        return None
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Region config must be a JSON object")
    return {key: int(data[key]) for key in ("left", "top", "width", "height")}

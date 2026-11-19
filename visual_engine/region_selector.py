"""Mouse-drag selector for choosing the chart rectangle on a monitor screenshot."""
from __future__ import annotations

import cv2
import numpy as np


def select_region(screen_bgr: np.ndarray) -> dict[str, int] | None:
    if screen_bgr is None or screen_bgr.size == 0:
        raise ValueError("The monitor screenshot is empty")
    print("\nDrag a rectangle around ONLY the Quotex candle chart, then press ENTER/SPACE.")
    print("Press C or ESC to cancel. Avoid the pair tabs, trade buttons and browser controls.")
    x, y, width, height = cv2.selectROI(
        "Select Quotex chart region - ENTER to confirm",
        screen_bgr,
        showCrosshair=True,
        fromCenter=False,
    )
    cv2.destroyWindow("Select Quotex chart region - ENTER to confirm")
    if width <= 0 or height <= 0:
        return None
    return {"left": int(x), "top": int(y), "width": int(width), "height": int(height)}

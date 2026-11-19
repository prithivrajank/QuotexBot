"""Local chart-only screen capture preview. No browser or account data is read."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import mss
import numpy as np

from visual_engine.region_selector import select_region
from visual_engine.visual_config import CONFIG_PATH, load_region, save_region, validate_region

WINDOW = "Quotex chart region preview | Q quit | R reselect | P pause"


def capture_monitor(sct: mss.mss, monitor_index: int) -> tuple[np.ndarray, dict[str, int]]:
    monitors = sct.monitors
    if monitor_index < 1 or monitor_index >= len(monitors):
        raise ValueError(f"Monitor {monitor_index} unavailable. Detected {len(monitors) - 1} monitor(s).")
    monitor = monitors[monitor_index]
    shot = np.asarray(sct.grab(monitor))
    return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR), {
        "left": int(monitor["left"]), "top": int(monitor["top"]),
        "width": int(monitor["width"]), "height": int(monitor["height"]),
    }


def run(monitor_index: int = 1, fps: float = 5.0, force_select: bool = False) -> int:
    if fps <= 0 or fps > 15:
        raise ValueError("Preview FPS must be greater than 0 and no more than 15")
    print("Quotex visual capture - READ ONLY")
    print("This tool captures screen pixels only. It does not inspect browser storage, credentials or network traffic.")
    print("Open Quotex Demo in maximized Chrome before selecting the chart region.")

    with mss.mss() as sct:
        screen, monitor = capture_monitor(sct, monitor_index)
        region = None if force_select else load_region()
        if region is not None:
            try:
                region = validate_region(region, monitor["width"], monitor["height"])
            except (ValueError, KeyError, TypeError):
                print("Saved region is invalid for this screen; please select it again.")
                region = None

        if region is None:
            selected = select_region(screen)
            if selected is None:
                print("Selection cancelled. No capture started.")
                return 1
            region = validate_region(selected, monitor["width"], monitor["height"])
            save_region(region)
            print(f"Saved chart region to {CONFIG_PATH}")

        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        paused = False
        delay = 1.0 / fps
        try:
            while True:
                started = time.perf_counter()
                if not paused:
                    frame, current_monitor = capture_monitor(sct, monitor_index)
                    if (current_monitor["width"], current_monitor["height"]) != (monitor["width"], monitor["height"]):
                        print("Screen dimensions changed. Restart and select the region again.")
                        break
                    x, y, w, h = region["left"], region["top"], region["width"], region["height"]
                    chart = frame[y:y+h, x:x+w].copy()
                    if chart.size == 0:
                        print("Selected region is no longer available. Press R to select again.")
                    else:
                        cv2.imshow(WINDOW, chart)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    print("Capture stopped by user.")
                    break
                if key == ord("p"):
                    paused = not paused
                    print("Preview paused." if paused else "Preview resumed.")
                if key == ord("r"):
                    screen, monitor = capture_monitor(sct, monitor_index)
                    selected = select_region(screen)
                    if selected is None:
                        print("Reselection cancelled; keeping previous region.")
                    else:
                        region = validate_region(selected, monitor["width"], monitor["height"])
                        save_region(region)
                        print("New chart region saved.")
                remaining = delay - (time.perf_counter() - started)
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            cv2.destroyAllWindows()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture a selected Quotex chart rectangle locally (read-only).")
    parser.add_argument("--monitor", type=int, default=1, help="MSS monitor index; 1 is the primary monitor")
    parser.add_argument("--fps", type=float, default=5.0, help="Preview frame rate (1-15; default 5)")
    parser.add_argument("--select", action="store_true", help="Force chart-region selection again")
    args = parser.parse_args()
    raise SystemExit(run(args.monitor, args.fps, args.select))


if __name__ == "__main__":
    main()

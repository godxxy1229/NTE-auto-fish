import json
import time
from pathlib import Path

import cv2
import numpy as np
import pyautogui

try:
    import mss
except ImportError:
    mss = None


PROJECT_DIR = Path(__file__).resolve().parent


def load_region():
    config = json.loads((PROJECT_DIR / "config.json").read_text(encoding="utf-8"))
    rois = []
    for key in ("bar_roi", "bite_roi", "success_roi"):
        x, y, w, h = [int(v) for v in config[key]]
        rois.append((x, y, w, h))

    margin = 6
    x1 = max(0, min(x for x, _, _, _ in rois) - margin)
    y1 = max(0, min(y for _, y, _, _ in rois) - margin)
    x2 = max(x + w for x, _, w, _ in rois) + margin
    y2 = max(y + h for _, y, _, h in rois) + margin
    return int(x1), int(y1), int(x2 - x1), int(y2 - y1)


def bench_pyautogui(region, count):
    for _ in range(2):
        pyautogui.screenshot(region=region)

    start = time.perf_counter()
    for _ in range(count):
        np.array(pyautogui.screenshot(region=region))
    elapsed = time.perf_counter() - start
    return elapsed * 1000 / count


def bench_mss(region, count):
    if mss is None:
        return None

    x, y, w, h = region
    monitor = {"left": x, "top": y, "width": w, "height": h}
    factory = getattr(mss, "MSS", mss.mss)
    with factory() as sct:
        for _ in range(2):
            frame = np.array(sct.grab(monitor))
            cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

        start = time.perf_counter()
        for _ in range(count):
            frame = np.array(sct.grab(monitor))
            cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        elapsed = time.perf_counter() - start
    return elapsed * 1000 / count


def main():
    region = load_region()
    count = 30
    print(f"region={region} pixels={region[2] * region[3]}")

    pyautogui_ms = bench_pyautogui(region, count)
    print(f"pyautogui: {pyautogui_ms:.2f} ms/capture, {1000 / pyautogui_ms:.1f} fps")

    mss_ms = bench_mss(region, count)
    if mss_ms is None:
        print("mss: not installed")
    else:
        print(f"mss:       {mss_ms:.2f} ms/capture, {1000 / mss_ms:.1f} fps")


if __name__ == "__main__":
    main()

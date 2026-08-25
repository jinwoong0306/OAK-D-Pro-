"""Measure stereo-depth stability for one physical test condition.

Example:
    python depth_condition_test.py --label "1m_front_bright"
"""

import argparse
import csv
from datetime import datetime
from pathlib import Path
import time

import depthai as dai
import numpy as np


RESULTS_PATH = Path("data/measurements/depth_validation_results.csv")
STEREO_SIZE = (1280, 800)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="Short description of the test condition")
    parser.add_argument("--frames", type=int, default=100, help="Number of depth frames to sample")
    parser.add_argument("--actual-m", type=float, help="Tape-measured target distance in metres")
    args = parser.parse_args()

    pipeline = dai.Pipeline()
    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    stereo = pipeline.create(dai.node.StereoDepth)
    left.requestOutput(STEREO_SIZE).link(stereo.left)
    right.requestOutput(STEREO_SIZE).link(stereo.right)
    # Use the same short-range stereo configuration as the demo so the
    # validation result represents the distance pipeline used by the dashboard.
    stereo.setLeftRightCheck(True)
    stereo.setExtendedDisparity(True)
    depth_queue = stereo.depth.createOutputQueue(maxSize=4, blocking=False)

    samples: list[float] = []
    valid_ratios: list[float] = []
    start = time.monotonic()

    with pipeline:
        pipeline.start()
        for _ in range(args.frames):
            frame = depth_queue.get().getFrame()
            height, width = frame.shape
            roi = frame[height * 2 // 5 : height * 3 // 5, width * 2 // 5 : width * 3 // 5]
            valid = roi[roi > 0]
            valid_ratios.append(valid.size / roi.size)
            if valid.size:
                samples.append(float(np.median(valid)))

    elapsed = time.monotonic() - start
    has_valid_depth = bool(samples)
    median_mm = float(np.median(samples)) if has_valid_depth else None
    actual_mm = args.actual_m * 1000 if args.actual_m is not None else None
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": args.label,
        "frames": len(samples),
        "fps": round(len(samples) / elapsed, 2),
        "actual_mm": round(actual_mm, 1) if actual_mm is not None else "",
        "median_mm": round(median_mm, 1) if median_mm is not None else "",
        "error_mm": round(median_mm - actual_mm, 1) if median_mm is not None and actual_mm is not None else "",
        "error_percent": round((median_mm - actual_mm) / actual_mm * 100, 2)
        if median_mm is not None and actual_mm not in (None, 0) else "",
        "p10_mm": round(float(np.percentile(samples, 10)), 1) if has_valid_depth else "",
        "p90_mm": round(float(np.percentile(samples, 90)), 1) if has_valid_depth else "",
        "variation_mm": round(float(np.percentile(samples, 90) - np.percentile(samples, 10)), 1) if has_valid_depth else "",
        "valid_roi_percent": round(float(np.mean(valid_ratios) * 100), 1),
    }

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    write_header = not RESULTS_PATH.exists()
    with RESULTS_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=result.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(result)

    print(result)
    print(f"Saved: {RESULTS_PATH}")


if __name__ == "__main__":
    main()

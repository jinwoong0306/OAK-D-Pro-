"""Record detection throughput for one named camera condition."""

import argparse
import csv
from datetime import datetime
from pathlib import Path
import time

import depthai as dai


RESULTS_PATH = Path("data/measurements/performance_results.csv")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()

    with dai.Pipeline() as pipeline:
        camera = pipeline.create(dai.node.Camera).build()
        detector = pipeline.create(dai.node.DetectionNetwork).build(
            camera, dai.NNModelDescription("yolov6-nano")
        )
        detector.setConfidenceThreshold(0.5)
        detector.input.setBlocking(False)
        labels = detector.getClasses() or []
        frame_queue = detector.passthrough.createOutputQueue(maxSize=4, blocking=False)
        detection_queue = detector.out.createOutputQueue(maxSize=4, blocking=False)

        pipeline.start()
        started = time.monotonic()
        frames = detection_messages = detections = 0
        classes: set[str] = set()
        while time.monotonic() - started < args.seconds:
            if frame_queue.tryGet() is not None:
                frames += 1
            message = detection_queue.tryGet()
            if message is not None:
                detection_messages += 1
                detections += len(message.detections)
                for detection in message.detections:
                    classes.add(labels[detection.label] if detection.label < len(labels) else str(detection.label))

    elapsed = time.monotonic() - started
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": args.label,
        "seconds": round(elapsed, 2),
        "fps": round(frames / elapsed, 2),
        "detection_messages": detection_messages,
        "detections": detections,
        "classes": ";".join(sorted(classes)),
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    header = not RESULTS_PATH.exists()
    with RESULTS_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=result.keys())
        if header:
            writer.writeheader()
        writer.writerow(result)
    print(result)


if __name__ == "__main__":
    main()

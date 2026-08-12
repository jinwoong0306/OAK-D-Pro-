"""Live YOLOv6-Nano detection with stereo-depth ROI median distance.

Press Q to close the preview.
"""

from collections import deque
import csv
from datetime import datetime
from pathlib import Path
import time

import cv2
import depthai as dai
import numpy as np


WARNING_DISTANCE_M = 1.2
LOG_PATH = Path("data/logs/detections.csv")
SNAPSHOT_DIR = Path("data/logs/warning_frames")


class MedianDistanceFilter:
    """Reject implausible jumps and smooth the last few valid distances."""

    def __init__(self, window_size: int = 5, max_jump_m: float = 0.7) -> None:
        self.values: deque[float] = deque(maxlen=window_size)
        self.max_jump_m = max_jump_m

    def update(self, raw_mm: float | None) -> float | None:
        if raw_mm is None:
            return None
        raw_m = raw_mm / 1000
        if self.values and abs(raw_m - float(np.median(self.values))) > self.max_jump_m:
            return float(np.median(self.values))
        self.values.append(raw_m)
        return float(np.median(self.values))


class DetectionLogger:
    """Append bounded-rate detection records and warning snapshots."""

    def __init__(self) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.last_logged: dict[str, float] = {}
        self.last_snapshot = 0.0
        self.write_header = not LOG_PATH.exists()

    def log(self, label: str, confidence: float, distance_m: float | None,
            is_warning: bool, frame: np.ndarray) -> None:
        now = time.monotonic()
        # Log each label at most once a second to keep the CSV usable.
        if now - self.last_logged.get(label, 0.0) < 1.0:
            return
        self.last_logged[label] = now
        timestamp = datetime.now()
        with LOG_PATH.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=[
                "timestamp", "label", "confidence", "distance_m", "warning"
            ])
            if self.write_header:
                writer.writeheader()
                self.write_header = False
            writer.writerow({
                "timestamp": timestamp.isoformat(timespec="seconds"),
                "label": label,
                "confidence": round(confidence, 4),
                "distance_m": round(distance_m, 3) if distance_m is not None else "",
                "warning": is_warning,
            })
        if is_warning and now - self.last_snapshot >= 5.0:
            path = SNAPSHOT_DIR / f"warning_{timestamp:%Y%m%d_%H%M%S}.png"
            cv2.imwrite(str(path), frame)
            self.last_snapshot = now


def roi_median_depth(depth: np.ndarray, detection: dai.ImgDetection) -> float | None:
    """Return depth median (mm) from the central part of a detection box."""
    height, width = depth.shape
    x1, y1 = int(detection.xmin * width), int(detection.ymin * height)
    x2, y2 = int(detection.xmax * width), int(detection.ymax * height)
    # Contract the box to reduce background leakage at the edges.
    margin_x, margin_y = (x2 - x1) // 5, (y2 - y1) // 5
    roi = depth[y1 + margin_y : y2 - margin_y, x1 + margin_x : x2 - margin_x]
    valid = roi[(roi >= 100) & (roi <= 3000)]
    return float(np.median(valid)) if valid.size else None


def main() -> None:
    with dai.Pipeline() as pipeline:
        camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
        right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
        stereo = pipeline.create(dai.node.StereoDepth)
        left.requestFullResolutionOutput().link(stereo.left)
        right.requestFullResolutionOutput().link(stereo.right)

        detector = pipeline.create(dai.node.DetectionNetwork).build(
            camera, dai.NNModelDescription("yolov6-nano")
        )
        detector.setConfidenceThreshold(0.5)
        detector.input.setBlocking(False)

        labels = detector.getClasses() or []
        rgb_queue = detector.passthrough.createOutputQueue(maxSize=4, blocking=False)
        detection_queue = detector.out.createOutputQueue(maxSize=4, blocking=False)
        depth_queue = stereo.depth.createOutputQueue(maxSize=4, blocking=False)

        pipeline.start()
        cv2.namedWindow("OAK-D Pro Object Distance", cv2.WINDOW_NORMAL)
        detections = []
        latest_depth = None
        distance_filters: dict[str, MedianDistanceFilter] = {}
        logger = DetectionLogger()
        previous = time.monotonic()
        fps = 0.0

        while pipeline.isRunning():
            message = detection_queue.tryGet()
            if message is not None:
                detections = message.detections
            message = depth_queue.tryGet()
            if message is not None:
                latest_depth = message.getFrame()
            message = rgb_queue.tryGet()
            if message is None:
                if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                    break
                continue

            frame = message.getCvFrame()
            now = time.monotonic()
            fps = 0.9 * fps + 0.1 / max(now - previous, 0.001)
            previous = now
            height, width = frame.shape[:2]
            warning_count = 0
            object_summaries: list[str] = []

            for detection in detections:
                x1, y1 = int(detection.xmin * width), int(detection.ymin * height)
                x2, y2 = int(detection.xmax * width), int(detection.ymax * height)
                label = labels[detection.label] if detection.label < len(labels) else str(detection.label)
                raw_distance = roi_median_depth(latest_depth, detection) if latest_depth is not None else None
                distance_filter = distance_filters.setdefault(label, MedianDistanceFilter())
                distance = distance_filter.update(raw_distance)
                distance_text = f"{distance:.2f}m" if distance is not None else "N/A"
                text = f"{label} {detection.confidence:.0%} | {distance_text}"
                is_warning = distance is not None and distance <= WARNING_DISTANCE_M
                warning_count += int(is_warning)
                color = (0, 0, 255) if is_warning else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, text, (x1, max(28, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, color, 2, cv2.LINE_AA)
                if is_warning:
                    cv2.putText(frame, "WARNING: TOO CLOSE", (x1, min(height - 12, y2 + 26)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2, cv2.LINE_AA)
                logger.log(label, detection.confidence, distance, is_warning, frame)
                object_summaries.append(f"{label}: {distance_text}")

            cv2.rectangle(frame, (0, 0), (width, 92), (25, 25, 25), thickness=-1)
            status = "WARNING" if warning_count else "CLEAR"
            status_color = (0, 0, 255) if warning_count else (0, 220, 0)
            cv2.putText(frame, "OAK-D Pro Safety Demo", (16, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.75, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, f"FPS {fps:.1f}  |  Objects {len(detections)}", (16, 58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, (220, 220, 220), 2, cv2.LINE_AA)
            cv2.putText(frame, f"STATUS: {status}", (16, 84), cv2.FONT_HERSHEY_SIMPLEX,
                        0.65, status_color, 2, cv2.LINE_AA)
            if object_summaries:
                summary = "  ".join(object_summaries[:2])
                cv2.putText(frame, summary, (min(310, width // 2), 84), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow("OAK-D Pro Object Distance", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Demo stopped by user.")
    except RuntimeError as error:
        # DepthAI raises RuntimeError for a missing camera or a broken XLink.
        print(f"Camera or pipeline error: {error}")
        print("Check the USB3 cable, reconnect the OAK-D Pro, then run the demo again.")
    except Exception as error:
        print(f"Unexpected demo error: {error}")
    finally:
        cv2.destroyAllWindows()

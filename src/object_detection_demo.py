"""Live COCO object detection on OAK-D Pro using DepthAI YOLOv6-Nano.

Press Q to close the preview.
"""

import time

import cv2
import depthai as dai


def main() -> None:
    with dai.Pipeline() as pipeline:
        camera = pipeline.create(dai.node.Camera).build()
        model = dai.NNModelDescription("yolov6-nano")
        detector = pipeline.create(dai.node.DetectionNetwork).build(camera, model)
        detector.setConfidenceThreshold(0.5)
        detector.input.setBlocking(False)

        labels = detector.getClasses() or []
        rgb_queue = detector.passthrough.createOutputQueue(maxSize=4, blocking=False)
        detection_queue = detector.out.createOutputQueue(maxSize=4, blocking=False)

        pipeline.start()
        cv2.namedWindow("OAK-D Pro Object Detection", cv2.WINDOW_NORMAL)
        detections = []
        previous = time.monotonic()
        fps = 0.0

        while pipeline.isRunning():
            detection_message = detection_queue.tryGet()
            if detection_message is not None:
                detections = detection_message.detections

            frame_message = rgb_queue.tryGet()
            if frame_message is None:
                if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                    break
                continue

            frame = frame_message.getCvFrame()
            now = time.monotonic()
            fps = 0.9 * fps + 0.1 / max(now - previous, 0.001)
            previous = now

            height, width = frame.shape[:2]
            for detection in detections:
                x1, y1 = int(detection.xmin * width), int(detection.ymin * height)
                x2, y2 = int(detection.xmax * width), int(detection.ymax * height)
                label = labels[detection.label] if detection.label < len(labels) else str(detection.label)
                text = f"{label} {detection.confidence:.0%}"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, text, (x1, max(28, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, (0, 255, 0), 2, cv2.LINE_AA)

            cv2.putText(frame, f"YOLOv6-Nano {fps:.1f} FPS", (16, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.imshow("OAK-D Pro Object Detection", frame)

            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

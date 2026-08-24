"""Live RGB and stereo-depth preview for OAK-D Pro.

Press Q in either OpenCV window to stop.
"""

import time

import cv2
import depthai as dai
import numpy as np

STEREO_SIZE = (1280, 800)


def colorize_depth(depth: np.ndarray) -> np.ndarray:
    valid = depth[depth > 0]
    if valid.size == 0:
        return np.zeros((*depth.shape, 3), dtype=np.uint8)

    low, high = np.percentile(valid, (3, 95))
    normalized = np.clip((depth - low) / max(high - low, 1) * 255, 0, 255).astype(np.uint8)
    colored = cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO)
    colored[depth == 0] = (0, 0, 0)
    return colored


def main() -> None:
    pipeline = dai.Pipeline()
    color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    stereo = pipeline.create(dai.node.StereoDepth)

    left.requestOutput(STEREO_SIZE).link(stereo.left)
    right.requestOutput(STEREO_SIZE).link(stereo.right)
    rgb_queue = color.requestOutput(
        (640, 400), type=dai.ImgFrame.Type.BGR888i
    ).createOutputQueue(maxSize=4, blocking=False)
    depth_queue = stereo.depth.createOutputQueue(maxSize=4, blocking=False)

    cv2.namedWindow("OAK-D Pro RGB", cv2.WINDOW_NORMAL)
    cv2.namedWindow("OAK-D Pro Stereo Depth", cv2.WINDOW_NORMAL)

    with pipeline:
        pipeline.start()
        last_time = time.monotonic()
        frames = 0
        fps = 0.0

        while pipeline.isRunning():
            rgb_frame = rgb_queue.tryGet()
            depth_frame = depth_queue.tryGet()

            if rgb_frame is not None:
                rgb = rgb_frame.getCvFrame()
                frames += 1
                elapsed = time.monotonic() - last_time
                if elapsed >= 1:
                    fps = frames / elapsed
                    frames = 0
                    last_time = time.monotonic()
                cv2.putText(rgb, f"RGB {fps:.1f} FPS", (16, 32), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0, 255, 0), 2, cv2.LINE_AA)
                cv2.imshow("OAK-D Pro RGB", rgb)

            if depth_frame is not None:
                depth = depth_frame.getFrame()
                preview = colorize_depth(depth)
                cv2.putText(preview, "Stereo depth", (16, 32), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.imshow("OAK-D Pro Stereo Depth", preview)

            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

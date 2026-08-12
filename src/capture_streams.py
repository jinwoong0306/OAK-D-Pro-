"""Capture one RGB and one stereo-depth frame from the connected OAK-D Pro."""

from pathlib import Path
import time

import cv2
import depthai as dai
import numpy as np


OUTPUT_DIR = Path("data/captures")


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    pipeline = dai.Pipeline()
    color = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    stereo = pipeline.create(dai.node.StereoDepth)

    left.requestFullResolutionOutput().link(stereo.left)
    right.requestFullResolutionOutput().link(stereo.right)

    rgb_queue = color.requestOutput(
        (640, 400), type=dai.ImgFrame.Type.BGR888i
    ).createOutputQueue(maxSize=4, blocking=False)
    depth_queue = stereo.depth.createOutputQueue(maxSize=4, blocking=False)

    with pipeline:
        pipeline.start()
        rgb = rgb_queue.get().getCvFrame()
        depth = depth_queue.get().getFrame()

        valid_depth = depth[depth > 0]
        if valid_depth.size == 0:
            raise RuntimeError("No valid depth pixels received.")

        # Use robust percentiles so the stored visualization is readable.
        low, high = np.percentile(valid_depth, (3, 95))
        normalized = np.clip((depth - low) / max(high - low, 1) * 255, 0, 255).astype(np.uint8)
        depth_color = cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO)
        depth_color[depth == 0] = (0, 0, 0)

        rgb_path = OUTPUT_DIR / "rgb_preview.png"
        depth_path = OUTPUT_DIR / "depth_preview.png"
        cv2.imwrite(str(rgb_path), rgb)
        cv2.imwrite(str(depth_path), depth_color)

        print(f"Device MXID: {pipeline.getDefaultDevice().getDeviceId()}")
        print(f"Saved RGB: {rgb_path} ({rgb.shape[1]}x{rgb.shape[0]})")
        print(f"Saved depth: {depth_path} ({depth.shape[1]}x{depth.shape[0]})")
        print(f"Valid depth range: {int(valid_depth.min())}-{int(valid_depth.max())} mm")


if __name__ == "__main__":
    main()

"""
Generates a lightweight sample video for demo and cloud testing.
"""
import sys
from pathlib import Path
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "dashboard" / "static" / "video" / "demo_sample.mp4"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def create_demo_video():
    width, height = 640, 480
    fps = 20
    duration_sec = 6
    total_frames = fps * duration_sec

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(OUT_PATH), fourcc, fps, (width, height))

    for i in range(total_frames):
        # Create a background frame simulating a workplace area
        frame = np.full((height, width, 3), 40, dtype=np.uint8)

        # Floor and wall simulation
        cv2.rectangle(frame, (0, 320), (width, height), (70, 70, 70), -1)
        cv2.line(frame, (0, 320), (width, 320), (120, 120, 120), 2)

        # Moving worker representation
        x_pos = int(150 + 150 * np.sin(i / 15.0))
        y_pos = 180

        # Draw person figure
        # Head
        cv2.circle(frame, (x_pos + 40, y_pos + 30), 25, (180, 180, 180), -1)
        # Body
        cv2.rectangle(frame, (x_pos + 15, y_pos + 55), (x_pos + 65, y_pos + 160), (0, 140, 255), -1)
        # Legs
        cv2.line(frame, (x_pos + 25, y_pos + 160), (x_pos + 20, y_pos + 240), (200, 200, 200), 8)
        cv2.line(frame, (x_pos + 55, y_pos + 160), (x_pos + 60, y_pos + 240), (200, 200, 200), 8)

        # Text overlay
        cv2.putText(frame, "SafetyEye Cloud Demo Stream", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)
        cv2.putText(frame, f"Frame: {i+1}/{total_frames}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)

        out.write(frame)

    out.release()
    print(f"[+] Generated sample video at: {OUT_PATH}")


if __name__ == "__main__":
    create_demo_video()

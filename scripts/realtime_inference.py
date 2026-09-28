"""
Standalone Realtime Inference CLI for SafetyEye PPE Detection.
Usage:
    python scripts/realtime_inference.py --source 0
    python scripts/realtime_inference.py --source path/to/video.mp4
"""
import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.utils.detection_utils import apply_rules
from dashboard.utils.alert_manager import trigger_alert_async


def main():
    parser = argparse.ArgumentParser(description="SafetyEye Standalone PPE Detection")
    parser.add_argument("--source", default="0", help="Video source (camera index or video path)")
    parser.add_argument("--model", default=str(PROJECT_ROOT / "model" / "best.pt"), help="Path to YOLO weights")
    parser.add_argument("--conf", type=float, default=0.45, help="Confidence threshold")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "dashboard" / "static" / "video" / "inference_output.mp4"), help="Output video path")
    args = parser.parse_args()

    # Source handling
    source = int(args.source) if args.source.isdigit() else args.source

    print(f"[*] Loading model from: {args.model}")
    model = YOLO(args.model)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[!] Error: Unable to open video source: {source}")
        sys.exit(1)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 25.0

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(args.output, fourcc, fps_in, (width, height))

    print(f"[*] Processing stream... Press 'q' in preview window to exit.")

    frame_count = 0
    t0 = time.time()

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            results = model.predict(frame[..., ::-1], imgsz=640, conf=args.conf, verbose=False)
            r = results[0]

            detections = []
            annotated = frame.copy()

            if r.boxes is not None:
                for box, cls, conf in zip(
                    r.boxes.xyxy.cpu().numpy(),
                    r.boxes.cls.cpu().numpy(),
                    r.boxes.conf.cpu().numpy(),
                ):
                    cls = int(cls)
                    label = model.names.get(cls, f"class_{cls}")
                    x1, y1, x2, y2 = map(int, box)
                    detections.append({"class": label, "confidence": float(conf), "bbox": [x1, y1, x2, y2]})

                    color = (0, 255, 0) if "no-" not in label.lower() and label.lower() in ["hardhat", "safety vest"] else (0, 0, 255)
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(annotated, f"{label} {conf:.2f}", (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            violations = apply_rules(detections)
            if violations:
                cv2.putText(annotated, f"VIOLATION: {', '.join(violations)}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            out.write(annotated)
            frame_count += 1

            # Show window if display is available
            cv2.imshow("SafetyEye Detection", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        out.release()
        cv2.destroyAllWindows()
        elapsed = time.time() - t0
        print(f"[*] Done! Processed {frame_count} frames in {elapsed:.2f}s ({frame_count / max(elapsed, 0.001):.1f} FPS).")
        print(f"[*] Output saved to: {args.output}")


if __name__ == "__main__":
    main()

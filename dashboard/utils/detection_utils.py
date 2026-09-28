import time
from pathlib import Path
from typing import List, Dict, Tuple, Any

import cv2
import numpy as np
import torch
from ultralytics import YOLO


class Detector:
    """YOLOv8 PPE Detector wrapper for SafetyEye."""

    def __init__(self, model_path: str, conf_thresh: float = 0.4):
        self.model_path = str(model_path)
        self.conf_thresh = float(conf_thresh)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = YOLO(self.model_path).to(self.device)
        self.class_names = self.model.names

    def run_on_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Dict[str, Any]], float]:
        """Run YOLO inference on a single BGR OpenCV frame."""
        t0 = time.time()
        
        # YOLO expects RGB
        results = self.model.predict(
            frame[..., ::-1],
            imgsz=640,
            conf=self.conf_thresh,
            device=self.device,
            verbose=False,
        )
        r = results[0]

        annotated = frame.copy()
        detections = []

        if r.boxes is not None and len(r.boxes) > 0:
            for box, cls, conf in zip(
                r.boxes.xyxy.cpu().numpy(),
                r.boxes.cls.cpu().numpy(),
                r.boxes.conf.cpu().numpy(),
            ):
                conf = float(conf)
                cls = int(cls)

                if conf < self.conf_thresh:
                    continue

                x1, y1, x2, y2 = map(int, box)
                label = self.class_names.get(cls, f"class_{cls}")

                detections.append(
                    {
                        "class": label,
                        "confidence": conf,
                        "bbox": [x1, y1, x2, y2],
                    }
                )

                # Color coding: Green for compliance gear, Red for NO-gear, Amber for others
                label_lower = label.lower()
                if "no-" in label_lower:
                    color = (0, 0, 255)  # Red
                elif any(c in label_lower for c in ["hardhat", "helmet", "vest", "mask", "glove"]):
                    color = (0, 255, 0)  # Green
                elif label_lower == "person":
                    color = (255, 200, 0)  # Cyan/Yellow
                else:
                    color = (200, 200, 200)

                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                label_text = f"{label} {conf:.2f}"
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
                cv2.putText(
                    annotated,
                    label_text,
                    (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 0) if color != (0, 0, 255) else (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

        fps = 1.0 / (time.time() - t0 + 1e-6)
        return annotated, detections, fps


def apply_rules(detections: List[Dict[str, Any]]) -> List[str]:
    """
    Evaluates PPE safety rules based on YOLO detected objects in frame.
    Returns a list of unique safety violation descriptions.
    """
    if not detections:
        return []

    labels = [det["class"] for det in detections]
    labels_lower = [l.lower() for l in labels]
    violations = []

    # Check direct violation classes from YOLO model
    if any(l in labels for l in ["NO-Hardhat", "no-hardhat"]):
        violations.append("No Helmet (Hardhat)")
    if any(l in labels for l in ["NO-Safety Vest", "no-safety vest", "no-vest"]):
        violations.append("No Safety Vest")
    if any(l in labels for l in ["NO-Mask", "no-mask"]):
        violations.append("No Face Mask")

    # Person presence check: If workers are in frame but gear is absent
    person_present = any("person" in l for l in labels_lower)
    if person_present:
        has_helmet = any(h in labels_lower for h in ["hardhat", "helmet"])
        has_no_helmet = any("no-hardhat" in l for l in labels_lower)
        if not has_helmet and not has_no_helmet:
            violations.append("No Helmet (Hardhat)")

        has_vest = any(v in labels_lower for v in ["safety vest", "vest"])
        has_no_vest = any("no-safety vest" in l for l in labels_lower)
        if not has_vest and not has_no_vest:
            violations.append("No Safety Vest")

    return list(set(violations))

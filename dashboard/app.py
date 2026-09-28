import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.utils.detection_utils import Detector, apply_rules
from dashboard.utils.log_reader import read_logs, export_csv
from dashboard.utils.alert_manager import trigger_alert_async
from dashboard.modules.compliance_stats import render_compliance_dashboard

MODEL_PATH = PROJECT_ROOT / "model" / "best.pt"
LOG_PATH = PROJECT_ROOT / "dashboard" / "static" / "logs" / "violations.jsonl"
VIDEO_DIR = PROJECT_ROOT / "dashboard" / "static" / "video"
DEMO_VIDEO_PATH = VIDEO_DIR / "demo_sample.mp4"

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


@st.cache_resource
def get_detector(model_path: str):
    """Caches YOLO detector to avoid reloading model weights on every rerun."""
    return Detector(model_path)


def ensure_demo_video():
    """Generates a demo test video if not present on disk."""
    if not DEMO_VIDEO_PATH.exists():
        try:
            from scripts.generate_sample_video import create_demo_video
            create_demo_video()
        except Exception:
            pass


def open_video_capture(source):
    """Opens video capture device or file with platform-specific fallback."""
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    backends = []
    if isinstance(source, int):
        backends = [getattr(cv2, "CAP_DSHOW", None), getattr(cv2, "CAP_MSMF", None), cv2.CAP_ANY]
    else:
        backends = [cv2.CAP_ANY]

    for backend in backends:
        try:
            if backend is None:
                cap = cv2.VideoCapture(source)
            else:
                cap = cv2.VideoCapture(source, backend)

            if cap.isOpened():
                return cap
            cap.release()
        except Exception:
            continue
    return None


def resolve_image_path(raw_path: str) -> Path | None:
    """Cross-platform image resolver to locate snapshots saved on different operating systems."""
    if not raw_path:
        return None
    p = Path(raw_path)
    if p.exists():
        return p
    candidate = VIDEO_DIR / p.name
    if candidate.exists():
        return candidate
    return None


def main():
    ensure_demo_video()

    st.set_page_config(
        page_title="SafetyEye - PPE Workplace Monitor",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Sidebar Navigation
    st.sidebar.title("🛡️ SafetyEye Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["📹 Live Monitoring", "📊 Compliance Analytics", "🎞️ Violation Replay"],
    )

    if page == "📹 Live Monitoring":
        st.title("🛡️ SafetyEye - Real-Time PPE & Safety Monitor")
        st.markdown("Live workplace occupancy and Personal Protective Equipment (PPE) compliance detection.")

        # Sidebar Controls - Exactly 4 Requested Options
        st.sidebar.subheader("Stream Configuration")
        source_mode = st.sidebar.radio(
            "Input Source",
            [
                "1. Webcam (Live Camera Processing)",
                "2. Upload Video / Image to Process",
                "3. URL / File Path Process",
                "4. Demo Video Stream",
            ],
        )

        conf_thresh = st.sidebar.slider("Detection Confidence Threshold", 0.10, 0.95, 0.45, 0.05)
        log_cooldown = st.sidebar.slider("Violation Log Cooldown (seconds)", 1, 60, 5)

        if "running" not in st.session_state:
            st.session_state.running = False
        if "last_log_time" not in st.session_state:
            st.session_state.last_log_time = 0.0

        # ==========================================
        # 1. WEBCAM (Live Camera Processing)
        # ==========================================
        if source_mode == "1. Webcam (Live Camera Processing)":
            st.info("💡 **Webcam Mode**: Take a photo using your laptop/device camera to run real-time YOLOv8 PPE detection and automated compliance alerts.")
            
            col1, col2 = st.columns([2.2, 1.0])
            with col1:
                st.subheader("Live Webcam Input")
                camera_photo = st.camera_input("Point webcam at worker to inspect PPE compliance")
            
            with col2:
                st.subheader("Inspection KPIs")
                fps_metric = st.metric("Inference Time", "0.0 ms")
                active_violations_box = st.empty()
                last_alert_box = st.empty()

            if camera_photo is not None:
                detector = get_detector(str(MODEL_PATH))
                detector.conf_thresh = conf_thresh

                bytes_data = camera_photo.getvalue()
                cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)

                if cv2_img is not None:
                    t0 = time.time()
                    annotated, detections, fps = detector.run_on_frame(cv2_img)
                    latency_ms = (time.time() - t0) * 1000.0
                    fps_metric.metric("Inference Time", f"{latency_ms:.1f} ms")

                    annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                    st.image(annotated_rgb, caption="Analyzed Webcam Frame", channels="RGB", use_container_width=True)

                    violations = apply_rules(detections)
                    ts_str = datetime.now().isoformat()
                    now_time = time.time()

                    if violations:
                        active_violations_box.error(f"⚠️ Active Violations: {', '.join(violations)}")

                        if (now_time - st.session_state.last_log_time) >= log_cooldown:
                            st.session_state.last_log_time = now_time

                            img_filename = f"violation_{datetime.now().strftime('%Y%m%d_%H%M%S')}_webcam.jpg"
                            img_path = VIDEO_DIR / img_filename
                            cv2.imwrite(str(img_path), annotated)

                            max_conf = max((d["confidence"] for d in detections), default=0.0)

                            for v in violations:
                                record = {
                                    "id": f"{ts_str}_{v.replace(' ', '_')}",
                                    "timestamp": ts_str,
                                    "frame_image": img_filename,
                                    "violation_type": v,
                                    "confidence": max_conf,
                                    "worker_id": "Worker-01",
                                    "source": "Webcam",
                                }
                                with open(LOG_PATH, "a", encoding="utf-8") as lf:
                                    lf.write(json.dumps(record) + "\n")

                            consolidated_alert = {
                                "id": ts_str,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "frame_image": str(img_path),
                                "violations": violations,
                                "confidence": max_conf,
                                "worker_id": "Worker-01",
                                "source": "Webcam",
                            }
                            trigger_alert_async(consolidated_alert)
                            last_alert_box.warning(f"🚨 Logged Alert: {', '.join(violations)} at {datetime.now().strftime('%H:%M:%S')}")
                    else:
                        active_violations_box.success("✅ All Workers Compliant")
            else:
                active_violations_box.info("Waiting for webcam capture...")

        # ==========================================
        # 2. UPLOAD VIDEO / IMAGE TO PROCESS
        # ==========================================
        elif source_mode == "2. Upload Video / Image to Process":
            uploaded_file = st.sidebar.file_uploader(
                "Upload Video (MP4/AVI/MOV) or Image (JPG/PNG/JPEG)",
                type=["mp4", "avi", "mov", "jpg", "jpeg", "png", "webp"],
            )

            if uploaded_file is not None:
                file_ext = Path(uploaded_file.name).suffix.lower()

                # Case A: Uploaded File is an Image
                if file_ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    col1, col2 = st.columns([2.2, 1.0])
                    with col1:
                        st.subheader("Image Detection Result")
                        frame_slot = st.empty()

                    with col2:
                        st.subheader("Inspection KPIs")
                        fps_metric = st.metric("Inference Time", "0.0 ms")
                        active_violations_box = st.empty()
                        last_alert_box = st.empty()

                    detector = get_detector(str(MODEL_PATH))
                    detector.conf_thresh = conf_thresh

                    file_bytes = np.frombuffer(uploaded_file.read(), np.uint8)
                    cv2_img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

                    if cv2_img is not None:
                        t0 = time.time()
                        annotated, detections, fps = detector.run_on_frame(cv2_img)
                        latency_ms = (time.time() - t0) * 1000.0
                        fps_metric.metric("Inference Time", f"{latency_ms:.1f} ms")

                        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                        frame_slot.image(annotated_rgb, caption=f"Analyzed Image: {uploaded_file.name}", channels="RGB", use_container_width=True)

                        violations = apply_rules(detections)
                        ts_str = datetime.now().isoformat()

                        if violations:
                            active_violations_box.error(f"⚠️ Active Violations: {', '.join(violations)}")

                            img_filename = f"violation_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
                            img_path = VIDEO_DIR / img_filename
                            cv2.imwrite(str(img_path), annotated)

                            max_conf = max((d["confidence"] for d in detections), default=0.0)

                            for v in violations:
                                record = {
                                    "id": f"{ts_str}_{v.replace(' ', '_')}",
                                    "timestamp": ts_str,
                                    "frame_image": img_filename,
                                    "violation_type": v,
                                    "confidence": max_conf,
                                    "worker_id": "Worker-01",
                                    "source": f"Upload: {uploaded_file.name}",
                                }
                                with open(LOG_PATH, "a", encoding="utf-8") as lf:
                                    lf.write(json.dumps(record) + "\n")

                            consolidated_alert = {
                                "id": ts_str,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "frame_image": str(img_path),
                                "violations": violations,
                                "confidence": max_conf,
                                "worker_id": "Worker-01",
                                "source": f"Upload: {uploaded_file.name}",
                            }
                            trigger_alert_async(consolidated_alert)
                            last_alert_box.warning(f"🚨 Logged Alert: {', '.join(violations)} at {datetime.now().strftime('%H:%M:%S')}")
                        else:
                            active_violations_box.success("✅ All Workers Compliant")

                # Case B: Uploaded File is a Video
                else:
                    temp_video_path = VIDEO_DIR / f"temp_{uploaded_file.name}"
                    with open(temp_video_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    col_btn1, col_btn2 = st.sidebar.columns(2)
                    start_button = col_btn1.button("▶️ Start Video", use_container_width=True)
                    stop_button = col_btn2.button("⏹️ Stop Video", use_container_width=True)

                    if start_button:
                        st.session_state.running = True
                    if stop_button:
                        st.session_state.running = False

                    col1, col2 = st.columns([2.2, 1.0])
                    with col1:
                        st.subheader("Live Detection Stream")
                        frame_slot = st.empty()

                    with col2:
                        st.subheader("Live Status & KPIs")
                        fps_metric = st.metric("Processing FPS", "0.0")
                        active_violations_box = st.empty()
                        last_alert_box = st.empty()

                    if st.session_state.running:
                        detector = get_detector(str(MODEL_PATH))
                        detector.conf_thresh = conf_thresh
                        cap = open_video_capture(str(temp_video_path))

                        if cap is None or not cap.isOpened():
                            st.error(f"❌ Failed to open uploaded video file.")
                            st.session_state.running = False
                        else:
                            try:
                                while st.session_state.running:
                                    ret, frame = cap.read()
                                    if not ret:
                                        st.info("End of video stream reached.")
                                        break

                                    annotated, detections, fps = detector.run_on_frame(frame)
                                    fps_metric.metric("Processing FPS", f"{fps:.1f}")

                                    annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                                    frame_slot.image(annotated_rgb, channels="RGB", use_container_width=True)

                                    violations = apply_rules(detections)
                                    now_time = time.time()
                                    ts_str = datetime.now().isoformat()

                                    if violations:
                                        active_violations_box.error(f"⚠️ Active Violations: {', '.join(violations)}")

                                        if (now_time - st.session_state.last_log_time) >= log_cooldown:
                                            st.session_state.last_log_time = now_time

                                            img_filename = f"violation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                            img_path = VIDEO_DIR / img_filename
                                            cv2.imwrite(str(img_path), annotated)

                                            max_conf = max((d["confidence"] for d in detections), default=0.0)

                                            for v in violations:
                                                record = {
                                                    "id": f"{ts_str}_{v.replace(' ', '_')}",
                                                    "timestamp": ts_str,
                                                    "frame_image": img_filename,
                                                    "violation_type": v,
                                                    "confidence": max_conf,
                                                    "worker_id": "Worker-01",
                                                    "source": uploaded_file.name,
                                                }
                                                with open(LOG_PATH, "a", encoding="utf-8") as lf:
                                                    lf.write(json.dumps(record) + "\n")

                                            consolidated_alert = {
                                                "id": ts_str,
                                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                "frame_image": str(img_path),
                                                "violations": violations,
                                                "confidence": max_conf,
                                                "worker_id": "Worker-01",
                                                "source": uploaded_file.name,
                                            }
                                            trigger_alert_async(consolidated_alert)
                                            last_alert_box.warning(f"🚨 Logged Alert: {', '.join(violations)} at {datetime.now().strftime('%H:%M:%S')}")
                                    else:
                                        active_violations_box.success("✅ All Workers Compliant")

                                    time.sleep(0.01)
                            finally:
                                cap.release()
                                st.session_state.running = False
                    else:
                        frame_slot.info("💡 Click **Start Video** to process the uploaded video.")
            else:
                st.info("💡 Upload any video or image file in the sidebar to begin processing.")

        # ==========================================
        # 3. URL / FILE PATH PROCESS
        # ==========================================
        elif source_mode == "3. URL / File Path Process":
            video_url = st.sidebar.text_input("Enter RTSP Stream URL or Local Video Path", "dashboard/static/video/demo_sample.mp4")

            col_btn1, col_btn2 = st.sidebar.columns(2)
            start_button = col_btn1.button("▶️ Start Stream", use_container_width=True)
            stop_button = col_btn2.button("⏹️ Stop Stream", use_container_width=True)

            if start_button:
                st.session_state.running = True
            if stop_button:
                st.session_state.running = False

            col1, col2 = st.columns([2.2, 1.0])
            with col1:
                st.subheader("Stream Detection Stream")
                frame_slot = st.empty()

            with col2:
                st.subheader("Live Status & KPIs")
                fps_metric = st.metric("Processing FPS", "0.0")
                active_violations_box = st.empty()
                last_alert_box = st.empty()

            if st.session_state.running and video_url:
                detector = get_detector(str(MODEL_PATH))
                detector.conf_thresh = conf_thresh
                cap = open_video_capture(video_url)

                if cap is None or not cap.isOpened():
                    st.error(f"❌ Failed to open stream from '{video_url}'.")
                    st.session_state.running = False
                else:
                    try:
                        while st.session_state.running:
                            ret, frame = cap.read()
                            if not ret:
                                st.info("End of video stream reached.")
                                break

                            annotated, detections, fps = detector.run_on_frame(frame)
                            fps_metric.metric("Processing FPS", f"{fps:.1f}")

                            annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                            frame_slot.image(annotated_rgb, channels="RGB", use_container_width=True)

                            violations = apply_rules(detections)
                            now_time = time.time()
                            ts_str = datetime.now().isoformat()

                            if violations:
                                active_violations_box.error(f"⚠️ Active Violations: {', '.join(violations)}")

                                if (now_time - st.session_state.last_log_time) >= log_cooldown:
                                    st.session_state.last_log_time = now_time

                                    img_filename = f"violation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                    img_path = VIDEO_DIR / img_filename
                                    cv2.imwrite(str(img_path), annotated)

                                    max_conf = max((d["confidence"] for d in detections), default=0.0)

                                    for v in violations:
                                        record = {
                                            "id": f"{ts_str}_{v.replace(' ', '_')}",
                                            "timestamp": ts_str,
                                            "frame_image": img_filename,
                                            "violation_type": v,
                                            "confidence": max_conf,
                                            "worker_id": "Worker-01",
                                            "source": str(video_url),
                                        }
                                        with open(LOG_PATH, "a", encoding="utf-8") as lf:
                                            lf.write(json.dumps(record) + "\n")

                                    consolidated_alert = {
                                        "id": ts_str,
                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "frame_image": str(img_path),
                                        "violations": violations,
                                        "confidence": max_conf,
                                        "worker_id": "Worker-01",
                                        "source": str(video_url),
                                    }
                                    trigger_alert_async(consolidated_alert)
                                    last_alert_box.warning(f"🚨 Logged Alert: {', '.join(violations)} at {datetime.now().strftime('%H:%M:%S')}")
                            else:
                                active_violations_box.success("✅ All Workers Compliant")

                            time.sleep(0.01)
                    finally:
                        cap.release()
                        st.session_state.running = False
            else:
                frame_slot.info("💡 Enter stream URL / path and click **Start Stream**.")

        # ==========================================
        # 4. DEMO VIDEO STREAM
        # ==========================================
        elif source_mode == "4. Demo Video Stream":
            col_btn1, col_btn2 = st.sidebar.columns(2)
            start_button = col_btn1.button("▶️ Start Demo Stream", use_container_width=True)
            stop_button = col_btn2.button("⏹️ Stop Demo Stream", use_container_width=True)

            if start_button:
                st.session_state.running = True
            if stop_button:
                st.session_state.running = False

            col1, col2 = st.columns([2.2, 1.0])
            with col1:
                st.subheader("Demo Detection Stream")
                frame_slot = st.empty()

            with col2:
                st.subheader("Live Status & KPIs")
                fps_metric = st.metric("Processing FPS", "0.0")
                active_violations_box = st.empty()
                last_alert_box = st.empty()

            if st.session_state.running:
                detector = get_detector(str(MODEL_PATH))
                detector.conf_thresh = conf_thresh
                cap = open_video_capture(str(DEMO_VIDEO_PATH))

                if cap is None or not cap.isOpened():
                    st.error("❌ Failed to open demo sample video.")
                    st.session_state.running = False
                else:
                    try:
                        while st.session_state.running:
                            ret, frame = cap.read()
                            if not ret:
                                st.info("End of demo stream reached.")
                                break

                            annotated, detections, fps = detector.run_on_frame(frame)
                            fps_metric.metric("Processing FPS", f"{fps:.1f}")

                            annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                            frame_slot.image(annotated_rgb, channels="RGB", use_container_width=True)

                            violations = apply_rules(detections)
                            now_time = time.time()
                            ts_str = datetime.now().isoformat()

                            if violations:
                                active_violations_box.error(f"⚠️ Active Violations: {', '.join(violations)}")

                                if (now_time - st.session_state.last_log_time) >= log_cooldown:
                                    st.session_state.last_log_time = now_time

                                    img_filename = f"violation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                    img_path = VIDEO_DIR / img_filename
                                    cv2.imwrite(str(img_path), annotated)

                                    max_conf = max((d["confidence"] for d in detections), default=0.0)

                                    for v in violations:
                                        record = {
                                            "id": f"{ts_str}_{v.replace(' ', '_')}",
                                            "timestamp": ts_str,
                                            "frame_image": img_filename,
                                            "violation_type": v,
                                            "confidence": max_conf,
                                            "worker_id": "Worker-01",
                                            "source": "Demo Stream",
                                        }
                                        with open(LOG_PATH, "a", encoding="utf-8") as lf:
                                            lf.write(json.dumps(record) + "\n")

                                    consolidated_alert = {
                                        "id": ts_str,
                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "frame_image": str(img_path),
                                        "violations": violations,
                                        "confidence": max_conf,
                                        "worker_id": "Worker-01",
                                        "source": "Demo Stream",
                                    }
                                    trigger_alert_async(consolidated_alert)
                                    last_alert_box.warning(f"🚨 Logged Alert: {', '.join(violations)} at {datetime.now().strftime('%H:%M:%S')}")
                            else:
                                active_violations_box.success("✅ All Workers Compliant")

                            time.sleep(0.01)
                    finally:
                        cap.release()
                        st.session_state.running = False
            else:
                frame_slot.info("💡 Click **Start Demo Stream** in the sidebar to run simulated workplace detection.")

        # Recent Logs Summary Table below
        st.markdown("---")
        st.subheader("Recent Violation Activity Log")
        df_logs = read_logs()
        if not df_logs.empty:
            st.dataframe(df_logs.sort_values(by="timestamp", ascending=False).head(15), use_container_width=True)
        else:
            st.info("No logs generated yet.")

    elif page == "📊 Compliance Analytics":
        render_compliance_dashboard()

    elif page == "🎞️ Violation Replay":
        st.title("🎞️ Violation Log Replay & Snapshot Viewer")
        st.markdown("Review captured violation images with inspection metadata.")

        df = read_logs()
        if df.empty:
            st.info("No recorded violation snapshots found.")
        else:
            df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
            options = [
                f"[{row['timestamp']}] — {row.get('violation_type', 'Unknown')} (Conf: {row.get('confidence', 0.0):.2f})"
                for _, row in df.iterrows()
            ]

            selected_idx = st.selectbox("Select Violation Record to Inspect", range(len(options)), format_func=lambda i: options[i])
            record = df.iloc[selected_idx].to_dict()

            col_img, col_info = st.columns([2, 1])
            with col_img:
                raw_img = record.get("frame_image")
                img_path = resolve_image_path(raw_img)
                if img_path and img_path.exists():
                    img = cv2.imread(str(img_path))
                    if img is not None:
                        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        st.image(img_rgb, caption=f"Captured Snapshot: {record.get('violation_type')}", use_container_width=True)
                    else:
                        st.warning("Snapshot file could not be read.")
                else:
                    st.warning("Snapshot image file is no longer available on disk.")

            with col_info:
                st.subheader("Violation Metadata")
                st.json(record)


if __name__ == "__main__":
    main()

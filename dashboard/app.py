import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
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
    # Try finding in local VIDEO_DIR by file name (e.g. if logged on Windows and viewed on Linux)
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

        # Sidebar Controls
        st.sidebar.subheader("Stream Configuration")
        source_mode = st.sidebar.radio(
            "Input Source",
            [
                "Upload Video File",
                "Demo Video Stream",
                "Video File Path / RTSP",
                "Webcam",
            ],
        )

        video_source = 0
        temp_video_path = None

        if source_mode == "Upload Video File":
            uploaded_file = st.sidebar.file_uploader("Upload MP4 / AVI / MOV", type=["mp4", "avi", "mov"])
            if uploaded_file is not None:
                temp_video_path = VIDEO_DIR / f"temp_{uploaded_file.name}"
                with open(temp_video_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                video_source = str(temp_video_path)
            else:
                video_source = None
        elif source_mode == "Demo Video Stream":
            video_source = str(DEMO_VIDEO_PATH)
        elif source_mode == "Video File Path / RTSP":
            video_source = st.sidebar.text_input("Enter Video File / RTSP Stream URL", "dashboard/static/video/demo_sample.mp4")
        elif source_mode == "Webcam":
            cam_idx = st.sidebar.number_input("Camera Index", min_value=0, max_value=10, value=0, step=1)
            video_source = int(cam_idx)

        conf_thresh = st.sidebar.slider("Detection Confidence Threshold", 0.10, 0.95, 0.45, 0.05)
        log_cooldown = st.sidebar.slider("Violation Log Cooldown (seconds)", 1, 60, 5)

        col_btn1, col_btn2 = st.sidebar.columns(2)
        start_button = col_btn1.button("▶️ Start Stream", use_container_width=True)
        stop_button = col_btn2.button("⏹️ Stop Stream", use_container_width=True)

        if "running" not in st.session_state:
            st.session_state.running = False
        if "last_log_time" not in st.session_state:
            st.session_state.last_log_time = 0.0

        if start_button:
            if video_source is None:
                st.sidebar.error("Please upload a video file first.")
            else:
                st.session_state.running = True
        if stop_button:
            st.session_state.running = False

        # Layout Columns
        col1, col2 = st.columns([2.2, 1.0])

        with col1:
            st.subheader("Live Detection Stream")
            frame_slot = st.empty()

        with col2:
            st.subheader("Live Status & KPIs")
            fps_metric = st.metric("Processing FPS", "0.0")
            active_violations_box = st.empty()
            last_alert_box = st.empty()

        if st.session_state.running and video_source is not None:
            if not MODEL_PATH.exists():
                st.error(f"❌ Model file not found at '{MODEL_PATH}'. Please ensure 'model/best.pt' exists.")
                st.session_state.running = False
            else:
                detector = get_detector(str(MODEL_PATH))
                detector.conf_thresh = conf_thresh
                cap = open_video_capture(video_source)

                if cap is None or not cap.isOpened():
                    if isinstance(video_source, int):
                        st.error("❌ Failed to open video source. Physical camera #0 is only accessible when running locally. On cloud deployment, please choose 'Upload Video File' or 'Demo Video Stream'!")
                    else:
                        st.error(f"❌ Failed to open video source '{video_source}'. Please verify file format or stream URL.")
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

                            # Render Frame
                            annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                            frame_slot.image(annotated_rgb, channels="RGB", use_container_width=True)

                            # Evaluate Safety Rules
                            violations = apply_rules(detections)
                            now_time = time.time()

                            if violations:
                                active_violations_box.error(f"⚠️ Active Violations: {', '.join(violations)}")
                                ts_str = datetime.now().isoformat()

                                if (now_time - st.session_state.last_log_time) >= log_cooldown:
                                    st.session_state.last_log_time = now_time

                                    img_filename = f"violation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                    img_path = VIDEO_DIR / img_filename
                                    cv2.imwrite(str(img_path), annotated)

                                    max_conf = max((d["confidence"] for d in detections), default=0.0)

                                    # Log each individual violation for detailed analytics/charts
                                    for v in violations:
                                        record = {
                                            "id": f"{ts_str}_{v.replace(' ', '_')}",
                                            "timestamp": ts_str,
                                            "frame_image": img_filename,
                                            "violation_type": v,
                                            "confidence": max_conf,
                                            "worker_id": "Worker-01",
                                            "source": str(video_source),
                                        }
                                        with open(LOG_PATH, "a", encoding="utf-8") as lf:
                                            lf.write(json.dumps(record) + "\n")

                                    # Send ONE combined email alert with all detected violations
                                    consolidated_alert = {
                                        "id": ts_str,
                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "frame_image": str(img_path),
                                        "violations": violations,
                                        "confidence": max_conf,
                                        "worker_id": "Worker-01",
                                        "source": str(video_source),
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
            frame_slot.info("💡 Select your stream configuration in the sidebar and click **Start Stream**.")

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

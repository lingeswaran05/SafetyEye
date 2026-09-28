# 🛡️ SafetyEye — AI Powered Workplace Occupancy & Safety Monitor

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io/)
[![YOLOv8](https://img.shields.io/badge/Vision-YOLOv8-green.svg)](https://github.com/ultralytics/ultralytics)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**SafetyEye** is an intelligent, real-time computer vision system engineered for industrial environments and construction sites. It automates Personal Protective Equipment (PPE) compliance detection, logs safety violations with snapshot evidence, and offers visual analytics to ensure a zero-hazard workplace.

---

## 🌟 Key Features

* **Real-time PPE Detection**: Custom-trained YOLOv8 computer vision model detecting Hardhats, Safety Vests, Masks, Personnel, and non-compliance flags (`NO-Hardhat`, `NO-Safety Vest`, `NO-Mask`).
* **Multi-Source Input**: Supports live webcams, RTSP IP camera streams, local video files, and browser file uploads.
* **Smart Violation Rule Engine**: Automatically detects missing safety gear on detected personnel and triggers safety alerts.
* **Instant Snapshot & Event Logging**: Saves violation evidence frames and logs JSONL audit trails with cooldown throttling to prevent redundant alarms.
* **Compliance Analytics Dashboard**: Interactive analytics with charts for compliance rates, hourly trends, category breakdown, and raw CSV report exporting.
* **Asynchronous Email Alerts**: Real-time email dispatch to safety officers with snapshot attachments on violation triggers with 1-minute rate limiting.

---

## 📁 Repository Structure

```
SafetyEye/
│
├── .env.example              # Template for email alert credentials
├── .gitignore                # Git ignore configuration
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies
├── app.py                    # Main application entry point
├── run_dashboard.py          # Python runner script
│
├── model/
│   ├── best.pt               # Trained YOLOv8 model weights
│   └── class_names.txt       # Detection class definitions
│
├── dashboard/
│   ├── __init__.py
│   ├── app.py                # Core Streamlit user interface
│   ├── modules/
│   │   ├── __init__.py
│   │   └── compliance_stats.py # Charts & compliance metrics
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── alert_manager.py  # Email dispatch & cooldown manager
│   │   ├── detection_utils.py# YOLOv8 inference & rule evaluator
│   │   └── log_reader.py     # Log storage & CSV export utilities
│   └── static/
│       ├── logs/             # Violation audit logs (.jsonl)
│       └── video/            # Saved violation frame snapshots
│
└── scripts/
    ├── __init__.py
    ├── realtime_inference.py # Standalone CLI inference tool
    └── test_email.py         # Email diagnostic test script
```

---

## 🚀 Quick Start & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/lingeswaran05/SafetyEye.git
cd SafetyEye
```

### 2. Create and Activate a Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🖥️ Running the Application

### Launch Streamlit Dashboard
Run the runner script:
```bash
python run_dashboard.py
```
Or execute Streamlit directly:
```bash
streamlit run app.py
```
Open your browser at **`http://localhost:8501`**.

---

## ⚡ Standalone CLI Mode

Run inference directly on a video file or camera stream from the command line:

```bash
# Run on webcam (Index 0)
python scripts/realtime_inference.py --source 0

# Run on a video file
python scripts/realtime_inference.py --source path/to/video.mp4 --conf 0.50
```

---

## ⚙️ Email Alert Configuration

1. Copy `.env.example` to `.env` (or use existing `.env`):
   ```bash
   cp .env.example .env
   ```
2. Configure SMTP settings in `.env`:
   ```ini
   SAFETYEYE_SMTP_SERVER=smtp.gmail.com
   SAFETYEYE_SMTP_PORT=587
   SAFETYEYE_SENDER_EMAIL=your_email@gmail.com
   SAFETYEYE_SENDER_PASSWORD=your_app_password
   SAFETYEYE_RECEIVER_EMAILS=safety_officer@company.com
   SAFETYEYE_EMAIL_COOLDOWN=60
   ```
3. Test your email setup:
   ```bash
   python scripts/test_email.py
   ```

---

## 📊 Detection Classes

| Class | Description | Compliance Status |
| :--- | :--- | :--- |
| `Hardhat` | Safety helmet present | ✅ Compliant |
| `Safety Vest` | High-visibility vest present | ✅ Compliant |
| `Mask` | Protective face mask | ✅ Compliant |
| `Person` | Worker / Person detected | ℹ️ Monitored |
| `NO-Hardhat` | Worker missing safety helmet | 🚨 Violation |
| `NO-Safety Vest` | Worker missing safety vest | 🚨 Violation |
| `NO-Mask` | Worker missing mask | 🚨 Violation |

---

## 📝 License
This project is licensed under the MIT License.
